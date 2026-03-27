import { createContext, useContext } from "react"

interface ConductorPanelContextType {
  openConversation: (conversationId?: string) => void
}

export const ConductorPanelContext = createContext<ConductorPanelContextType>({
  openConversation: () => {},
})

export function useConductorPanel() {
  return useContext(ConductorPanelContext)
}
