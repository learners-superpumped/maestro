import { Activity, AlertTriangle, DollarSign, List } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface KpiCardProps {
  title: string
  value: string | number | undefined
  subText: string
  icon: React.ElementType
  iconColor: string
  valueColor?: string
  badge?: string
  badgeColor?: string
  loading: boolean
}

function KpiCard({
  title,
  value,
  subText,
  icon: Icon,
  iconColor,
  valueColor,
  badge,
  badgeColor,
  loading,
}: KpiCardProps) {
  return (
    <div className="flex-1 px-5 py-4 flex items-center gap-3 border-r border-[#e8e5df] last:border-r-0">
      <Icon className={cn("h-4 w-4 shrink-0", iconColor)} />
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-[#9b9a97] font-medium">{title}</div>
        {loading ? (
          <Skeleton className="h-6 w-16 bg-[#f7f6f3] mt-0.5" />
        ) : (
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className={cn("text-[20px] font-semibold text-[#37352f]", valueColor)}>
              {value ?? "—"}
            </span>
            {badge && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                style={{ color: badgeColor, backgroundColor: `${badgeColor}18` }}
              >
                {badge}
              </span>
            )}
          </div>
        )}
        <div className="text-[11px] text-[#9b9a97] mt-0.5">{subText}</div>
      </div>
    </div>
  )
}

interface DashboardKpiRowProps {
  stats: any
  loading: boolean
}

export function DashboardKpiRow({ stats, loading }: DashboardKpiRowProps) {
  const todaySpend =
    stats?.today_spend_usd != null
      ? `$${Number(stats.today_spend_usd).toFixed(4)}`
      : "—"

  return (
    <div className="flex border border-[#e8e5df] rounded bg-white overflow-hidden">
      <KpiCard
        title="Running"
        value={stats?.running}
        subText="agents active"
        icon={Activity}
        iconColor="text-[#f2994a]"
        valueColor="text-[#f2994a]"
        loading={loading}
      />
      <KpiCard
        title="Pending Approval"
        value={stats?.pending_approvals}
        subText=""
        icon={AlertTriangle}
        iconColor="text-[#cb912f]"
        badge={stats?.pending_approvals > 0 ? "action needed" : undefined}
        badgeColor="#cb912f"
        loading={loading}
      />
      <KpiCard
        title="Today's Spend"
        value={todaySpend}
        subText="today"
        icon={DollarSign}
        iconColor="text-[#4dab9a]"
        loading={loading}
      />
      <KpiCard
        title="Total Tasks"
        value={stats?.total_tasks}
        subText="all time"
        icon={List}
        iconColor="text-[#9065b0]"
        loading={loading}
      />
    </div>
  )
}
