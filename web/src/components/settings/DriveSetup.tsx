import { useState, useEffect } from "react"
import { useDriveStatus, useDriveAuthUrl, useDriveDrives, useDriveFolders, useDriveSetup } from "@/hooks/queries/use-drive"

export function DriveSetup() {
  const { data: status } = useDriveStatus()
  const authUrl = useDriveAuthUrl()
  const setup = useDriveSetup()

  const [step, setStep] = useState(1)
  const [clientId, setClientId] = useState("")
  const [clientSecret, setClientSecret] = useState("")

  // Connected state
  if (status?.connected && step === 1) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500" />
          <span className="text-sm font-medium" style={{ color: "#37352f" }}>
            Google Drive 연결됨
          </span>
        </div>
        {status.drive_id && (
          <p className="text-sm" style={{ color: "#787774" }}>
            드라이브 ID: {status.drive_id || "내 드라이브"}
          </p>
        )}
        <button
          onClick={() => setStep(2)}
          className="text-sm underline"
          style={{ color: "#787774" }}
        >
          설정 변경
        </button>
      </div>
    )
  }

  // Step 1: OAuth credentials
  if (step === 1) {
    return (
      <div className="space-y-4">
        <h3 className="text-sm font-semibold" style={{ color: "#37352f" }}>
          1. Google Cloud Console에서 OAuth 2.0 클라이언트 생성
        </h3>
        <p className="text-sm" style={{ color: "#787774" }}>
          Google Cloud Console → APIs &amp; Services → Credentials에서
          OAuth 2.0 Client ID를 생성하세요. 유형은 &quot;Web application&quot;으로 선택하고,
          Redirect URI에 현재 호스트의 /api/internal/drive/callback을 추가하세요.
        </p>
        <div className="space-y-2">
          <input
            type="text"
            placeholder="Client ID"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="w-full rounded border px-3 py-2 text-sm"
            style={{ borderColor: "#e8e5df" }}
          />
          <input
            type="password"
            placeholder="Client Secret"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            className="w-full rounded border px-3 py-2 text-sm"
            style={{ borderColor: "#e8e5df" }}
          />
        </div>
        <button
          disabled={!clientId || !clientSecret || authUrl.isPending}
          onClick={async () => {
            const result = await authUrl.mutateAsync({ client_id: clientId, client_secret: clientSecret })
            window.open(result.auth_url, "_blank", "width=500,height=700")
            setStep(2)
          }}
          className="rounded px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: "#37352f" }}
        >
          {authUrl.isPending ? "생성 중..." : "Google Drive 연결"}
        </button>
      </div>
    )
  }

  // Step 2: Select drive & folder (after OAuth callback)
  return (
    <DriveSelector
      onComplete={(driveId, folderId) => {
        setup.mutate({ drive_id: driveId, root_folder_id: folderId })
        setStep(1)
      }}
    />
  )
}

function DriveSelector({ onComplete }: { onComplete: (driveId: string, folderId: string) => void }) {
  const [selectedDrive, setSelectedDrive] = useState("")
  const [selectedFolder, setSelectedFolder] = useState("")
  const [parentStack, setParentStack] = useState<Array<{ id: string; name: string }>>([])
  const drives = useDriveDrives()
  const currentParent = parentStack.length > 0 ? parentStack[parentStack.length - 1].id : ""
  const folders = useDriveFolders({ drive_id: selectedDrive, parent_id: currentParent })

  // Fetch drives on mount
  useEffect(() => {
    drives.refetch()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold" style={{ color: "#37352f" }}>
        2. 드라이브 &amp; 폴더 선택
      </h3>

      {/* Drive selector */}
      <div>
        <label className="text-xs font-medium" style={{ color: "#787774" }}>드라이브</label>
        <select
          value={selectedDrive}
          onChange={(e) => {
            setSelectedDrive(e.target.value)
            setParentStack([])
            setSelectedFolder("")
          }}
          className="mt-1 w-full rounded border px-3 py-2 text-sm"
          style={{ borderColor: "#e8e5df" }}
        >
          <option value="">선택하세요</option>
          {drives.data?.drives.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
      </div>

      {/* Folder browser */}
      {selectedDrive !== undefined && (
        <div>
          <label className="text-xs font-medium" style={{ color: "#787774" }}>폴더</label>
          <div className="mt-1 rounded border p-2 text-sm" style={{ borderColor: "#e8e5df", maxHeight: 200, overflowY: "auto" }}>
            {/* Breadcrumb */}
            <div className="flex gap-1 text-xs mb-2" style={{ color: "#787774" }}>
              <button onClick={() => { setParentStack([]); setSelectedFolder("") }}>루트</button>
              {parentStack.map((p, i) => (
                <span key={p.id}>
                  {" / "}
                  <button onClick={() => {
                    setParentStack(parentStack.slice(0, i + 1))
                    setSelectedFolder(p.id)
                  }}>{p.name}</button>
                </span>
              ))}
            </div>

            {/* Use entire drive option */}
            <div
              className={`cursor-pointer rounded px-2 py-1 ${selectedFolder === "" ? "font-medium" : ""}`}
              style={{ backgroundColor: selectedFolder === "" ? "#f7f6f3" : "transparent" }}
              onClick={() => setSelectedFolder("")}
            >
              📁 전체 드라이브 사용
            </div>

            {folders.data?.folders.map((f) => (
              <div
                key={f.id}
                className={`cursor-pointer rounded px-2 py-1 flex justify-between items-center ${selectedFolder === f.id ? "font-medium" : ""}`}
                style={{ backgroundColor: selectedFolder === f.id ? "#f7f6f3" : "transparent" }}
                onClick={() => setSelectedFolder(f.id)}
                onDoubleClick={() => {
                  setParentStack([...parentStack, f])
                  setSelectedFolder(f.id)
                }}
              >
                <span>📁 {f.name}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setParentStack([...parentStack, f])
                  }}
                  className="text-xs px-1 rounded"
                  style={{ color: "#787774" }}
                >
                  →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => onComplete(selectedDrive, selectedFolder)}
        className="rounded px-4 py-2 text-sm font-medium text-white"
        style={{ backgroundColor: "#37352f" }}
      >
        저장
      </button>
    </div>
  )
}
