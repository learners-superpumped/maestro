import { Fragment, useState } from "react"
import { useNavigate } from "@tanstack/react-router"
import { useTaskChildren } from "@/hooks/queries/use-tasks"
import { StatusBadge } from "@/components/StatusBadge"
import { TaskTypeBadge } from "@/components/TaskTypeBadge"
import { ProgressIndicator } from "@/components/ProgressIndicator"
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

  if (isLoading) {
    return (
      <TableRow className="border-b border-[#e8e5df]">
        <TableCell colSpan={7}>
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
            className="border-b border-[#e8e5df] hover:bg-[#f7f6f3] cursor-pointer h-[36px]"
            onClick={() => navigate({ to: "/tasks/$id", params: { id: child.id } })}
          >
            <TableCell>
              <StatusBadge status={child.status} />
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
              </div>
            </TableCell>
            <TableCell><TaskTypeBadge type={child.type} /></TableCell>
            <TableCell className="text-[14px] text-[#787774]">{child.workspace}</TableCell>
            <TableCell />
            <TableCell className="text-[13px] font-mono text-[#787774]">
              {child.cost_usd != null ? `$${Number(child.cost_usd).toFixed(4)}` : "—"}
            </TableCell>
            <TableCell className="text-[12px] text-[#9b9a97]">
              {child.updated_at ? new Date(child.updated_at).toLocaleString() : "—"}
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

  return (
    <div className="border border-[#e8e5df] rounded overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="border-b border-[#e8e5df] hover:bg-transparent">
            <TableHead className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97] w-24">Status</TableHead>
            <TableHead className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97]">Title</TableHead>
            <TableHead className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97]">Type</TableHead>
            <TableHead className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97]">Workspace</TableHead>
            <TableHead className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97] w-16">Progress</TableHead>
            <TableHead className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97]">Cost</TableHead>
            <TableHead className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97]">Updated</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={i} className="border-b border-[#e8e5df]">
                {Array.from({ length: 7 }).map((_, j) => (
                  <TableCell key={j}><Skeleton className="h-4 bg-[#f7f6f3]" /></TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            tasks.map((task: any) => {
              const hasChildren = task.children_summary?.total > 0
              return (
                <Fragment key={task.id}>
                  <TableRow
                    className="border-b border-[#e8e5df] hover:bg-[#f7f6f3] cursor-pointer h-[36px]"
                    onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
                  >
                    <TableCell><StatusBadge status={task.status} /></TableCell>
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
                      </div>
                    </TableCell>
                    <TableCell><TaskTypeBadge type={task.type} /></TableCell>
                    <TableCell className="text-[14px] text-[#787774]">{task.workspace}</TableCell>
                    <TableCell>
                      {task.children_summary && (
                        <ProgressIndicator total={task.children_summary.total} completed={task.children_summary.completed} />
                      )}
                    </TableCell>
                    <TableCell className="text-[13px] font-mono text-[#787774]">
                      {task.cost_usd != null ? `$${Number(task.cost_usd).toFixed(4)}` : "—"}
                    </TableCell>
                    <TableCell className="text-[12px] text-[#9b9a97]">
                      {task.updated_at ? new Date(task.updated_at).toLocaleString() : "—"}
                    </TableCell>
                  </TableRow>
                  {expanded[task.id] && hasChildren && <ChildRows parentId={task.id} depth={1} />}
                </Fragment>
              )
            })
          )}
          {!isLoading && tasks.length === 0 && (
            <TableRow className="border-b border-[#e8e5df]">
              <TableCell colSpan={7} className="text-center text-[14px] text-[#9b9a97] py-8">No tasks found</TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
