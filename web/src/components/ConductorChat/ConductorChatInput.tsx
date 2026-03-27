import { useState, useRef, useCallback } from "react"
import { ArrowUp } from "lucide-react"
import { cn } from "@/lib/utils"

interface ConductorChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
}

export function ConductorChatInput({ onSend, disabled }: ConductorChatInputProps) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue("")
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }, [value, disabled, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (el) {
      el.style.height = "auto"
      el.style.height = Math.min(el.scrollHeight, 120) + "px"
    }
  }

  const canSend = value.trim().length > 0 && !disabled

  return (
    <div className="border-t border-[#e8e5df] p-3 bg-white">
      <div className="flex items-end gap-2 rounded-lg border border-[#e8e5df] bg-[#f7f6f3] px-3 py-2 focus-within:border-[#2383e2] focus-within:ring-1 focus-within:ring-[#2383e2]/30 transition-colors">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            handleInput()
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="지시를 입력하세요..."
          rows={1}
          className={cn(
            "flex-1 resize-none bg-transparent text-[14px] text-[#37352f]",
            "placeholder:text-[#9b9a97] outline-none",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "max-h-[120px]"
          )}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={cn(
            "shrink-0 h-6 w-6 flex items-center justify-center rounded transition-colors",
            canSend
              ? "bg-[#37352f] text-white hover:bg-[#2383e2]"
              : "text-[#9b9a97] cursor-default"
          )}
        >
          <ArrowUp className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
