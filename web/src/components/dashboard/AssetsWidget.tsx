import { useNavigate } from "@tanstack/react-router"
import { File, Image, BarChart2, FileText } from "lucide-react"

interface Asset {
  id: string
  title?: string
  name?: string
  asset_type?: string
  type?: string
}

function AssetIcon({ type }: { type?: string }) {
  const t = (type || "").toLowerCase()
  if (t.includes("image") || t.includes("photo")) return <Image className="h-4 w-4 text-[#9b9a97]" />
  if (t.includes("chart") || t.includes("data")) return <BarChart2 className="h-4 w-4 text-[#9b9a97]" />
  if (t.includes("text") || t.includes("doc")) return <FileText className="h-4 w-4 text-[#9b9a97]" />
  return <File className="h-4 w-4 text-[#9b9a97]" />
}

interface Props {
  assets: Asset[]
  driveConnected: boolean
  loading: boolean
}

export function AssetsWidget({ assets, driveConnected, loading }: Props) {
  const navigate = useNavigate()
  const shown = assets.slice(0, 4)

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
            Recent Assets
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: driveConnected ? "#4dab9a" : "#9b9a97" }}
          />
          <span className="text-[10px] text-[#9b9a97]">
            {driveConnected ? "Drive connected" : "Drive disconnected"} · {assets.length} files
          </span>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-4 gap-1.5">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="aspect-square rounded bg-[#f7f6f3] animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-1.5">
          {shown.map((asset) => (
            <button
              key={asset.id}
              onClick={() => navigate({ to: "/assets" })}
              className="aspect-square rounded bg-[#f7f6f3] flex items-center justify-center hover:bg-[#ebebea] transition-colors"
              title={asset.title || asset.name || asset.asset_type || asset.type}
            >
              <AssetIcon type={asset.asset_type || asset.type} />
            </button>
          ))}
          {shown.length === 0 && (
            <div className="col-span-4 py-2 text-[12px] text-[#9b9a97] px-1">에셋 없음</div>
          )}
        </div>
      )}
    </div>
  )
}
