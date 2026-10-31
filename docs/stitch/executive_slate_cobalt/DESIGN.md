---
name: Executive Slate & Cobalt
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#c7c4d8'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#918fa1'
  outline-variant: '#464555'
  surface-tint: '#c3c0ff'
  primary: '#c3c0ff'
  on-primary: '#1d00a5'
  primary-container: '#4f46e5'
  on-primary-container: '#dad7ff'
  inverse-primary: '#4d44e3'
  secondary: '#4cd7f6'
  on-secondary: '#003640'
  secondary-container: '#03b5d3'
  on-secondary-container: '#00424e'
  tertiary: '#4edea3'
  on-tertiary: '#003824'
  tertiary-container: '#006e4b'
  on-tertiary-container: '#67f4b7'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3323cc'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  display-hero:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  metric-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  metric-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.015em
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-tabular:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.01em
  badge-micro:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-compact: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system targets high-growth B2B finance executives, revenue operations leaders, and billing administrators who demand real-time clarity over recurring revenue, churn velocity, and invoice lifecycles. The visual personality communicates mathematical precision, institutional reliability, and effortless executive speed.

The design movement blends **Modern Fintech Precision** with subtle **Glassmorphic Depth**:
- Deep navy slate foundations eliminate eye fatigue across dense ledger and lifecycle monitoring screens.
- Controlled cobalt-indigo luminous accents guide key operational paths without cognitive overload.
- Financial figures command authoritative visual presence through strict tabular geometry and crisp contrast.
- Visual elements avoid playful whimsy, instead prioritizing structural hierarchy, crisp 1px separation lines, and micro-interactions that feel engineered and tactile.

## Colors

The palette is engineered for high-density, multi-tenant billing environments with mission-critical status indicators:

- **Canvas & Structural Neutrals:**
  - `bg-canvas`: `#0B0F17` (Deepest void navy base)
  - `bg-surface`: `#0F172A` (Elevated slate surface for content containers and sidebars)
  - `bg-surface-elevated`: `#1E293B` (Cards, drawers, popovers, and table rows)
  - `border-subtle`: `rgba(148, 163, 184, 0.12)` (Hairline grid and divider borders)
  - `border-focus`: `rgba(99, 102, 241, 0.45)` (Interactive element outlines)

- **Brand Accents:**
  - `primary-base`: `#4F46E5` (Cobalt Indigo for focal triggers, active tabs, and primary actions)
  - `primary-glow`: `#6366F1` (Hover state, focus rings, and high-priority callouts)
  - `secondary-highlight`: `#06B6D4` (Cyan telemetry metrics, lifecycle connectors, and chart vectors)

- **Subscription Lifecycle States:**
  - `state-active-emerald`: `#10B981` (Settled payments, active contracts, auto-debit success)
  - `state-pending-amber`: `#F59E0B` (In-trial, aging dunning, renewal pending)
  - `state-alert-rose`: `#EF4444` (Failed webhooks, hard churn, delinquent mandates)

- **Typography Tones:**
  - `text-primary`: `#F8FAFC` (High-contrast metrics and primary text)
  - `text-secondary`: `#94A3B8` (Metadata, column headers, currency symbols)
  - `text-muted`: `#64748B` (Audit timestamps, inactive status labels)

## Typography

The typography pairs **Plus Jakarta Sans** for interfaces and headings with **Inter** for dense transactional layers.

- **Tabular Numerics Rule:** All ledger data, billing quantities, transaction IDs, and currency amounts in Indian Rupees (₹) must utilize Inter with active open-type tabular lining numerals (`font-feature-settings: "tnum" 1, "cv05" 1`). This guarantees strict vertical alignment across multi-row subscription tables and reconciliation matrices.
- **Indian Rupee Standard:** The currency symbol (₹) precedes numbers without a space (e.g., `₹12,49,200.00`), set in `text-secondary` weight to maintain metric readability.
- **Section Headers & Metric Contrast:** Use `Plus Jakarta Sans` semi-bold styling for section titles and page headers. Financial telemetry blocks juxtapose a 12px uppercase slate label directly above bold 24px/32px Inter tabular numerical readouts.

## Layout & Spacing

The layout is built for SaaS control panels managing multi-entity billing workflows.

- **Layout Grid & Structure:**
  - **Global Frame:** Fixed 260px collapsible administrative sidebar on the left, paired with a fluid main workspace bounded to a maximum width of `1680px`.
  - **12-Column Ledger Grid:** Content modules and stat arrangements follow a 12-column grid with `1.5rem` (`24px`) gutters.
  - **Sticky Action Banner:** Top application headers are pinned (`sticky top-0 z-40`) at `56px` height, featuring a backdrop blur to keep critical billing filters and batch actions permanently visible.

- **Responsive Adaptations:**
  - **Desktop (≥ 1280px):** Full 12-column span, visible multi-filter action bar, standard high-density data tables showing all 7–9 ledger columns.
  - **Tablet (768px – 1279px):** Sidebar collapses to an icon rail (68px). Dashboard stat panels shift to 2x2 grids; non-essential table columns (e.g., tax breakdown, raw webhook timestamps) tuck into expandable row drawers.
  - **Mobile (< 768px):** Sidebar converts into a sliding off-canvas sheet; canvas margin reduces to `1rem`. High-density tables pivot into structured swipeable subscription card stacks with status badges fixed in the top right corner.

## Elevation & Depth

Visual hierarchy uses a dark-slate layered surface model accentuated with subtle frosted glass and micro-luminescence:

- **Layer 0 (Canvas Base):** Deepest slate (`#0B0F17`), unadorned and non-reflective.
- **Layer 1 (Card & Module Surfaces):** Slate container (`#0F172A`) framed with a 1px border of `rgba(148, 163, 184, 0.08)`. No diffuse shadow is applied; structure is established by surface-contrast alone.
- **Layer 2 (Glassmorphic Stat Tiles):** Semi-translucent panels (`background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(16px);`) edged with a directional linear border (`linear-gradient(180deg, rgba(255, 255, 255, 0.12) 0%, rgba(255, 255, 255, 0.02) 100%)`).
- **Layer 3 (Overlays & Drawer Sheets):** Higher-tier slate (`#1E293B`) elevated by a directional ambient shadow: `0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)` with an inner top border glow `rgba(255, 255, 255, 0.06)`.
- **Active State Glow:** Focused form elements, active lifecycle stages, and primary triggers emit a low-spread cobalt glow (`box-shadow: 0 0 0 1px #4F46E5, 0 0 14px -2px rgba(79, 70, 229, 0.4)`).

## Shapes

The design system enforces a **Soft (Level 1)** geometric standard. This delivers an architectural, crisp feel suited for enterprise fintech, preventing the casual playfulness of rounder radii while eliminating the harshness of raw 90-degree corners:

- Standard controls, inputs, status pills, and small buttons use `0.25rem` (`4px`) or `0.375rem` (`6px`).
- Metric cards, slide-over sheets, and modal frames use `0.5rem` (`8px`) (`rounded-lg`).
- High-level containers and layout boundaries never exceed `0.75rem` (`12px`) (`rounded-xl`).
- Status indicator dots and badge pills use circular radii (`rounded-full`) exclusively to highlight transactional state changes.

## Components

### Buttons
- **Primary:** Solid cobalt background (`#4F46E5`), sharp `0.375rem` corner radius, white semibold text, with an inline micro-transition. Hover transitions to `#6366F1` with an ambient glow.
- **Secondary / Ghost:** Transparent background with hairline border `rgba(148, 163, 184, 0.2)` and slate-200 text. Hover activates `rgba(30, 41, 59, 0.7)` background.
- **Destructive:** Deep rose-tinted surface (`rgba(239, 68, 68, 0.1)`) with `#EF4444` border and text.

### High-Density Data Tables
- **Grid Layout:** Table headers are uppercase 11px Inter semibold (`text-slate-400`) over a pinned slate bar (`#0B0F17`) with a 1px solid lower border (`rgba(148, 163, 184, 0.1)`).
- **Row Anatomy:** Alternating zebra rows are avoided; clean rows feature a `1px` subtle bottom border. Row hover introduces a smooth `#1E293B/50` slate wash.
- **Monetary Cells:** Always right-aligned with Inter tabular numerals and clear Rupee currency markers.

### Status Badges & Lifecycle Chips
- Compact dimensions: `h-6`, `px-2.5`, `text-xs`, `font-semibold`.
- **Active / Paid:** Emerald glow pill (`bg-emerald-500/10 text-emerald-400 border border-emerald-500/20`) featuring an inner 6px solid emerald status dot.
- **Dunning / Overdue:** Amber glow pill (`bg-amber-500/10 text-amber-400 border border-amber-500/20`).
- **Canceled / Failed:** Rose glow pill (`bg-rose-500/10 text-rose-400 border border-rose-500/20`).
- **Trial / Provisioning:** Cyan highlight pill (`bg-cyan-500/10 text-cyan-400 border border-cyan-500/20`).

### Subscription Lifecycle Progress Bar
- Multi-segment linear track (`h-2`, `rounded-full`, `bg-slate-800`).
- Shows segmented stages: Trial (Cyan) → Activated (Cobalt) → Renewed/Paid (Emerald) or At-Risk (Amber).
- Completed segments link via micro-glow connectors; pending cycles remain dotted slate tracks.

### Input Fields & Search Bars
- Background `#0F172A`, 1px border `rgba(148, 163, 184, 0.18)`, `rounded-md`, text `#F8FAFC`.
- Focus state instantly drops the border into cobalt `#4F46E5` with a 2px outer outline ring at 20% opacity.
- Includes embedded search shortcuts (e.g., `⌘K`) rendered in miniature slate keyboard keycaps (`kbd`).

### Sidebar Navigation & Badge Counters
- Dark slate column (`#0B0F17`) partitioned by a 1px vertical slate-800 divider.
- Nav items display 16px geometric icons alongside medium-weight labels. Active item receives a vertical 2px left border accent in `#4F46E5` and a soft background gradient.
- Unread webhook and failed retry alerts display an integrated badge counter (`bg-rose-500 text-white font-bold text-[10px] px-1.5 py-0.5 rounded-full`).