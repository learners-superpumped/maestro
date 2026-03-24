const BASE = ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

function buildQuery(params?: Record<string, string | undefined>): string {
  if (!params) return ""
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") q.set(k, v)
  }
  const s = q.toString()
  return s ? `?${s}` : ""
}

export const api = {
  stats: () => request<any>("/api/internal/stats"),

  tasks: {
    list: (params?: { status?: string; workspace?: string }) =>
      request<any>(`/api/internal/tasks${buildQuery(params)}`),
    get: (id: string) => request<any>(`/api/internal/task/${id}`),
    create: (data: any) =>
      request<any>("/api/internal/task", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    children: (id: string) => request<any>(`/api/internal/task/${id}/children`),
    approve: (id: string) =>
      request<any>(`/api/internal/task/${id}/approve`, { method: "POST" }),
    reject: (id: string, note?: string) =>
      request<any>(`/api/internal/task/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ note }),
      }),
    revise: (id: string, note: string) =>
      request<any>(`/api/internal/task/${id}/revise`, {
        method: "POST",
        body: JSON.stringify({ note }),
      }),
  },

  assets: {
    list: (params?: { type?: string; workspace?: string; tags?: string }) =>
      request<any>(`/api/internal/assets${buildQuery(params)}`),
    get: (id: string) => request<any>(`/api/internal/asset/${id}`),
    register: (data: any) =>
      request<any>("/api/internal/asset/register", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<any>(`/api/internal/asset/${id}`, { method: "DELETE" }),
    archive: (id: string) =>
      request<any>(`/api/internal/asset/${id}/archive`, { method: "POST" }),
    cleanup: (graceDays: number) =>
      request<any>("/api/internal/assets/cleanup", {
        method: "POST",
        body: JSON.stringify({ grace_days: graceDays }),
      }),
  },

  schedules: {
    list: () => request<any>("/api/internal/schedules"),
    create: (data: any) =>
      request<any>("/api/internal/schedule", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (name: string) =>
      request<any>(`/api/internal/schedule/${name}`, { method: "DELETE" }),
    enable: (name: string) =>
      request<any>(`/api/internal/schedule/${name}/enable`, { method: "POST" }),
    disable: (name: string) =>
      request<any>(`/api/internal/schedule/${name}/disable`, {
        method: "POST",
      }),
  },

  rules: {
    list: (params?: { workspace?: string }) =>
      request<any>(`/api/internal/rules${buildQuery(params)}`),
    create: (data: any) =>
      request<any>("/api/internal/rule", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (workspace: string, taskType: string) =>
      request<any>(`/api/internal/rule/${workspace}/${taskType}`, {
        method: "DELETE",
      }),
  },

  approvals: {
    pending: () => request<any>("/api/internal/approvals/pending"),
  },
}
