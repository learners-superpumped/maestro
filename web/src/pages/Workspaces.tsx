import { useState } from "react"
import { Plus, Loader2, CheckCircle2, AlertTriangle, RefreshCw, FolderOpen } from "lucide-react"
import {
  useWorkspaces,
  useCreateWorkspace,
  useValidateWorkspace,
} from "@/hooks/queries/use-workspaces"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"

const namePattern = /^[a-zA-Z0-9_-]+$/

const WORKSPACE_TEMPLATES = [
  { value: "default", label: "Default" },
  { value: "sns", label: "SNS" },
  { value: "content", label: "Content" },
  { value: "research", label: "Research" },
]

export function Workspaces() {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [template, setTemplate] = useState("default")
  const [nameError, setNameError] = useState("")

  const { data, isLoading } = useWorkspaces()
  const createWorkspace = useCreateWorkspace()
  const validateWorkspace = useValidateWorkspace()

  const workspaces: any[] = data?.workspaces ?? (Array.isArray(data) ? data : [])

  const handleCreate = async () => {
    if (!name.trim()) {
      setNameError("Name is required")
      return
    }
    if (!namePattern.test(name)) {
      setNameError("Only alphanumeric characters, hyphens, and underscores allowed")
      return
    }
    setNameError("")
    await createWorkspace.mutateAsync({ name, template: template || "default" })
    setName("")
    setTemplate("default")
    setOpen(false)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-[#37352f]">Workspaces</h1>
          <p className="text-[14px] text-[#787774] mt-1">
            {data != null
              ? `${workspaces.length} workspace${workspaces.length !== 1 ? "s" : ""}`
              : ""}
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3">
                <Plus className="h-3.5 w-3.5 mr-1" />
                New Workspace
              </Button>
            }
          />
          <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-sm">
            <DialogHeader>
              <DialogTitle className="text-[16px] font-semibold text-[#37352f]">New Workspace</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Name *</Label>
                <Input
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value)
                    setNameError("")
                  }}
                  className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                  placeholder="my-workspace"
                />
                {nameError && (
                  <p className="text-[12px] text-[#eb5757]">{nameError}</p>
                )}
              </div>
              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Template</Label>
                <Select value={template} onValueChange={setTemplate}>
                  <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded">
                    <SelectValue placeholder="Select template" />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-[#e8e5df]">
                    {WORKSPACE_TEMPLATES.map((t) => (
                      <SelectItem key={t.value} value={t.value} className="text-[#37352f] text-[13px] hover:bg-[#f7f6f3]">
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setOpen(false)
                    setName("")
                    setTemplate("default")
                    setNameError("")
                  }}
                  className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3]"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={createWorkspace.isPending}
                  className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3"
                >
                  {createWorkspace.isPending && (
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  )}
                  Create
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded border border-[#e8e5df] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Name</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Status</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Warnings</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i} className="border-[#e8e5df]">
                    {Array.from({ length: 4 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-[#f7f6f3]" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : workspaces.map((ws: any) => {
                  const hasWarnings =
                    ws.warnings != null &&
                    (Array.isArray(ws.warnings)
                      ? ws.warnings.length > 0
                      : ws.warnings !== "")
                  const warningsText = Array.isArray(ws.warnings)
                    ? ws.warnings.join(", ")
                    : (ws.warnings ?? "")
                  return (
                    <TableRow key={ws.name} className="border-b border-[#e8e5df] hover:bg-[#f7f6f3]">
                      <TableCell className="text-[#37352f] text-[14px] font-medium">
                        <div className="flex items-center gap-2">
                          <FolderOpen className="h-4 w-4 text-[#9b9a97]" />
                          {ws.name}
                        </div>
                      </TableCell>
                      <TableCell>
                        {hasWarnings ? (
                          <span className="inline-flex items-center gap-1 text-[12px] bg-[#f7f6f3] text-[#cb912f] border border-[#e8e5df] rounded px-1.5 py-0.5">
                            <AlertTriangle className="h-3 w-3" />
                            warnings
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[12px] bg-[#f7f6f3] text-[#4dab9a] border border-[#e8e5df] rounded px-1.5 py-0.5">
                            <CheckCircle2 className="h-3 w-3" />
                            valid
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-[12px] text-[#9b9a97] max-w-xs truncate">
                        {warningsText || "—"}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => validateWorkspace.mutate(ws.name)}
                          disabled={validateWorkspace.isPending}
                          className="h-7 w-7 text-[#9b9a97] hover:text-[#2383e2] hover:bg-[#f7f6f3]"
                          title="Re-validate"
                        >
                          {validateWorkspace.isPending ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <RefreshCw className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
            {!isLoading && workspaces.length === 0 && (
              <TableRow className="border-[#e8e5df]">
                <TableCell colSpan={4} className="text-center text-[14px] text-[#9b9a97] py-8">
                  No workspaces found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
