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

function TaskRow({
  task,
  depth,
  expanded,
  onToggle,
  onClick,
}: {
  task: any
  depth: number
  expanded: boolean
  onToggle: () => void
  onClick: () => void
}) {
  const hasChildren = task.children_summary?.total > 0
  const status = task.effective_status ?? task.status
  const indent = depth * 20

  return (
    <TableRow
      className="border-b border-[#f0efed] hover:bg-[#f7f6f3] cursor-pointer h-[36px]"
      onClick={onClick}
    >
      {/* Status + Title in one cell for proper indentation */}
      <TableCell>
        <div className="flex items-center" style={{ paddingLeft: `${indent}px` }}>
          {/* Chevron — only if has children, otherwise spacer */}
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onToggle()
              }}
              className="text-[#9b9a97] hover:text-[#37352f] w-5 h-5 flex items-center justify-center shrink-0"
            >
              {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            </button>
          ) : (
            <span className="w-5 shrink-0" />
          )}
          <StatusIcon status={status} size={14} />
          {task.task_number != null && (
            <span className="text-[12px] text-[#9b9a97] font-mono ml-2 shrink-0">
              MAE-{task.task_number}
            </span>
          )}
          <span className={`text-[13px] truncate ml-1.5 ${depth === 0 ? "text-[#37352f]" : "text-[#787774]"}`}>
            {task.title}
          </span>
          {task.depends_on_tasks && task.depends_on_tasks.length > 0 && (
            <span
              className="text-[11px] text-[#cb912f] shrink-0 ml-2"
              title={task.depends_on_tasks.map((d: any) => d.title).join(", ")}
            >
              ← {task.depends_on_tasks.length}
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
      <TableCell className="w-[80px] text-right text-[13px] font-mono text-[#9b9a97]">
        {task.cost_usd != null ? `$${Number(task.cost_usd).toFixed(2)}` : "—"}
      </TableCell>
    </TableRow>
  )
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
        <TableCell colSpan={4}>
          <div style={{ paddingLeft: `${depth * 20 + 20}px` }}>
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
          <TaskRow
            task={child}
            depth={depth}
            expanded={!!expanded[child.id]}
            onToggle={() => setExpanded((prev) => ({ ...prev, [child.id]: !prev[child.id] }))}
            onClick={() => navigate({ to: "/tasks/$id", params: { id: child.id } })}
          />
          {expanded[child.id] && child.children_summary?.total > 0 && depth < 2 && (
            <ChildRows parentId={child.id} depth={depth + 1} />
          )}
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
    <div className="border border-[#e8e5df] rounded overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="border-b border-[#e8e5df] hover:bg-transparent">
            <TableHead className="text-[12px] font-medium text-[#9b9a97]">Task</TableHead>
            <TableHead className="text-[12px] font-medium text-[#9b9a97] w-[40px] px-2">Priority</TableHead>
            <TableHead className="text-[12px] font-medium text-[#9b9a97] w-[80px]">Time</TableHead>
            <TableHead className="text-[12px] font-medium text-[#9b9a97] w-[80px] text-right">Cost</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={i} className="border-b border-[#f0efed]">
                {Array.from({ length: 4 }).map((_, j) => (
                  <TableCell key={j}><Skeleton className="h-4 bg-[#f7f6f3]" /></TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            tasks.map((task: any) => (
              <Fragment key={task.id}>
                <TaskRow
                  task={task}
                  depth={0}
                  expanded={!!expanded[task.id]}
                  onToggle={() => setExpanded((prev) => ({ ...prev, [task.id]: !prev[task.id] }))}
                  onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
                />
                {expanded[task.id] && task.children_summary?.total > 0 && (
                  <ChildRows parentId={task.id} depth={1} />
                )}
              </Fragment>
            ))
          )}
          {!isLoading && tasks.length === 0 && (
            <TableRow className="border-b border-[#f0efed]">
              <TableCell colSpan={4} className="text-center text-[13px] text-[#9b9a97] py-8">No tasks found</TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
