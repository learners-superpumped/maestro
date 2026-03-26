const PRIORITY_CONFIG: Record<number, { bars: number; color: string }> = {
  1: { bars: 3, color: "#eb5757" },
  2: { bars: 3, color: "#f2994a" },
  3: { bars: 2, color: "#9b9a97" },
  4: { bars: 1, color: "#9b9a97" },
  5: { bars: 1, color: "#9b9a97" },
}

export function PriorityIcon({ priority, size = 14 }: { priority: number; size?: number }) {
  const config = PRIORITY_CONFIG[priority] ?? PRIORITY_CONFIG[3]
  const barWidth = size * 0.2
  const gap = size * 0.08
  const totalWidth = 3 * barWidth + 2 * gap
  const startX = (size - totalWidth) / 2

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
      {[0, 1, 2].map((i) => (
        <rect
          key={i}
          x={startX + i * (barWidth + gap)}
          y={size * 0.2}
          width={barWidth}
          height={size * 0.6}
          rx={1}
          fill={config.color}
          opacity={i < config.bars ? 1 : 0.2}
        />
      ))}
    </svg>
  )
}
