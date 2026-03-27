interface Props {
  weekSpend: number[]
  todaySpend: number
}

export function SpendChart({ weekSpend, todaySpend }: Props) {
  const total = weekSpend.reduce((a, b) => a + b, 0)
  const max = Math.max(...weekSpend, 0.0001) // avoid div-by-zero
  const days = ["M", "T", "W", "T", "F", "S", "S"]

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
          Spend This Week
        </span>
      </div>

      <div className="px-1">
        <div className="text-[20px] font-semibold text-[#37352f]">
          ${total.toFixed(4)}
        </div>
        <div className="text-[11px] text-[#9b9a97] mb-2">
          7-day total · today ${todaySpend.toFixed(4)}
        </div>

        {/* Mini bar chart */}
        <div className="flex items-end gap-[3px] h-8">
          {weekSpend.map((val, i) => {
            const isToday = i === weekSpend.length - 1
            const heightPct = max > 0 ? (val / max) * 100 : 0
            return (
              <div
                key={i}
                className="flex-1 rounded-sm"
                style={{
                  height: `${Math.max(heightPct, 4)}%`,
                  backgroundColor: isToday ? "#2383e2" : "#ebebea",
                }}
                title={`${days[i]}: $${val.toFixed(4)}`}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}
