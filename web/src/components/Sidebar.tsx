import { Link, useRouterState } from "@tanstack/react-router"
import {
  LayoutDashboard,
  ListTodo,
  Package,
  Clock,
  GitBranch,
  FolderOpen,
  Target,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", to: "/" },
  { icon: ListTodo, label: "Tasks", to: "/tasks" },
  { icon: Package, label: "Assets", to: "/assets" },
  { icon: Clock, label: "Schedules", to: "/schedules" },
  { icon: GitBranch, label: "Rules", to: "/rules" },
  { icon: Target, label: "Goals", to: "/goals" },
  { icon: FolderOpen, label: "Workspaces", to: "/workspaces" },
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
        "flex flex-col h-full bg-[#f7f6f3] border-r border-[#e8e5df] transition-all duration-200",
        collapsed ? "w-[44px]" : "w-[240px]"
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-11 px-2 border-b border-[#e8e5df]">
        {!collapsed && (
          <span className="text-[14px] font-semibold text-[#37352f] truncate flex-1 px-1">
            Maestro
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className={cn(
            "h-7 w-7 text-[#9b9a97] hover:text-[#37352f] hover:bg-[#ebebea] rounded shrink-0",
            collapsed ? "mx-auto" : "ml-auto"
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
      <nav className="flex-1 p-2 space-y-0.5">
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
                "flex items-center gap-2 px-2 py-1 rounded h-[30px] text-[14px] transition-colors",
                isActive
                  ? "bg-[#ebebea] text-[#37352f]"
                  : "text-[#787774] hover:bg-[#ebebea] hover:text-[#37352f]"
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
