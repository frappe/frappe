# Designing Studio pages

How a Studio page should LOOK, distilled from the design language of shipping
Frappe apps (Gameplan, CRM, Helpdesk, Drive, Insights). Vocabulary here is
Studio blocks: camelCase `style` properties and `var(--*)` espresso tokens —
the Tailwind/Vue original lives in the frappe-ui skill
(`frappe-ui/skills/frappe-ui/DESIGN.md`, `TOKENS.md`). This file is also baked
into Studio's AI prompts (`studio/ai/prompts.py`), so every agent — runtime or
CLI — designs from the same source of truth. When unsure how something should
look, copy a shipping Frappe app; don't invent.

## Principles

1. **Gray first.** Ink-gray text on `var(--surface-base)`; color appears only
   where it encodes information. The primary button is `variant: solid` with
   the default gray theme.
2. **Hierarchy through ink, not boxes.** Differentiate with the ink ladder and
   type scale, and separate stacked content with hairline dividers — not by
   wrapping everything in bordered cards. A border must earn its place: an
   interactive affordance, an overlay, a genuinely distinct surface.
3. **One primary action per screen**, usually in the page header. Everything
   else is `subtle` or `ghost`.
4. **Dense but breathable.** 13–14px body text, 40–60px list rows, 48px page
   headers, generous bottom padding on scrollable areas.
5. **Alignment over flow.** Repeating trailing elements (badges, timestamps,
   counts) get fixed-width, right-aligned columns — not ragged flex rows.
6. **Icons support labels, never replace them.** Icon-only buttons only for
   universal actions (close, overflow "…"). Decorative icons are noise.
7. **At most one accent per screen** — a single status dot in a gray list, not
   a palette.

## Hierarchy — the ink ladder

Pick text color by ROLE, not by eye:

| Token | Role |
|---|---|
| `var(--ink-gray-9)` | strongest values: unread titles, KPI figures, page default |
| `var(--ink-gray-8)` | headings, titles, primary content |
| `var(--ink-gray-7)` | secondary values, table cells, descriptions |
| `var(--ink-gray-6)` | field labels, form icons |
| `var(--ink-gray-5)` | timestamps, counts, captions, meta |
| `var(--ink-gray-4)` | record ids, decorative glyphs |

Type by role (TextBlock `fontSize`): page title `text-2xl`/`text-3xl` with
`fontWeight: "600"`; section heading `text-lg` + 600; card/panel title
`text-xl`; one-line labels and row titles `text-base`; meta `text-sm` in
`var(--ink-gray-5)`. Multi-line copy uses the `text-p-*` family (relaxed
line-height), headings and labels the tight `text-*` family. **Never
uppercase headings or labels** — Frappe UIs are sentence case ("Recent
activity"); a quiet section label is `text-sm` + `var(--ink-gray-5)`, not
capitals.

## Surfaces & borders

- Page background `var(--surface-base)`. Subtle fills and hover surfaces
  `var(--surface-gray-1)` / `var(--surface-gray-2)`; board/kanban columns
  `var(--surface-gray-1)` with cards on `var(--surface-elevation-1)`.
- Stacked rows separate with a bottom hairline per row:
  `borderWidth: "0px 0px 1px 0px"`, `borderColor: "var(--outline-gray-1)"`,
  `borderStyle: "solid"` — the Frappe look is divided lists, not grids of
  boxed cards.
- When a card IS warranted: `var(--surface-base)` + 1px
  `var(--outline-gray-1)` border, or a tinted surface with no border — not
  both heavy. borderRadius: cards/panels `0.5rem`–`0.625rem`, dialogs
  `0.75rem`, full-bleed sections none. boxShadow rarely — overlays, not
  resting cards.

## Color discipline

Everything is gray unless the color MEANS something:

- Status/priority: a Badge with `variant: subtle` and a theme mapped from the
  value (open → blue, done → green, error → red, everything else gray) — one
  mapping per page, applied consistently.
- Sign: negative `var(--ink-red-6)`, positive `var(--ink-green-6)`. Severity:
  red/amber/green inks, never backgrounds.
- Unread/attention: a single small dot (8px circle, `var(--surface-blue-7)` or
  amber) — not a row highlight.
- Tinted banners (`var(--surface-red-1)`, `--surface-amber-1`, …) only for
  page-level notices; prefer the Alert component.

## Geometry & rhythm

- Page header: 48px (`minHeight: "48px"`), title left, the screen's one solid
  Button right. Horizontal gutters 20px desktop / 12px mobile — the SAME pair
  on header, body, and full-width rows so edges align.
- Content width: reading/detail pages `maxWidth: "940px"` centered; prose
  `770px`; dashboards `896px`; dense tables may run full-width.
- Spacing scale: sections stack with `gap: "24px"`; form fields `16px`;
  related meta `12px`; inline actions `8px`; sidebar nav items `2px`. Page
  body starts with `paddingTop: "20px"`; scrollable bodies end with
  `paddingBottom: "40px"` or more.
- Row heights: 40px dense tables, 44–60px medium lists, ~60px feeds. Pick one
  mechanism per list and keep every row identical.

## Screen archetypes

- **App shell**: Sidebar (14rem, `header` + grouped nav items with lucide
  icons) beside a main column (`flex: "1"`, `flexDirection: "column"`); the
  main column is header row + scrollable body. Never nest a second sidebar.
- **List page**: header (title + primary Button) → ListView, or a Repeater of
  divider-separated rows: leading title `text-base` `ink-gray-8`, meta line
  `text-sm` `ink-gray-5`, trailing Badge/timestamp in a fixed-width right
  column.
- **Dashboard**: centered `896px` column, `gap: "24px"`; a KPI strip of
  NumberCharts separated by hairlines (not four boxed cards); charts below,
  each with a `text-lg` 600 heading.
- **Form page**: ONE centered column `maxWidth: "576px"`, `gap: "16px"`; every
  field a FormControl WITH a `label` (placeholder is never the label); footer
  actions right-aligned `gap: "8px"` — ghost/subtle Cancel, then solid Save.
- **Detail + meta panel**: content column (`flex: "1"`) plus a right panel
  `width: "320px"` with a left hairline, holding label/value rows (label
  `text-sm` `ink-gray-6`, value `text-base` `ink-gray-8`).
- **Empty state** (any list/dashboard with no data): centered column,
  `padding: "64px 0px"`, `gap: "12px"` — an icon in a `var(--surface-gray-2)`
  circle (`padding: "12px"`, `borderRadius: "9999px"`, icon `ink-gray-5`), a
  `text-base` `ink-gray-7` title, a `text-sm` `ink-gray-5` caption, and one
  solid CTA. Never render a bare "No data" string.

## Mobile (`mstyle`)

A systematic translation, not a second design: columns stack
(`flexDirection: "column"`), side/meta panels collapse below content, rows get
taller and titles one step bigger (`text-base` → `text-lg`), action clusters
collapse into one Dropdown, gutters drop to 12px. Same data on both — trim
fields, don't fork the layout.
