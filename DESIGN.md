# Local Knowledge Studio — Design System

The interface is a dense, desktop-first local workbench informed by Linear's dark product language. It uses a near-black canvas, layered charcoal panels, one restrained violet accent, crisp 1px borders, and compact controls. The result should feel like a dependable native utility rather than a marketing page.

## Tokens

- Canvas: `#09090b`
- Sidebar: `#0c0c0f`
- Surface 1: `#111114`
- Surface 2: `#17171b`
- Border: `#29292f`
- Strong border: `#3a3a43`
- Primary text: `#f4f4f5`
- Secondary text: `#a1a1aa`
- Muted text: `#71717a`
- Accent: `#7c6ff2`
- Accent hover: `#9187f6`
- Success: `#4ade80`
- Warning: `#fbbf24`
- Danger: `#fb7185`

Typography uses Inter/system sans with slightly tightened headings, and JetBrains Mono/system monospace for source IDs, timestamps, paths, and metrics. Spacing follows a 4px base grid. Buttons and inputs use 8px radii; cards use 12px; status pills use full rounding.

## Layout

- 240px fixed sidebar on desktop, compact top navigation on narrow screens.
- 64px application top bar.
- Main content max width is 1440px with 24–32px gutters.
- Dashboard metrics use a responsive four-column grid.
- Operational screens use a two-pane composition when useful: list/context left, detail right.
- Surfaces rely on background elevation and borders, not heavy shadows or gradients.

## Interaction

- Violet is reserved for the brand mark, primary actions, selection, and focus.
- All interactive targets are at least 40px tall.
- Hover changes surface level; focus receives a visible violet ring.
- Processing uses compact status badges and inline progress bars.
- Destructive actions require confirmation and archive data instead of silently deleting it.
- Motion is limited to 150–220ms opacity, color, and transform transitions and respects reduced motion.

## Responsive behavior

At 900px, the sidebar becomes a horizontal rail and multi-column regions stack. At 640px, toolbars wrap, cards become single-column, and secondary labels collapse while preserving touch targets.

