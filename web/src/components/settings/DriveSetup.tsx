import { useState, useEffect } from "react";
import {
  useDriveStatus,
  useDriveAuthUrl,
  useDriveDrives,
  useDriveFolders,
  useDriveSetup,
} from "@/hooks/queries/use-drive";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";

function CopyableCode({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-2 rounded border border-[#e8e5df] bg-[#f7f6f3] px-3 py-2">
      <span className="flex-1 break-all font-mono text-[13px] text-[#37352f]">
        {value}
      </span>
      <Button
        size="sm"
        variant="outline"
        className="shrink-0 h-7 px-2 text-[12px] border-[#e8e5df] text-[#37352f] hover:bg-[#ebebea]"
        onClick={() => {
          navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }}
      >
        {copied ? "Copied!" : "Copy"}
      </Button>
    </div>
  );
}

function StepBadge({ n }: { n: number }) {
  return (
    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#37352f] text-[12px] font-bold text-white">
      {n}
    </span>
  );
}

export function DriveSetup() {
  const { data: status } = useDriveStatus();
  const authUrl = useDriveAuthUrl();
  const setup = useDriveSetup();

  const [step, setStep] = useState(1);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");

  const redirectUri = `${window.location.origin}/api/internal/drive/callback`;

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === "drive-oauth-complete") {
        setStep(2);
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  // Connected state
  if (status?.connected && step === 1) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-[#4dab9a]" />
          <span className="text-[13px] font-medium text-[#37352f]">
            Google Drive connected
          </span>
        </div>
        {status.drive_id && (
          <p className="text-[12px] text-[#787774]">
            Drive ID: <span className="font-mono">{status.drive_id}</span>
          </p>
        )}
        <button
          onClick={() => setStep(2)}
          className="text-[12px] text-[#787774] hover:text-[#37352f] underline transition-colors"
        >
          Change settings
        </button>
      </div>
    );
  }

  // Step 1: OAuth credentials with setup guide
  if (step === 1) {
    return (
      <div className="space-y-5">
        <div>
          <p className="text-[13px] font-medium text-[#37352f] mb-1">
            Connect Google Drive via OAuth 2.0
          </p>
          <p className="text-[12px] text-[#787774]">
            You need a Google Cloud project with the Drive API enabled. Follow
            the steps below — this is a one-time setup.
          </p>
        </div>

        {/* Step 1 */}
        <div className="flex gap-3">
          <StepBadge n={1} />
          <div className="space-y-1">
            <p className="text-[13px] font-medium text-[#37352f]">Enable Google Drive API</p>
            <p className="text-[12px] text-[#787774]">
              Go to{" "}
              <a
                href="https://console.cloud.google.com/apis/library/drive.googleapis.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#2383e2] hover:underline"
              >
                Google Cloud Console → APIs & Services → Library
              </a>
              , search for <strong>Google Drive API</strong>, and click{" "}
              <strong>Enable</strong>.
            </p>
          </div>
        </div>

        {/* Step 2 */}
        <div className="flex gap-3">
          <StepBadge n={2} />
          <div className="space-y-1">
            <p className="text-[13px] font-medium text-[#37352f]">Configure OAuth Consent Screen</p>
            <p className="text-[12px] text-[#787774]">
              Go to <strong>APIs & Services → OAuth consent screen</strong>.
            </p>
            <ol className="list-decimal list-inside space-y-0.5 text-[12px] text-[#787774]">
              <li>
                User Type: select <strong>External</strong> → Create
              </li>
              <li>
                Fill in App name (e.g. <em>Maestro Local</em>) and your email
              </li>
              <li>Skip Scopes — click Save and Continue</li>
              <li>
                Under <strong>Test users</strong>, add your Google account email
              </li>
              <li>
                Publishing status: leave as <strong>Testing</strong> (no Google review needed)
              </li>
            </ol>
          </div>
        </div>

        {/* Step 3 */}
        <div className="flex gap-3">
          <StepBadge n={3} />
          <div className="space-y-2">
            <p className="text-[13px] font-medium text-[#37352f]">Create OAuth 2.0 Client ID</p>
            <p className="text-[12px] text-[#787774]">
              Go to{" "}
              <strong>
                APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
              </strong>
              .
            </p>
            <ol className="list-decimal list-inside space-y-0.5 text-[12px] text-[#787774]">
              <li>
                Application type: <strong>Web application</strong>
              </li>
              <li>
                Under <strong>Authorized redirect URIs</strong>, click{" "}
                <strong>Add URI</strong> and paste:
              </li>
            </ol>
            <CopyableCode value={redirectUri} />
            <p className="text-[12px] text-[#787774]">
              3. Click <strong>Create</strong> — a dialog will show your Client ID and Client Secret.
            </p>
          </div>
        </div>

        {/* Step 4 */}
        <div className="flex gap-3">
          <StepBadge n={4} />
          <div className="space-y-2 flex-1">
            <p className="text-[13px] font-medium text-[#37352f]">Paste your credentials below</p>
            <p className="text-[12px] text-[#787774]">
              Copy the Client ID and Client Secret from the dialog and paste them here.
            </p>
            <div className="space-y-2">
              <Input
                type="text"
                placeholder="Client ID  (e.g. 123456789-abc…apps.googleusercontent.com)"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                className="bg-white border-[#e8e5df] text-[#37352f] text-[13px] h-[32px]"
              />
              <Input
                type="password"
                placeholder="Client Secret  (e.g. GOCSPX-…)"
                value={clientSecret}
                onChange={(e) => setClientSecret(e.target.value)}
                className="bg-white border-[#e8e5df] text-[#37352f] text-[13px] h-[32px]"
              />
            </div>
          </div>
        </div>

        {/* Connect button */}
        <div className="space-y-2">
          <Button
            disabled={!clientId || !clientSecret || authUrl.isPending}
            onClick={async () => {
              const result = await authUrl.mutateAsync({
                client_id: clientId,
                client_secret: clientSecret,
              });
              window.open(result.auth_url, "_blank", "width=520,height=700");
              setStep(2);
            }}
            className="w-full bg-[#2383e2] hover:bg-[#1a73cc] text-white text-[13px] h-[32px]"
          >
            {authUrl.isPending
              ? "Generating auth URL…"
              : "Connect Google Drive →"}
          </Button>
          <p className="text-[12px] text-[#787774] text-center">
            A Google sign-in window will open. After authorizing, you'll be
            redirected back here.
          </p>
        </div>
      </div>
    );
  }

  // Step 2: Select drive & folder
  return (
    <DriveSelector
      onComplete={(driveId, folderId) => {
        setup.mutate({ drive_id: driveId, root_folder_id: folderId });
        setStep(1);
      }}
    />
  );
}

function DriveSelector({
  onComplete,
}: {
  onComplete: (driveId: string, folderId: string) => void;
}) {
  const [selectedDrive, setSelectedDrive] = useState("");
  const [selectedFolder, setSelectedFolder] = useState("");
  const [parentStack, setParentStack] = useState<
    Array<{ id: string; name: string }>
  >([]);
  const drives = useDriveDrives();
  const currentParent =
    parentStack.length > 0 ? parentStack[parentStack.length - 1].id : "";
  const folders = useDriveFolders({
    drive_id: selectedDrive,
    parent_id: currentParent,
  });

  useEffect(() => {
    drives.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <p className="text-[13px] font-medium text-[#37352f] mb-1">
          Select Drive &amp; Folder
        </p>
        <p className="text-[12px] text-[#787774]">
          Choose where Maestro will store uploaded assets. Double-click a folder
          to browse into it.
        </p>
      </div>

      {/* Drive selector */}
      <div>
        <label className="text-[12px] font-medium text-[#9b9a97]">Drive</label>
        <div className="mt-1">
          <Select
            value={selectedDrive}
            onValueChange={(v) => {
              const driveId = v === "__my_drive__" ? "" : (v as string);
              setSelectedDrive(driveId);
              setParentStack([]);
              setSelectedFolder("");
            }}
          >
            <SelectTrigger className="w-full bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]">
              <SelectValue placeholder="Select a drive…" />
            </SelectTrigger>
            <SelectContent className="bg-white border-[#e8e5df]">
              {drives.data?.drives.map((d: any) => (
                <SelectItem
                  key={d.id}
                  value={d.id || "__my_drive__"}
                  className="text-[13px] text-[#37352f] hover:bg-[#f7f6f3]"
                >
                  {d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {drives.isLoading && (
          <p className="text-[12px] text-[#787774] mt-1">Loading drives…</p>
        )}
      </div>

      {/* Folder browser */}
      {selectedDrive && (
        <div>
          <label className="text-[12px] font-medium text-[#9b9a97]">
            Folder (optional)
          </label>
          <div className="mt-1 rounded border border-[#e8e5df]">
            {/* Breadcrumb */}
            <div className="flex gap-1 flex-wrap border-b border-[#e8e5df] px-3 py-1.5 text-[12px] text-[#787774]">
              <button
                onClick={() => {
                  setParentStack([]);
                  setSelectedFolder("");
                }}
                className="hover:underline"
              >
                Root
              </button>
              {parentStack.map((p, i) => (
                <span key={p.id} className="flex items-center gap-1">
                  <span>/</span>
                  <button
                    onClick={() => {
                      setParentStack(parentStack.slice(0, i + 1));
                      setSelectedFolder(p.id);
                    }}
                    className="hover:underline"
                  >
                    {p.name}
                  </button>
                </span>
              ))}
            </div>

            {/* Folder list */}
            <div className="max-h-[180px] overflow-y-auto">
              <div
                className={`cursor-pointer px-3 py-1.5 flex items-center gap-2 text-[13px] hover:bg-[#f7f6f3] transition-colors ${
                  selectedFolder === "" ? "bg-[#f7f6f3] font-medium" : ""
                }`}
                onClick={() => setSelectedFolder("")}
              >
                <span>📁</span>
                <span className="text-[#37352f]">Use entire drive</span>
              </div>

              {folders.isLoading && (
                <p className="px-3 py-2 text-[12px] text-[#787774]">
                  Loading folders…
                </p>
              )}

              {folders.data?.folders.map((f: any) => (
                <div
                  key={f.id}
                  className={`cursor-pointer px-3 py-1.5 flex items-center justify-between text-[13px] hover:bg-[#f7f6f3] transition-colors ${
                    selectedFolder === f.id ? "bg-[#f7f6f3] font-medium" : ""
                  }`}
                  onClick={() => setSelectedFolder(f.id)}
                  onDoubleClick={() => {
                    setParentStack([...parentStack, f]);
                    setSelectedFolder(f.id);
                  }}
                >
                  <span className="flex items-center gap-2">
                    <span>📁</span>
                    <span className="text-[#37352f]">{f.name}</span>
                  </span>
                  <button
                    title="Browse into folder"
                    onClick={(e) => {
                      e.stopPropagation();
                      setParentStack([...parentStack, f]);
                    }}
                    className="rounded px-1.5 py-0.5 text-[12px] text-[#787774] hover:bg-[#ebebea] transition-colors"
                  >
                    Open →
                  </button>
                </div>
              ))}
            </div>
          </div>
          <p className="text-[12px] text-[#787774] mt-1">
            {selectedFolder
              ? "Assets will be stored in the selected folder."
              : "Assets will be stored at the root of the selected drive."}
          </p>
        </div>
      )}

      <Button
        disabled={!selectedDrive}
        onClick={() => onComplete(selectedDrive, selectedFolder)}
        className="w-full bg-[#2383e2] hover:bg-[#1a73cc] text-white text-[13px] h-[32px]"
      >
        Save Drive Settings
      </Button>
    </div>
  );
}
