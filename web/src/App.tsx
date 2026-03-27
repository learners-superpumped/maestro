import { lazy, Suspense } from "react"
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

const Dashboard = lazy(() =>
  import("@/pages/Dashboard").then((m) => ({ default: m.Dashboard }))
)
const Tasks = lazy(() =>
  import("@/pages/Tasks").then((m) => ({ default: m.Tasks }))
)
const TaskDetail = lazy(() =>
  import("@/pages/TaskDetail").then((m) => ({ default: m.TaskDetail }))
)
const Assets = lazy(() =>
  import("@/pages/Assets").then((m) => ({ default: m.Assets }))
)
const Schedules = lazy(() =>
  import("@/pages/Schedules").then((m) => ({ default: m.Schedules }))
)
const Rules = lazy(() =>
  import("@/pages/Rules").then((m) => ({ default: m.Rules }))
)
const Goals = lazy(() =>
  import("@/pages/Goals").then((m) => ({ default: m.Goals }))
)
const Settings = lazy(() =>
  import("@/pages/Settings").then((m) => ({ default: m.Settings }))
)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5_000,
    },
  },
})

function RootComponent() {
  return (
    <Suspense>
      <Layout />
    </Suspense>
  )
}

const rootRoute = createRootRoute({
  component: RootComponent,
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

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: Settings,
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
  settingsRoute,
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
