import { SlackSetup } from "@/components/settings/SlackSetup"
import { DriveSetup } from "@/components/settings/DriveSetup"
import { Card } from "@/components/ui/card"

export function Settings() {
  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <h1 className="text-[20px] font-semibold text-[#37352f]">Settings</h1>
        <p className="text-[14px] text-[#787774] mt-1">Integrations & configuration</p>
      </div>
      <SlackSetup />
      <Card className="p-4 border border-[#e8e5df] bg-white rounded-lg">
        <h2 className="text-[14px] font-semibold text-[#37352f] mb-1">Google Drive</h2>
        <p className="text-[13px] text-[#787774] mb-4">
          Connect Google Drive to store and manage assets.
        </p>
        <DriveSetup />
      </Card>
    </div>
  )
}
