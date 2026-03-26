import {
  createRouter,
  createRoute,
  createRootRoute,
  RouterProvider,
  redirect,
} from "@tanstack/react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "@/components/ui/sonner"
import { Layout } from "@/components/Layout"
import { Dashboard } from "@/pages/Dashboard"
import { Tasks } from "@/pages/Tasks"
import { TaskDetail } from "@/pages/TaskDetail"
import { Assets } from "@/pages/Assets"
import { Schedules } from "@/pages/Schedules"
import { Rules } from "@/pages/Rules"
import { Goals } from "@/pages/Goals"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5_000,
    },
  },
})

const rootRoute = createRootRoute({
  component: Layout,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Dashboard,
})

const tasksRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/tasks",
  component: Tasks,
})

const taskDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/tasks/$id",
  component: TaskDetail,
})

const assetsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/assets",
  component: Assets,
})

const schedulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/schedules",
  component: Schedules,
})

const rulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/rules",
  component: Rules,
})

const approvalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/approvals",
  beforeLoad: () => {
    throw redirect({ to: "/tasks" })
  },
  component: () => null,
})

const goalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/goals",
  component: Goals,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  tasksRoute,
  taskDetailRoute,
  assetsRoute,
  schedulesRoute,
  rulesRoute,
  approvalsRoute,
  goalsRoute,
])

const router = createRouter({ routeTree })

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster richColors />
    </QueryClientProvider>
  )
}
