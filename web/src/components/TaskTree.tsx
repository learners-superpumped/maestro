import { useNavigate } from "@tanstack/react-router"
import { StatusBadge } from "@/components/StatusBadge"
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
          "flex items-center gap-2 py-1.5 px-2 rounded hover:bg-gray-800/50 cursor-pointer text-sm",
          depth === 0 && "font-medium"
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => navigate({ to: "/tasks/$id", params: { id: node.id } })}
      >
        <StatusBadge status={node.status} />
        <span className="text-gray-50 truncate">{node.title}</span>
        <span className="text-gray-500 text-xs font-mono ml-auto shrink-0">
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
        <p className="text-xs text-gray-500 px-2 pt-2 border-t border-gray-800">
          Total cost: ${total.toFixed(4)}
        </p>
      )}
    </div>
  )
}
