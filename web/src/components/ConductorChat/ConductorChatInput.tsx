import { useState, useRef, useCallback } from "react"
import { Send } from "lucide-react"
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

  return (
    <div className="flex items-end gap-2 border-t border-[#e8e5df] p-3 bg-white">
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
          "flex-1 resize-none rounded-lg border border-[#e8e5df] bg-[#f7f6f3] px-3 py-2 text-[14px] text-[#37352f]",
          "placeholder:text-[#9b9a97] outline-none focus:border-[#2383e2] focus:ring-1 focus:ring-[#2383e2]/30",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          "max-h-[120px]"
        )}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        className={cn(
          "shrink-0 h-9 w-9 flex items-center justify-center rounded-lg transition-colors",
          value.trim() && !disabled
            ? "bg-[#2383e2] text-white hover:bg-[#1b6ec2]"
            : "bg-[#e8e5df] text-[#9b9a97] cursor-not-allowed"
        )}
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  )
}
