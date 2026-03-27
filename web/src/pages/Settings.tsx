import { SlackSetup } from "@/components/settings/SlackSetup"

export function Settings() {
  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-[24px] font-semibold text-[#37352f] mb-6">Settings</h1>
      <SlackSetup />
    </div>
  )
}
