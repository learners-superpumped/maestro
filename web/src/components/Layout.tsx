import { useState } from "react"
import { Outlet } from "@tanstack/react-router"
import { Sidebar } from "./Sidebar"
import { ConductorChatPanel } from "./ConductorChat"
import { useWebSocket } from "@/hooks/use-websocket"
import { Wifi, WifiOff, Loader2, MessageSquare } from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"

function WsIndicator() {
  const status = useWebSocket()

  if (status === "connected") {
    return (
      <div className="flex items-center gap-1.5 text-[12px] text-[#4dab9a]">
        <Wifi className="h-3 w-3" />
        <span className="hidden sm:inline">Live</span>
      </div>
    )
  }
  if (status === "connecting") {
    return (
      <div className="flex items-center gap-1.5 text-[12px] text-[#cb912f]">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span className="hidden sm:inline">Connecting</span>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1.5 text-[12px] text-[#9b9a97]">
      <WifiOff className="h-3 w-3" />
      <span className="hidden sm:inline">Offline</span>
    </div>
  )
}

export function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  const { isError: healthError } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 30_000,
    retry: false,
  })

  return (
    <div className="flex h-screen bg-white text-[#37352f] overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />

      <div className={cn(
        "flex flex-col flex-1 min-w-0 overflow-hidden transition-all duration-200",
        chatOpen && "mr-[400px]"
      )}>
        {/* Top bar */}
        <header className="flex items-center justify-end gap-3 h-11 px-4 border-b border-[#e8e5df] bg-white shrink-0">
          {/* Status indicators */}
          <div className="flex items-center gap-2.5">
            <span className={cn(
              "inline-flex items-center gap-1.5 text-[12px]",
              healthError ? "text-[#eb5757]" : "text-[#4dab9a]"
            )}>
              <span className={cn(
                "h-1.5 w-1.5 rounded-full",
                healthError ? "bg-[#eb5757]" : "bg-[#4dab9a]"
              )} />
              {healthError ? "Offline" : "Online"}
            </span>
            <WsIndicator />
          </div>

          {/* Separator */}
          <div className="h-4 w-px bg-[#e8e5df]" />

          {/* Action icons */}
          <button
            onClick={() => setChatOpen((o) => !o)}
            className={cn(
              "h-7 w-7 flex items-center justify-center rounded hover:bg-[#ebebea] transition-colors",
              chatOpen ? "text-[#2383e2]" : "text-[#9b9a97] hover:text-[#37352f]"
            )}
            title="Conductor"
          >
            <MessageSquare className="h-4 w-4" />
          </button>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6 bg-white">
          <Outlet />
        </main>
      </div>

      {/* Conductor Chat Panel */}
      <ConductorChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  )
}
