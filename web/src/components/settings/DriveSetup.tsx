import { useState, useEffect } from "react"
import { useDriveStatus, useDriveAuthUrl, useDriveDrives, useDriveFolders, useDriveSetup } from "@/hooks/queries/use-drive"

function CopyableCode({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="flex items-center gap-2 rounded border px-3 py-2 text-sm font-mono" style={{ borderColor: "#e8e5df", backgroundColor: "#f7f6f3" }}>
      <span className="flex-1 break-all" style={{ color: "#37352f" }}>{value}</span>
      <button
        onClick={() => {
          navigator.clipboard.writeText(value)
          setCopied(true)
          setTimeout(() => setCopied(false), 2000)
        }}
        className="shrink-0 rounded px-2 py-0.5 text-xs font-medium transition-colors"
        style={{ backgroundColor: copied ? "#e8f5e9" : "#e8e5df", color: copied ? "#2e7d32" : "#37352f" }}
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  )
}

function StepBadge({ n }: { n: number }) {
  return (
    <span
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
      style={{ backgroundColor: "#37352f" }}
    >
      {n}
    </span>
  )
}

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline" style={{ color: "#0d6efd" }}>
      {children}
    </a>
  )
}

export function DriveSetup() {
  const { data: status } = useDriveStatus()
  const authUrl = useDriveAuthUrl()
  const setup = useDriveSetup()

  const [step, setStep] = useState(1)
  const [clientId, setClientId] = useState("")
  const [clientSecret, setClientSecret] = useState("")

  const redirectUri = `${window.location.origin}/api/internal/drive/callback`

  // Connected state
  if (status?.connected && step === 1) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500" />
          <span className="text-sm font-medium" style={{ color: "#37352f" }}>
            Google Drive connected
          </span>
        </div>
        {status.drive_id && (
          <p className="text-xs" style={{ color: "#787774" }}>
            Drive ID: {status.drive_id}
          </p>
        )}
        <button
          onClick={() => setStep(2)}
          className="text-xs underline"
          style={{ color: "#787774" }}
        >
          Change settings
        </button>
      </div>
    )
  }

  // Step 1: OAuth credentials with setup guide
  if (step === 1) {
    return (
      <div className="space-y-6">

        {/* Setup Guide */}
        <div className="space-y-4">
          <p className="text-sm font-semibold" style={{ color: "#37352f" }}>
            Connect Google Drive via OAuth 2.0
          </p>
          <p className="text-xs" style={{ color: "#787774" }}>
            You need a Google Cloud project with the Drive API enabled. Follow the steps below — this is a one-time setup.
          </p>

          {/* Step A */}
          <div className="flex gap-3">
            <StepBadge n={1} />
            <div className="space-y-1 text-sm" style={{ color: "#37352f" }}>
              <p className="font-medium">Enable Google Drive API</p>
              <p className="text-xs" style={{ color: "#787774" }}>
                Go to{" "}
                <ExternalLink href="https://console.cloud.google.com/apis/library/drive.googleapis.com">
                  Google Cloud Console → APIs & Services → Library
                </ExternalLink>
                , search for <strong>Google Drive API</strong>, and click <strong>Enable</strong>.
              </p>
            </div>
          </div>

          {/* Step B */}
          <div className="flex gap-3">
            <StepBadge n={2} />
            <div className="space-y-1 text-sm" style={{ color: "#37352f" }}>
              <p className="font-medium">Configure OAuth Consent Screen</p>
              <p className="text-xs" style={{ color: "#787774" }}>
                Go to <strong>APIs & Services → OAuth consent screen</strong>.
              </p>
              <ol className="list-decimal list-inside space-y-0.5 text-xs" style={{ color: "#787774" }}>
                <li>User Type: select <strong>External</strong> → Create</li>
                <li>Fill in App name (e.g. <em>Maestro Local</em>) and your email</li>
                <li>Skip Scopes — click Save and Continue</li>
                <li>Under <strong>Test users</strong>, add your Google account email</li>
                <li>Publishing status: leave as <strong>Testing</strong> (no Google review needed)</li>
              </ol>
            </div>
          </div>

          {/* Step C */}
          <div className="flex gap-3">
            <StepBadge n={3} />
            <div className="space-y-2 text-sm" style={{ color: "#37352f" }}>
              <p className="font-medium">Create OAuth 2.0 Client ID</p>
              <p className="text-xs" style={{ color: "#787774" }}>
                Go to <strong>APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID</strong>.
              </p>
              <ol className="list-decimal list-inside space-y-0.5 text-xs" style={{ color: "#787774" }}>
                <li>Application type: <strong>Web application</strong></li>
                <li>
                  Under <strong>Authorized redirect URIs</strong>, click <strong>Add URI</strong> and paste:
                </li>
              </ol>
              <CopyableCode value={redirectUri} />
              <p className="text-xs" style={{ color: "#787774" }}>
                3. Click <strong>Create</strong> — a dialog will show your Client ID and Client Secret.
              </p>
            </div>
          </div>

          {/* Step D */}
          <div className="flex gap-3">
            <StepBadge n={4} />
            <div className="space-y-2 text-sm" style={{ color: "#37352f" }}>
              <p className="font-medium">Paste your credentials below</p>
              <p className="text-xs" style={{ color: "#787774" }}>
                Copy the Client ID and Client Secret from the dialog and paste them here.
              </p>
              <div className="space-y-2">
                <input
                  type="text"
                  placeholder="Client ID  (e.g. 123456789-abc…apps.googleusercontent.com)"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  className="w-full rounded border px-3 py-2 text-sm"
                  style={{ borderColor: "#e8e5df" }}
                />
                <input
                  type="password"
                  placeholder="Client Secret  (e.g. GOCSPX-…)"
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  className="w-full rounded border px-3 py-2 text-sm"
                  style={{ borderColor: "#e8e5df" }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Connect button */}
        <div className="space-y-2">
          <button
            disabled={!clientId || !clientSecret || authUrl.isPending}
            onClick={async () => {
              const result = await authUrl.mutateAsync({ client_id: clientId, client_secret: clientSecret })
              window.open(result.auth_url, "_blank", "width=520,height=700")
              setStep(2)
            }}
            className="w-full rounded px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            style={{ backgroundColor: "#37352f" }}
          >
            {authUrl.isPending ? "Generating auth URL…" : "Connect Google Drive →"}
          </button>
          <p className="text-xs text-center" style={{ color: "#787774" }}>
            A Google sign-in window will open. After authorizing, you'll be redirected back here.
          </p>
        </div>
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

  useEffect(() => {
    drives.refetch()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-semibold" style={{ color: "#37352f" }}>Select Drive &amp; Folder</p>
        <p className="text-xs mt-0.5" style={{ color: "#787774" }}>
          Choose where Maestro will store uploaded assets. Double-click a folder to browse into it.
        </p>
      </div>

      {/* Drive selector */}
      <div>
        <label className="text-xs font-medium" style={{ color: "#787774" }}>Drive</label>
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
          <option value="">Select a drive…</option>
          {drives.data?.drives.map((d: any) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        {drives.isLoading && (
          <p className="text-xs mt-1" style={{ color: "#787774" }}>Loading drives…</p>
        )}
      </div>

      {/* Folder browser */}
      {selectedDrive && (
        <div>
          <label className="text-xs font-medium" style={{ color: "#787774" }}>Folder (optional)</label>
          <div className="mt-1 rounded border text-sm" style={{ borderColor: "#e8e5df" }}>
            {/* Breadcrumb */}
            <div className="flex gap-1 flex-wrap border-b px-3 py-1.5 text-xs" style={{ borderColor: "#e8e5df", color: "#787774" }}>
              <button
                onClick={() => { setParentStack([]); setSelectedFolder("") }}
                className="hover:underline"
              >
                Root
              </button>
              {parentStack.map((p, i) => (
                <span key={p.id} className="flex items-center gap-1">
                  <span>/</span>
                  <button
                    onClick={() => {
                      setParentStack(parentStack.slice(0, i + 1))
                      setSelectedFolder(p.id)
                    }}
                    className="hover:underline"
                  >
                    {p.name}
                  </button>
                </span>
              ))}
            </div>

            {/* Folder list */}
            <div style={{ maxHeight: 180, overflowY: "auto" }}>
              <div
                className={`cursor-pointer px-3 py-1.5 flex items-center gap-2 ${selectedFolder === "" ? "font-medium" : ""}`}
                style={{ backgroundColor: selectedFolder === "" ? "#f7f6f3" : "transparent" }}
                onClick={() => setSelectedFolder("")}
              >
                <span>📁</span>
                <span style={{ color: "#37352f" }}>Use entire drive</span>
              </div>

              {folders.isLoading && (
                <p className="px-3 py-2 text-xs" style={{ color: "#787774" }}>Loading folders…</p>
              )}

              {folders.data?.folders.map((f: any) => (
                <div
                  key={f.id}
                  className={`cursor-pointer px-3 py-1.5 flex items-center justify-between ${selectedFolder === f.id ? "font-medium" : ""}`}
                  style={{ backgroundColor: selectedFolder === f.id ? "#f7f6f3" : "transparent" }}
                  onClick={() => setSelectedFolder(f.id)}
                  onDoubleClick={() => {
                    setParentStack([...parentStack, f])
                    setSelectedFolder(f.id)
                  }}
                >
                  <span className="flex items-center gap-2">
                    <span>📁</span>
                    <span style={{ color: "#37352f" }}>{f.name}</span>
                  </span>
                  <button
                    title="Browse into folder"
                    onClick={(e) => {
                      e.stopPropagation()
                      setParentStack([...parentStack, f])
                    }}
                    className="rounded px-1.5 py-0.5 text-xs hover:bg-gray-100"
                    style={{ color: "#787774" }}
                  >
                    Open →
                  </button>
                </div>
              ))}
            </div>
          </div>
          <p className="text-xs mt-1" style={{ color: "#787774" }}>
            {selectedFolder
              ? `Assets will be stored in the selected folder.`
              : `Assets will be stored at the root of the selected drive.`}
          </p>
        </div>
      )}

      <button
        disabled={!selectedDrive}
        onClick={() => onComplete(selectedDrive, selectedFolder)}
        className="w-full rounded px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        style={{ backgroundColor: "#37352f" }}
      >
        Save Drive Settings
      </button>
    </div>
  )
}
