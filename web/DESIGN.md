# Maestro — Design System

## Visual Theme & Atmosphere

Notion-inspired workspace aesthetic. Clean, professional, and content-focused — the interface disappears so users can focus on their tasks and agent outputs. Every surface is deliberately flat with minimal depth cues; structure comes from whitespace and subtle borders rather than shadows or gradients.

- **Ultra-clean white canvas** with warm-toned neutrals (never blue-gray)
- **Content-first hierarchy** — typography and spacing do the heavy lifting, not decoration
- **Minimal chrome** — borders are thin and warm, never heavy or cool-toned
- **Functional color only** — color appears to convey status, never for decoration
- **Compact information density** — 13–14px text, tight spacing, no wasted vertical space

---

## Color Palette & Roles

### Foundation

| Name | Hex | Role |
|------|-----|------|
| **Clean White** | `#ffffff` | Primary background. Cards, dialogs, input fields. |
| **Warm Off-White** | `#f7f6f3` | Secondary background. Hover states, code blocks, collapsible sections, subtle containers. |
| **Soft Hover** | `#ebebea` | Tertiary background. Active/pressed states on interactive elements already on off-white. |

### Borders & Dividers

| Name | Hex | Role |
|------|-----|------|
| **Warm Light Border** | `#e8e5df` | All borders — cards, inputs, dividers, table cells. Single consistent border color throughout. |

### Typography & Text Hierarchy

| Name | Hex | Role |
|------|-----|------|
| **Deep Warm Black** | `#37352f` | Primary text. Headings, body copy, labels, table cell content. |
| **Warm Medium Gray** | `#787774` | Secondary text. Descriptions, expanded details, status badge labels. |
| **Warm Muted Gray** | `#9b9a97` | Tertiary text. Timestamps, metadata labels, placeholders, section headers, disabled elements. |

### Interactive & Accent

| Name | Hex | Role |
|------|-----|------|
| **Notion Blue** | `#2383e2` | Primary actions. Buttons, links, active indicators, focus rings. Hover darkens to `#1a73cc`. |

### Semantic Status Colors

| Name | Hex | Role |
|------|-----|------|
| **Teal Green** | `#4dab9a` | Success. Completed tasks, approved reviews, pass verdicts. Background tint: `#4dab9a/10`. |
| **Warm Red** | `#eb5757` | Error/Danger. Failed tasks, rejected reviews, destructive actions. Background tint: `#eb5757/10`. |
| **Amber Orange** | `#cb912f` | Warning/Pending. Pending tasks, paused states, revision requests. Background tint: `#cb912f/10`. |
| **Muted Purple** | `#9065b0` | Neutral state. Paused badge indicator. Background tint: `#9065b0/10`. |

### Status Color Mapping

```
running      → Notion Blue (#2383e2)
completed    → Teal Green (#4dab9a)
failed       → Warm Red (#eb5757)
pending      → Amber Orange (#cb912f)
paused       → Muted Purple (#9065b0)
cancelled    → Warm Muted Gray (#9b9a97)
approved     → Notion Blue (#2383e2)
claimed      → Amber Orange (#cb912f)
retry_queued → Warm Red (#eb5757)
```

---

## Typography Rules

### Font Stack

System sans-serif optimized for each platform — no web font loading overhead.

```
ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif
```

### Hierarchy & Weights

| Level | Size | Weight | Color | Usage |
|-------|------|--------|-------|-------|
| **Page Title** | 20px | 600 (semibold) | Deep Warm Black | One per page. Task title, section headers. |
| **Card Title** | 16px | 600 (semibold) | Deep Warm Black | Dialog titles, card headers. |
| **Section Title** | 14px | 600 (semibold) | Deep Warm Black | Card subtitles, inline headings. |
| **Section Label** | 12px | 500 (medium) | Warm Muted Gray | Uppercase tracking-wider. Sidebar section headers ("PROPERTIES", "CHILDREN"). |
| **Body Text** | 14px | 400 (normal) | Deep Warm Black | Primary content, descriptions, table cells. Line-height: 1.6. |
| **UI Text** | 13px | 400 (normal) | Deep Warm Black | Buttons, form inputs, select triggers, compact UI elements. |
| **Meta / Caption** | 12px | 400 (normal) | Warm Muted Gray | Timestamps, field labels, status text, badge labels, metadata. |
| **Code / Mono** | 13px | 400 (normal) | Warm Medium Gray | IDs, costs, technical values. Font: system monospace. |

### Minimum Size

Never go below **12px** for any visible text. This is a hard floor.

---

## Component Stylings

### Buttons

- **Primary**: `bg-[#2383e2]` text white, hover `bg-[#1a73cc]`. Height 28–32px, text 13px, rounded, px-3.
- **Ghost/Secondary**: No background, text `#787774`, hover `bg-[#f7f6f3]`. Same dimensions.
- **Destructive ghost**: No background, text `#eb5757`, hover `bg-red-50`.
- All buttons use `cursor-pointer`. No shadows. No borders on primary buttons.

### Cards & Containers

- Background: Clean White (`#ffffff`).
- Border: 1px solid Warm Light Border (`#e8e5df`).
- Border radius: 4px (`rounded`). Never pill-shaped.
- No box shadows. Depth comes from border alone.
- Padding: 16px (CardContent default).

### Status Badges

- Small colored dot (8×8px, `rounded-full`) + label text in Warm Medium Gray.
- Running status: dot has `animate-ping` pulse effect.
- No background pill — just dot and text inline.

### Inputs & Forms

- Height: 32px. Text: 13px.
- Background: Clean White. Border: Warm Light Border.
- Placeholder text: Warm Muted Gray.
- Focus ring: Notion Blue.

### Dialogs

- Background: Clean White. Border: Warm Light Border.
- Max width: `max-w-lg` (32rem).
- Title: 16px semibold. Labels: 12px Warm Muted Gray.

### Collapsible Sections

- Border: 1px solid Warm Light Border, rounded.
- Toggle button: full-width, 13px medium text in Warm Medium Gray, hover `bg-[#f7f6f3]`.
- Chevron icon (ChevronDown/ChevronRight) as open/close indicator.
- Content area: separated by top border, padded.

### Activity Timeline

- Vertical line connector: 1px Warm Light Border. Stops at last event.
- Event icons: 20×20px circle with tinted background (status color at 10% opacity) + colored icon.
- Label: 13px medium Deep Warm Black. Actor: 12px Warm Muted Gray.
- Time: 12px Warm Muted Gray, relative format ("3m ago", "2h ago").
- Collapsed by default beyond 5 events, with "Show N more" link in Notion Blue.

### Markdown Prose

- Applied via `.prose` class. Max-width: none (fills container).
- Tables: full-width, collapsed borders, Warm Light Border cells, header row in Warm Off-White.
- Code inline: 13px, Warm Red text, Warm Off-White background, 3px radius.
- Code blocks: Warm Off-White background, Warm Light Border, 4px radius, 12px padding.
- Links: Notion Blue, underline on hover only.

---

## Layout Principles

### Grid & Structure

- **Task Detail (desktop)**: Two-column flex layout at `lg` breakpoint (1024px+).
  - Main column: `flex-1 min-w-0` — primary content (agent log, result, instruction).
  - Sidebar: `320px` fixed width — properties, children, activity.
  - Gap: 20px between columns.
- **Task Detail (mobile)**: Single column stack, sidebar content flows below main.
- **Task List**: Full width with filter bar. List or Board (kanban) view toggle.

### Whitespace Strategy

- **Base unit**: 4px (Tailwind default).
- **Section gap**: 20px (`space-y-5`) for major sections, 16px (`space-y-4`) within columns.
- **Component internal gap**: 12px (`space-y-3`) for form fields, 8px (`space-y-2`) for list items.
- **Edge padding**: Handled by parent layout — page content never adds its own horizontal padding.

### Responsive Behavior

- Breakpoint: `lg` (1024px) — two-column ↔ single-column.
- No horizontal scrolling. Tables use `overflow-x-auto`.
- Touch targets: minimum 28px height for buttons, 32px for inputs.
- All interactive cards have `cursor-pointer` and hover state.

---

## Design System Rules for Code Generation

### Color References

Always use descriptive name + hex in conversation. In code, use hex directly in Tailwind arbitrary values:

```
✅  text-[#37352f]   bg-[#f7f6f3]   border-[#e8e5df]
❌  text-gray-900    bg-gray-50      border-gray-200
```

Tailwind's default gray scale is **not used** — all grays are warm-toned Notion values.

### Forbidden Patterns

- No `box-shadow` on cards or containers — use border only.
- No gradient backgrounds.
- No rounded-full buttons (pills) — use `rounded` (4px).
- No text below 12px.
- No colors outside the defined palette — verify hex values against this document.
- No emoji as UI icons — use Lucide React icon set exclusively.

### Animation

- Entry animation: `fade-in-up` (opacity 0→1, translateY 4px→0, 300ms ease-out).
- Hover transitions: `transition-colors` (150ms default).
- Loading: `Loader2` icon with `animate-spin`.
- Running status: `animate-ping` on status dot.
- Respect `prefers-reduced-motion`.

### Icon Set

Lucide React exclusively. Common icons:

```
Navigation: ArrowLeft, ChevronDown, ChevronUp, ChevronRight
Actions:    Plus, Check, X, Play, RefreshCw, PenLine
Status:     AlertTriangle, CheckCircle2, XCircle, Eye, Loader2
```
