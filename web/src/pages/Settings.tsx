import { SlackSetup } from "@/components/settings/SlackSetup"
import { DriveSetup } from "@/components/settings/DriveSetup"

export function Settings() {
  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-[24px] font-semibold text-[#37352f] mb-6">Settings</h1>
      <SlackSetup />
      <div className="rounded-lg border p-6 mt-6" style={{ borderColor: "#e8e5df" }}>
        <h2 className="mb-4 text-lg font-semibold" style={{ color: "#37352f" }}>
          Google Drive
        </h2>
        <DriveSetup />
      </div>
    </div>
  )
}
