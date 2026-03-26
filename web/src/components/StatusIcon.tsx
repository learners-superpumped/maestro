const STATUS_CONFIG: Record<string, { color: string; icon: "empty" | "half" | "check" | "x" | "pause" | "user" }> = {
  pending:      { color: "#9b9a97", icon: "empty" },
  running:      { color: "#f2994a", icon: "half" },
  paused:       { color: "#cb912f", icon: "pause" },
  completed:    { color: "#4dab9a", icon: "check" },
  failed:       { color: "#eb5757", icon: "x" },
  cancelled:    { color: "#eb5757", icon: "x" },
  approved:     { color: "#2383e2", icon: "check" },
  claimed:      { color: "#2383e2", icon: "user" },
  retry_queued: { color: "#f2994a", icon: "half" },
}

export function StatusIcon({ status, size = 14 }: { status: string; size?: number }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending
  const r = size / 2 - 1
  const cx = size / 2
  const cy = size / 2

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
      {config.icon === "empty" && (
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={config.color} strokeWidth={1.5} />
      )}
      {config.icon === "half" && (
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={config.color} strokeWidth={1.5}
          strokeDasharray={`${Math.PI * r} ${Math.PI * r}`}
          className="animate-spin"
          style={{ transformOrigin: "center", animationDuration: "2s" }}
        />
      )}
      {config.icon === "check" && (
        <>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={config.color} strokeWidth={1.5} />
          <path
            d={`M${size * 0.3} ${cy} l${size * 0.13} ${size * 0.13} l${size * 0.24} -${size * 0.24}`}
            fill="none" stroke={config.color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"
          />
        </>
      )}
      {config.icon === "x" && (
        <>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={config.color} strokeWidth={1.5} />
          <path
            d={`M${size * 0.35} ${size * 0.35} l${size * 0.3} ${size * 0.3} M${size * 0.65} ${size * 0.35} l-${size * 0.3} ${size * 0.3}`}
            fill="none" stroke={config.color} strokeWidth={1.5} strokeLinecap="round"
          />
        </>
      )}
      {config.icon === "pause" && (
        <>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={config.color} strokeWidth={1.5} />
          <line x1={size * 0.38} y1={size * 0.35} x2={size * 0.38} y2={size * 0.65} stroke={config.color} strokeWidth={1.5} strokeLinecap="round" />
          <line x1={size * 0.62} y1={size * 0.35} x2={size * 0.62} y2={size * 0.65} stroke={config.color} strokeWidth={1.5} strokeLinecap="round" />
        </>
      )}
      {config.icon === "user" && (
        <>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={config.color} strokeWidth={1.5} />
          <circle cx={cx} cy={size * 0.38} r={size * 0.1} fill={config.color} />
          <path d={`M${size * 0.3} ${size * 0.72} a${size * 0.2} ${size * 0.18} 0 0 1 ${size * 0.4} 0`} fill={config.color} />
        </>
      )}
    </svg>
  )
}
