import { SlackSetup } from "@/components/settings/SlackSetup"
import { DriveSetup } from "@/components/settings/DriveSetup"

export function Settings() {
  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <h1 className="text-[20px] font-semibold text-[#37352f]">Settings</h1>
        <p className="text-[14px] text-[#787774] mt-1">Integrations & configuration</p>
      </div>
      <SlackSetup />
      <div className="rounded-lg border p-6" style={{ borderColor: "#e8e5df" }}>
        <h2 className="mb-4 text-lg font-semibold" style={{ color: "#37352f" }}>
          Google Drive
        </h2>
        <DriveSetup />
      </div>
    </div>
  )
}
