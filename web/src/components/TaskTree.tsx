import { useNavigate } from "@tanstack/react-router"
import { StatusIcon } from "@/components/StatusIcon"
import { cn } from "@/lib/utils"

interface TreeNode {
  id: string
  title: string
  status: string
  type: string
  cost_usd?: number
  children?: TreeNode[]
}

function TreeItem({ node, depth = 0 }: { node: TreeNode; depth?: number }) {
  const navigate = useNavigate()
  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-2 py-1.5 px-2 rounded hover:bg-[#f7f6f3] cursor-pointer",
          depth === 0 && "font-medium"
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => navigate({ to: "/tasks/$id", params: { id: node.id } })}
      >
        <StatusIcon status={node.status} />
        <span className="text-[14px] text-[#37352f] truncate">{node.title}</span>
        <span className="text-[12px] text-[#9b9a97] font-mono ml-auto shrink-0">
          {node.cost_usd != null ? `$${Number(node.cost_usd).toFixed(4)}` : ""}
        </span>
      </div>
      {node.children?.map((child) => (
        <TreeItem key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  )
}

export function TaskTree({ tree }: { tree: TreeNode }) {
  function totalCost(node: TreeNode): number {
    const own = Number(node.cost_usd ?? 0)
    const childCost = (node.children ?? []).reduce((sum, c) => sum + totalCost(c), 0)
    return own + childCost
  }
  const total = totalCost(tree)
  return (
    <div className="space-y-2">
      <TreeItem node={tree} />
      {total > 0 && (
        <p className="text-[12px] text-[#9b9a97] px-2 pt-2 border-t border-[#e8e5df]">
          Total cost: ${total.toFixed(4)}
        </p>
      )}
    </div>
  )
}
