import { Fragment, useState, useEffect } from "react"
import { useNavigate } from "@tanstack/react-router"
import { useTaskChildren } from "@/hooks/queries/use-tasks"
import { StatusIcon } from "@/components/StatusIcon"
import { PriorityIcon } from "@/components/PriorityIcon"
import { formatTaskTime } from "@/lib/time"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { ChevronRight, ChevronDown } from "lucide-react"

interface TaskListTreeProps {
  tasks: any[]
  isLoading: boolean
}

function ChildRows({ parentId, depth }: { parentId: string; depth: number }) {
  const { data, isLoading } = useTaskChildren(parentId)
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const children: any[] = data?.children ?? []
  const [, setTick] = useState(0)

  const hasRunning = children.some((c: any) => c.status === "running")

  useEffect(() => {
    if (!hasRunning) return
    const id = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [hasRunning])

  if (isLoading) {
    return (
      <TableRow className="border-b border-[#f0efed]">
        <TableCell colSpan={5}>
          <div style={{ paddingLeft: `${depth * 24}px` }}>
            <Skeleton className="h-4 w-48 bg-[#f7f6f3]" />
          </div>
        </TableCell>
      </TableRow>
    )
  }

  return (
    <>
      {children.map((child: any) => (
        <Fragment key={child.id}>
          <TableRow
            className="border-b border-[#f0efed] hover:bg-[#f7f6f3] cursor-pointer h-[36px]"
            onClick={() => navigate({ to: "/tasks/$id", params: { id: child.id } })}
          >
            <TableCell className="w-[24px] px-2">
              <StatusIcon status={child.status} size={14} />
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1" style={{ paddingLeft: `${depth * 24}px` }}>
                {depth < 2 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setExpanded((prev) => ({ ...prev, [child.id]: !prev[child.id] }))
                    }}
                    className="text-[#9b9a97] hover:text-[#37352f] w-5 h-5 flex items-center justify-center"
                  >
                    {expanded[child.id] ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  </button>
                )}
                <span className="text-[14px] text-[#787774] truncate">{child.title}</span>
                {child.depends_on_tasks && child.depends_on_tasks.length > 0 && (
                  <span className="text-[12px] text-[#cb912f] shrink-0" title={child.depends_on_tasks.map((d: any) => d.title).join(", ")}>
                    ← {child.depends_on_tasks.length} step{child.depends_on_tasks.length > 1 ? "s" : ""}
                  </span>
                )}
              </div>
            </TableCell>
            <TableCell className="w-[40px] px-2">
              {child.priority != null && <PriorityIcon priority={child.priority} size={14} />}
            </TableCell>
            <TableCell className="w-[80px] text-[12px] text-[#9b9a97] tabular-nums">
              {formatTaskTime(child)}
            </TableCell>
            <TableCell className="w-[80px] text-right text-[13px] font-mono text-[#787774]">
              {child.cost_usd != null ? `$${Number(child.cost_usd).toFixed(2)}` : "—"}
            </TableCell>
          </TableRow>
          {expanded[child.id] && depth < 2 && <ChildRows parentId={child.id} depth={depth + 1} />}
        </Fragment>
      ))}
    </>
  )
}

export function TaskListTree({ tasks, isLoading }: TaskListTreeProps) {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [, setTick] = useState(0)

  const hasRunning = tasks.some((t: any) => (t.effective_status ?? t.status) === "running")

  useEffect(() => {
    if (!hasRunning) return
    const id = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [hasRunning])

  return (
    <div className="border border-[#f0efed] rounded overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="border-b border-[#f0efed] hover:bg-transparent">
            <TableHead className="text-[12px] font-medium text-[#9b9a97] w-[24px] px-2">Status</TableHead>
            <TableHead className="text-[12px] font-medium text-[#9b9a97]">Title</TableHead>
            <TableHead className="text-[12px] font-medium text-[#9b9a97] w-[40px] px-2">Priority</TableHead>
            <TableHead className="text-[12px] font-medium text-[#9b9a97] w-[80px]">Time</TableHead>
            <TableHead className="text-[12px] font-medium text-[#9b9a97] w-[80px] text-right">Cost</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={i} className="border-b border-[#f0efed]">
                {Array.from({ length: 5 }).map((_, j) => (
                  <TableCell key={j}><Skeleton className="h-4 bg-[#f7f6f3]" /></TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            tasks.map((task: any) => {
              const hasChildren = task.children_summary?.total > 0
              const status = task.effective_status ?? task.status
              return (
                <Fragment key={task.id}>
                  <TableRow
                    className="border-b border-[#f0efed] hover:bg-[#f7f6f3] cursor-pointer h-[36px]"
                    onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
                  >
                    <TableCell className="w-[24px] px-2">
                      <StatusIcon status={status} size={14} />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {hasChildren && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setExpanded((prev) => ({ ...prev, [task.id]: !prev[task.id] }))
                            }}
                            className="text-[#9b9a97] hover:text-[#37352f] w-5 h-5 flex items-center justify-center"
                          >
                            {expanded[task.id] ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                          </button>
                        )}
                        <span className="text-[14px] text-[#37352f] truncate max-w-xs">{task.title}</span>
                        {task.depends_on_tasks && task.depends_on_tasks.length > 0 && (
                          <span className="text-[12px] text-[#cb912f] shrink-0" title={task.depends_on_tasks.map((d: any) => d.title).join(", ")}>
                            ← {task.depends_on_tasks.length} step{task.depends_on_tasks.length > 1 ? "s" : ""}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="w-[40px] px-2">
                      {task.priority != null && <PriorityIcon priority={task.priority} size={14} />}
                    </TableCell>
                    <TableCell className="w-[80px] text-[12px] text-[#9b9a97] tabular-nums">
                      {formatTaskTime(task)}
                    </TableCell>
                    <TableCell className="w-[80px] text-right text-[13px] font-mono text-[#787774]">
                      {task.cost_usd != null ? `$${Number(task.cost_usd).toFixed(2)}` : "—"}
                    </TableCell>
                  </TableRow>
                  {expanded[task.id] && hasChildren && <ChildRows parentId={task.id} depth={1} />}
                </Fragment>
              )
            })
          )}
          {!isLoading && tasks.length === 0 && (
            <TableRow className="border-b border-[#f0efed]">
              <TableCell colSpan={5} className="text-center text-[14px] text-[#9b9a97] py-8">No tasks found</TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
