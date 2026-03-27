import { useState } from "react"
import { useQuery, useMutation } from "@tanstack/react-query"
import { api } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"

export function SlackSetup() {
  const [step, setStep] = useState(1)
  const [botToken, setBotToken] = useState("")
  const [appToken, setAppToken] = useState("")
  const [channel, setChannel] = useState("")
  const [copied, setCopied] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean } | null>(null)
  const [setupError, setSetupError] = useState<string | null>(null)

  const statusQuery = useQuery({
    queryKey: ["slack-status"],
    queryFn: () => api.slack.status(),
  })

  const manifestQuery = useQuery({
    queryKey: ["slack-manifest"],
    queryFn: () => api.slack.manifest(),
    enabled: step === 1,
  })

  const setupMutation = useMutation({
    mutationFn: (data: { bot_token: string; app_token: string; channel: string }) =>
      api.slack.setup(data),
    onSuccess: () => {
      setStep(3)
      setSetupError(null)
      statusQuery.refetch()
    },
    onError: (err: Error) => {
      setSetupError(err.message)
    },
  })

  const testMutation = useMutation({
    mutationFn: () => api.slack.test(),
    onSuccess: (data) => {
      setTestResult(data)
    },
    onError: () => {
      setTestResult({ ok: false })
    },
  })

  const handleCopyManifest = () => {
    const manifestText = JSON.stringify(manifestQuery.data, null, 2)
    navigator.clipboard.writeText(manifestText).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleSetup = () => {
    setSetupError(null)
    setupMutation.mutate({ bot_token: botToken, app_token: appToken, channel })
  }

  // Already connected — show status
  if (statusQuery.data?.connected) {
    return (
      <Card className="p-4 border border-[#e8e5df] bg-white rounded-lg">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-[14px] font-semibold text-[#37352f] mb-1">Slack Integration</h2>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
              <span className="text-[13px] text-[#37352f]">Connected</span>
            </div>
            {statusQuery.data.channel && (
              <p className="text-[12px] text-[#787774]">
                Channel: <span className="font-mono">{statusQuery.data.channel}</span>
              </p>
            )}
          </div>
          <Button
            size="sm"
            variant="outline"
            className="text-[13px] border-[#e8e5df] text-[#37352f] hover:bg-[#f7f6f3]"
            onClick={() => testMutation.mutate()}
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? "Testing…" : "Send Test Message"}
          </Button>
        </div>
        {testResult !== null && (
          <p
            className={`mt-3 text-[13px] ${testResult.ok ? "text-green-700" : "text-red-600"}`}
          >
            {testResult.ok ? "Test message sent successfully." : "Test failed. Check your Slack configuration."}
          </p>
        )}
      </Card>
    )
  }

  return (
    <Card className="p-4 border border-[#e8e5df] bg-white rounded-lg">
      <h2 className="text-[14px] font-semibold text-[#37352f] mb-1">Slack Integration</h2>
      <p className="text-[13px] text-[#787774] mb-4">
        Connect Maestro to Slack to receive notifications and interact via chat.
      </p>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-5">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`flex items-center justify-center w-6 h-6 rounded-full text-[12px] font-medium transition-colors ${
                s === step
                  ? "bg-[#37352f] text-white"
                  : s < step
                  ? "bg-[#ebebea] text-[#37352f]"
                  : "bg-[#f7f6f3] text-[#9b9a97] border border-[#e8e5df]"
              }`}
            >
              {s < step ? "✓" : s}
            </div>
            {s < 3 && <div className="w-8 h-px bg-[#e8e5df]" />}
          </div>
        ))}
      </div>

      {/* Step 1: Manifest */}
      {step === 1 && (
        <div>
          <p className="text-[13px] text-[#37352f] font-medium mb-2">Create a Slack App</p>
          <ol className="text-[12px] text-[#787774] mb-3 space-y-1 list-decimal list-inside">
            <li>
              Go to{" "}
              <a
                href="https://api.slack.com/apps"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                api.slack.com/apps
              </a>
              {" "}and click <strong>"Create New App"</strong>
            </li>
            <li>Select <strong>"From a manifest"</strong> and choose your workspace</li>
            <li>Copy the JSON below and paste it into the manifest field</li>
            <li>Click <strong>"Create"</strong> to finish</li>
          </ol>
          <div className="relative mb-3">
            <pre className="bg-[#f7f6f3] border border-[#e8e5df] rounded p-3 text-[12px] text-[#37352f] overflow-auto max-h-64 font-mono whitespace-pre-wrap">
              {manifestQuery.isLoading
                ? "Loading manifest…"
                : manifestQuery.error
                ? "Failed to load manifest."
                : JSON.stringify(manifestQuery.data, null, 2)}
            </pre>
            <Button
              size="sm"
              variant="outline"
              className="absolute top-2 right-2 text-[12px] border-[#e8e5df] text-[#37352f] hover:bg-[#ebebea] h-7 px-2"
              onClick={handleCopyManifest}
              disabled={!manifestQuery.data}
            >
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>
          <div className="flex justify-end">
            <Button
              size="sm"
              className="bg-[#37352f] hover:bg-[#2f2e2b] text-white text-[13px]"
              onClick={() => setStep(2)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: Token inputs */}
      {step === 2 && (
        <div>
          <p className="text-[13px] text-[#37352f] font-medium mb-1">Enter your tokens</p>
          <p className="text-[11px] text-[#9b9a97] mb-3">
            Copy these tokens from the Slack App you just created.
          </p>
          <div className="space-y-3 mb-4">
            <div>
              <label className="block text-[12px] text-[#787774] mb-1">Bot Token</label>
              <Input
                placeholder="xoxb-…"
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
                className="text-[13px] border-[#e8e5df] focus:border-[#37352f] h-8"
              />
              <p className="text-[11px] text-[#9b9a97] mt-1">
                Install App → install, then OAuth & Permissions → Bot User OAuth Token
              </p>
            </div>
            <div>
              <label className="block text-[12px] text-[#787774] mb-1">App-Level Token</label>
              <Input
                placeholder="xapp-…"
                value={appToken}
                onChange={(e) => setAppToken(e.target.value)}
                className="text-[13px] border-[#e8e5df] focus:border-[#37352f] h-8"
              />
              <p className="text-[11px] text-[#9b9a97] mt-1">
                Basic Information → App-Level Tokens → Generate Token (scope: connections:write)
              </p>
            </div>
            <div>
              <label className="block text-[12px] text-[#787774] mb-1">Default Channel</label>
              <Input
                placeholder="#general"
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="text-[13px] border-[#e8e5df] focus:border-[#37352f] h-8"
              />
              <p className="text-[11px] text-[#9b9a97] mt-1">
                The channel to receive notifications (the bot must be invited to this channel)
              </p>
            </div>
          </div>
          {setupError && (
            <p className="text-[12px] text-red-600 mb-3">{setupError}</p>
          )}
          <div className="flex items-center justify-between">
            <Button
              size="sm"
              variant="outline"
              className="text-[13px] border-[#e8e5df] text-[#787774] hover:bg-[#f7f6f3]"
              onClick={() => setStep(1)}
            >
              Back
            </Button>
            <Button
              size="sm"
              className="bg-[#37352f] hover:bg-[#2f2e2b] text-white text-[13px]"
              onClick={handleSetup}
              disabled={
                !botToken || !appToken || !channel || setupMutation.isPending
              }
            >
              {setupMutation.isPending ? "Saving…" : "Save & Connect"}
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Test */}
      {step === 3 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
            <p className="text-[13px] text-[#37352f] font-medium">Connected successfully!</p>
          </div>
          <p className="text-[13px] text-[#787774] mb-4">
            Send a test message to verify everything is working.
          </p>
          <Button
            size="sm"
            variant="outline"
            className="text-[13px] border-[#e8e5df] text-[#37352f] hover:bg-[#f7f6f3] mb-3"
            onClick={() => testMutation.mutate()}
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? "Testing…" : "Send Test Message"}
          </Button>
          {testResult !== null && (
            <p
              className={`text-[13px] ${testResult.ok ? "text-green-700" : "text-red-600"}`}
            >
              {testResult.ok
                ? "Test message sent successfully."
                : "Test failed. Check your configuration and try again."}
            </p>
          )}
          <div className="mt-4 pt-3 border-t border-[#e8e5df]">
            <p className="text-[12px] text-[#787774] font-medium mb-1">Next steps</p>
            <ul className="text-[11px] text-[#9b9a97] space-y-0.5 list-disc list-inside">
              <li>Restart the daemon to activate Slack integration</li>
              <li>Mention <strong>@YourBot</strong> in a channel or send a DM to start chatting</li>
              <li>Task notifications and approval requests will appear in your configured channel</li>
            </ul>
          </div>
        </div>
      )}
    </Card>
  )
}
