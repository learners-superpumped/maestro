import { useState } from "react"
import { Outlet } from "@tanstack/react-router"
import { Sidebar } from "./Sidebar"
import { useWebSocket } from "@/hooks/use-websocket"
import { Wifi, WifiOff, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"

function WsIndicator() {
  const status = useWebSocket()

  if (status === "connected") {
    return (
      <div className="flex items-center gap-1.5 text-green-500 text-xs">
        <Wifi className="h-3 w-3" />
        <span className="hidden sm:inline">Live</span>
      </div>
    )
  }
  if (status === "connecting") {
    return (
      <div className="flex items-center gap-1.5 text-amber-500 text-xs">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span className="hidden sm:inline">Connecting</span>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1.5 text-gray-500 text-xs">
      <WifiOff className="h-3 w-3" />
      <span className="hidden sm:inline">Offline</span>
    </div>
  )
}

export function Layout() {
  const [collapsed, setCollapsed] = useState(false)

  const { isError: healthError } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 30_000,
    retry: false,
  })

  return (
    <div className="flex h-screen bg-gray-950 text-gray-50 overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-end gap-3 h-14 px-4 border-b border-gray-800 bg-gray-900 shrink-0">
          <span className={cn(
            "inline-flex items-center gap-1.5 text-xs",
            healthError ? "text-red-400" : "text-green-400"
          )}>
            <span className={cn(
              "h-1.5 w-1.5 rounded-full",
              healthError ? "bg-red-400" : "bg-green-400"
            )} />
            {healthError ? "Server offline" : "Server online"}
          </span>
          <WsIndicator />
        </header>

        {/* Page content */}
        <main
          className={cn(
            "flex-1 overflow-auto p-6"
          )}
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
