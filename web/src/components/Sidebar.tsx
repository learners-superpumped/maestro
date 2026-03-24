import { Link, useRouterState } from "@tanstack/react-router"
import {
  LayoutDashboard,
  ListTodo,
  Package,
  Clock,
  GitBranch,
  ClipboardCheck,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", to: "/" },
  { icon: ClipboardCheck, label: "Approvals", to: "/approvals" },
  { icon: ListTodo, label: "Tasks", to: "/tasks" },
  { icon: Package, label: "Assets", to: "/assets" },
  { icon: Clock, label: "Schedules", to: "/schedules" },
  { icon: GitBranch, label: "Rules", to: "/rules" },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const routerState = useRouterState()
  const currentPath = routerState.location.pathname

  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-gray-900 border-r border-gray-800 transition-all duration-200",
        collapsed ? "w-14" : "w-52"
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-3 border-b border-gray-800">
        {!collapsed && (
          <span className="text-gray-50 font-semibold text-sm tracking-wide truncate">
            Maestro
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className={cn(
            "ml-auto h-7 w-7 text-gray-400 hover:text-gray-50 hover:bg-gray-800",
            collapsed && "mx-auto"
          )}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map(({ icon: Icon, label, to }) => {
          const isActive =
            to === "/"
              ? currentPath === "/"
              : currentPath.startsWith(to)
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex items-center gap-3 px-2 py-2 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-500/20 text-indigo-400"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-50"
              )}
              title={collapsed ? label : undefined}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{label}</span>}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
