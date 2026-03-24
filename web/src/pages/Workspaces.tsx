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
import { Badge } from "@/components/ui/badge"
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
          <h1 className="text-xl font-semibold text-gray-50">Workspaces</h1>
          <p className="text-sm text-gray-400 mt-1">
            {data != null
              ? `${workspaces.length} workspace${workspaces.length !== 1 ? "s" : ""}`
              : ""}
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="bg-indigo-600 hover:bg-indigo-500 text-white">
                <Plus className="h-4 w-4 mr-1" />
                New Workspace
              </Button>
            }
          />
          <DialogContent className="bg-gray-900 border-gray-800 text-gray-50 max-w-sm">
            <DialogHeader>
              <DialogTitle>New Workspace</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="space-y-1">
                <Label className="text-gray-400 text-xs">Name *</Label>
                <Input
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value)
                    setNameError("")
                  }}
                  className="bg-gray-800 border-gray-700 text-gray-50"
                  placeholder="my-workspace"
                />
                {nameError && (
                  <p className="text-xs text-red-400">{nameError}</p>
                )}
              </div>
              <div className="space-y-1">
                <Label className="text-gray-400 text-xs">Template</Label>
                <Input
                  value={template}
                  onChange={(e) => setTemplate(e.target.value)}
                  className="bg-gray-800 border-gray-700 text-gray-50"
                  placeholder="default"
                />
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
                  className="text-gray-400"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={createWorkspace.isPending}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white"
                >
                  {createWorkspace.isPending && (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  )}
                  Create
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-lg border border-gray-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-800 hover:bg-transparent">
              <TableHead className="text-gray-400 text-xs">Name</TableHead>
              <TableHead className="text-gray-400 text-xs">Status</TableHead>
              <TableHead className="text-gray-400 text-xs">Warnings</TableHead>
              <TableHead className="text-gray-400 text-xs w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i} className="border-gray-800">
                    {Array.from({ length: 4 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-gray-800" />
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
                    <TableRow key={ws.name} className="border-gray-800 hover:bg-gray-800/30">
                      <TableCell className="text-gray-50 text-sm font-medium">
                        <div className="flex items-center gap-2">
                          <FolderOpen className="h-4 w-4 text-gray-500" />
                          {ws.name}
                        </div>
                      </TableCell>
                      <TableCell>
                        {hasWarnings ? (
                          <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/30 border">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            warnings
                          </Badge>
                        ) : (
                          <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 border">
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            valid
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-gray-400 text-xs max-w-xs truncate">
                        {warningsText || "—"}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => validateWorkspace.mutate(ws.name)}
                          disabled={validateWorkspace.isPending}
                          className="h-7 w-7 text-gray-500 hover:text-indigo-400"
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
              <TableRow className="border-gray-800">
                <TableCell colSpan={4} className="text-center text-gray-500 py-8">
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
