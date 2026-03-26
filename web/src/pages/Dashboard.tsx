import { useStats } from "@/hooks/queries/use-stats"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Activity, CheckCircle2, DollarSign, ListTodo, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

interface StatCardProps {
  title: string
  value: string | number | undefined
  icon: React.ElementType
  iconColor: string
  loading: boolean
}

function StatCard({ title, value, icon: Icon, iconColor, loading }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">{title}</CardTitle>
        <Icon className={cn("h-4 w-4", iconColor)} />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24 bg-[#f7f6f3]" />
        ) : (
          <div className="text-[24px] font-semibold text-[#37352f]">
            {value ?? "—"}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function Dashboard() {
  const { data, isLoading } = useStats()

  const todaySpend =
    data?.today_spend_usd != null
      ? `$${Number(data.today_spend_usd).toFixed(4)}`
      : "—"

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[20px] font-semibold text-[#37352f]">Dashboard</h1>
        <p className="text-[14px] text-[#787774] mt-1">
          Overview of your Maestro agents
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Running Tasks"
          value={data?.running}
          icon={Activity}
          iconColor="text-[#2383e2]"
          loading={isLoading}
        />
        <StatCard
          title="Pending Approvals"
          value={data?.pending_approvals}
          icon={AlertTriangle}
          iconColor="text-[#cb912f]"
          loading={isLoading}
        />
        <StatCard
          title="Today's Spend"
          value={todaySpend}
          icon={DollarSign}
          iconColor="text-[#4dab9a]"
          loading={isLoading}
        />
        <StatCard
          title="Total Tasks"
          value={data?.total_tasks}
          icon={ListTodo}
          iconColor="text-[#9065b0]"
          loading={isLoading}
        />
      </div>

      {/* Status breakdown */}
      {(isLoading || data?.status_counts) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Status Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-5 w-full bg-[#f7f6f3]" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {Object.entries(data?.status_counts ?? {}).map(
                  ([status, count]) => (
                    <div
                      key={status}
                      className="flex items-center justify-between px-3 py-2 bg-[#f7f6f3] rounded"
                    >
                      <span className="text-[12px] text-[#787774] capitalize">
                        {status.replace("_", " ")}
                      </span>
                      <span className="text-[14px] font-semibold text-[#37352f]">
                        {count as number}
                      </span>
                    </div>
                  )
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Date */}
      {data?.date && (
        <p className="text-[12px] text-[#9b9a97]">
          Stats as of {data.date}
        </p>
      )}
    </div>
  )
}
