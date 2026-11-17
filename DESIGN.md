---
name: Spectra QA
description: Unified AI QA automation and bilingual Thai/English document verification workspace
colors:
  neon-iris: "#6366f1"
  plasma-violet: "#a855f7"
  signal-cyan: "#06b6d4"
  deep-midnight: "#050505"
  obsidian-surface: "#0a0b12"
  slate-panel: "#12141c"
  crisp-white: "#f8fafc"
  muted-slate: "#94a3b8"
  dim-slate: "#475569"
  emerald-ok: "#10b981"
  amber-warn: "#f59e0b"
  rose-alert: "#f43f5e"
typography:
  display:
    fontFamily: "Outfit, Inter, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Prompt, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0em"
  title:
    fontFamily: "Outfit, Inter, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.03em"
  body:
    fontFamily: "Prompt, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0em"
  label:
    fontFamily: "Outfit, Inter, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.05em"
rounded:
  sm: "8px"
  md: "12px"
  lg: "20px"
  xl: "28px"
  pill: "20px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.neon-iris}"
    textColor: "{colors.crisp-white}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 24px"
  button-secondary:
    backgroundColor: "{colors.slate-panel}"
    textColor: "{colors.crisp-white}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  button-warning:
    backgroundColor: "{colors.deep-midnight}"
    textColor: "{colors.amber-warn}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  button-warning-hover:
    backgroundColor: "{colors.amber-warn}"
    textColor: "{colors.crisp-white}"
  input-default:
    backgroundColor: "{colors.obsidian-surface}"
    textColor: "{colors.crisp-white}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "12px 15px"
  nav-item-active:
    backgroundColor: "{colors.slate-panel}"
    textColor: "{colors.crisp-white}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
  badge-status:
    backgroundColor: "{colors.obsidian-surface}"
    textColor: "{colors.emerald-ok}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "6px 12px"
  card-glass:
    backgroundColor: "{colors.slate-panel}"
    textColor: "{colors.crisp-white}"
    rounded: "{rounded.lg}"
    padding: "32px"
---

# Design System: Spectra QA

## Overview

**Creative North Star: "The Spectrum Command Deck"**

Spectra QA is a dark glassmorphic mission control built for precise, nocturnal, telemetry-driven QA work. Its surfaces stay calm and low-glare so dense test artifacts, API payloads, and bilingual Thai/English OCR results remain effortless to scan over long engineering sessions.

Rather than relying on bright chrome or heavy card shadows, the interface pairs deep obsidian canvases with subtle frosted panels, hairline borders, and a restrained indigo-to-violet spectrum accent that activates only on primary actions, active navigation, and live system telemetry. Bright white enterprise dashboards and unstyled browser defaults are explicitly rejected.

**Key Characteristics:**
- Nocturnal obsidian canvas (`deep-midnight` and `obsidian-surface`) with a slow-drifting ambient spectrum backdrop.
- Bilingual typographic pairing: geometric English headings/labels (`Outfit`, `Inter`) paired with legible Thai body copy (`Prompt`).
- Flat tonal surfaces separated by 1px translucent borders, reserving glow and lift for hover, focus, and active states.
- Semantic status discipline (`emerald-ok`, `amber-warn`, `rose-alert`, `signal-cyan`) for health, warnings, and destructive actions.

## Colors

The palette anchors dark neutral surfaces with a focused indigo-violet spectrum pair and semantic status accents.

### Primary
- **Neon Iris** (`colors.neon-iris`): Core interactive accent used for primary CTAs, active navigation tints, focus borders, and the start stop of the primary gradient.

### Secondary
- **Plasma Violet** (`colors.plasma-violet`): Paired with Neon Iris in the primary gradient, active sidebar icon glow, and select-dropdown focus rings.

### Tertiary
- **Signal Cyan** (`colors.signal-cyan`): Subtle ambient telemetry accent used sparingly in background radial washes and informational highlights.

### Neutral
- **Deep Midnight** (`colors.deep-midnight`): Root viewport background (`html, body`), modal backdrops, and dropdown surfaces.
- **Obsidian Surface** (`colors.obsidian-surface`): Secondary dark surface for login cards, recessed inputs, and elevated overlays.
- **Slate Panel** (`colors.slate-panel`): Base surface for frosted glass panels (`rgba(18, 20, 28, 0.45)` with 16px backdrop blur) and workspace containers.
- **Crisp White** (`colors.crisp-white`): Primary body and heading text on dark surfaces.
- **Muted Slate** (`colors.muted-slate`): Secondary labels, inactive nav items, timestamps, and metadata.
- **Dim Slate** (`colors.dim-slate`): Breadcrumb prefixes, placeholders, and footer links.

### Semantic
- **Emerald Ok** (`colors.emerald-ok`): System-ready status badges and positive health dots.
- **Amber Warn** (`colors.amber-warn`): Warning buttons and cautionary states.
- **Rose Alert** (`colors.rose-alert`): Logout actions, delete controls, notification count badges, and error states.

### Named Rules
**The Glow-On-Intent Rule.** Resting cards and navigation items stay flat; Neon Iris and Plasma Violet glows appear only on primary CTAs, active indicators, hover states, and focus rings.

## Typography

**Display Font:** `Outfit`, `Inter` (with `sans-serif` fallback)
**Body Font:** `Prompt` (with `sans-serif` fallback)
**Label/UI Font:** `Outfit`, `Inter` (with `sans-serif` fallback)

**Character:** Crisp geometric English display and metadata paired with clean, well-spaced Thai body typography so mixed-language QA specs and OCR documents read harmoniously.

### Hierarchy
- **Display** (`700`, `2rem` / `32px`, line-height `1.2`, letter-spacing `-0.03em`): Page and auth hero titles (`Outfit`).
- **Headline** (`600`, `1.25rem` / `20px`, line-height `1.3`): Modal headers and section headings (`Prompt`).
- **Title** (`700`, `1.125rem` / `18px`, line-height `1.2`, letter-spacing `0.03em`): Sidebar brand wordmark (`Outfit`) and card titles.
- **Body** (`400`, `0.875rem` / `14px`, line-height `1.6`): Default reading size across workspace views, OCR results, and form controls (`Prompt`).
- **Label** (`600`, `0.75rem` / `12px`, line-height `1.2`, letter-spacing `0.05em`): Breadcrumbs, uppercase section dividers, status badges, and micro-metadata (`10px–11px` for history dates and counts).

### Named Rules
**The Bilingual Separation Rule.** Use `Outfit` / `Inter` for English branding, breadcrumbs, numeric badges, and technical labels; use `Prompt` for Thai prose, OCR output, and bilingual form controls.

## Layout

The application uses a fixed full-viewport (`100vw` × `100vh`) shell split into a persistent `260px` left sidebar and a flexible main workspace column (`flex: 1; min-width: 0`). Above the scrollable content area (`32px` padding, or `0` for full-bleed canvas views like the workflow builder), a `70px` frosted topbar anchors breadcrumbs, global search (`260px` pill), notifications, system status, and user profile.

Below `900px`, the shell stacks vertically: the sidebar collapses into a horizontal scrollable strip at the top and the desktop topbar hides. Feature views use responsive breakpoints at `1024px`, `768px`, `640px`, and `600px` to stack multi-column grids and dashboards.

## Elevation & Depth

Surfaces rely on flat tonal layering and frosted translucency rather than heavy drop shadows. Panels sit on `1px solid` translucent white borders (`rgba(255, 255, 255, 0.08)` at rest, `0.15` on emphasis) with `backdrop-filter: blur(16px)`.

### Shadow Vocabulary
- **Glass Panel Shadow** (`box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37)`): Ambient separation for frosted containers.
- **Modal & Card Depth** (`box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5)`): Deep backdrop separation for centered modal dialogs and floating dropdowns.
- **Primary Action Glow** (`box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3)` resting, `0 8px 25px rgba(99, 102, 241, 0.5)` hover): Tactile lift reserved for primary gradient buttons.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat and border-defined at rest; elevation shadows and spectrum glows appear only on overlays or in response to hover, focus, and active selection.

## Shapes

The system uses a consistent rounded-rectangle vocabulary scaled by container size:
- **Compact Controls** (`8px` / `rounded.sm`): History items, delete icon buttons, and small inner badges.
- **Standard Interactive** (`12px` / `rounded.md`): Buttons, text inputs, selects, and sidebar navigation items.
- **Panels & Modals** (`20px` / `rounded.lg`): Frosted glass panels, modal dialogs, and pill search/status containers.
- **Hero Cards** (`28px` / `rounded.xl`): Large authentication and feature spotlight cards.
- **Circular** (`50%`): Icon buttons, avatars, and status indicator dots (`8px`).

## Components

Controls balance restrained dark surfaces with crisp interactive states.

### Buttons
- **Shape:** Standard interactive corners (`12px` radius).
- **Primary:** Indigo-to-violet linear gradient (`135deg`) with crisp white text, `10px 24px` padding, and soft indigo shadow; lifts `-2px` on hover with expanded glow and settles back on active press.
- **Secondary:** Subtle translucent fill (`rgba(255, 255, 255, 0.05)`) with `1px` glass border and `10px 20px` padding; brightens to `0.1` fill on hover.
- **Warning:** `1px solid` Amber Warn border on `10%` amber tint; fills solid Amber Warn with white text on hover.

### Chips / Status Badges
- **Style:** Pill-shaped (`20px` radius), `6px 12px` padding, `12px` medium `Outfit` label with an `8px` glowing status dot (`Emerald Ok` for ready, `Rose Alert` for error).
- **Notification Count:** Compact `18px` pill in `Rose Alert` with `2px` `Deep Midnight` cutout border.

### Cards / Containers
- **Corner Style:** `20px` radius (`28px` for hero auth cards).
- **Background:** Frosted `Slate Panel` (`rgba(18, 20, 28, 0.45)`) with `blur(16px)`.
- **Shadow Strategy:** Ambient glass shadow at rest (`0 8px 32px rgba(0, 0, 0, 0.37)`).
- **Border:** `1px solid rgba(255, 255, 255, 0.08)` (`0.15` for emphasized cards).
- **Internal Padding:** `32px` for modals and workspace containers (`50px` on hero login card).

### Inputs / Fields
- **Style:** Recessed dark fill (`rgba(0, 0, 0, 0.2)` to `0.3`) with `1px` glass border, `12px` radius, and `12px 15px` padding; native `<select>` elements use `rgba(18, 20, 28, 0.85)` with a custom violet chevron and `1px solid rgba(168, 85, 247, 0.35)` border.
- **Focus:** Shifts border to `Neon Iris` (or `Plasma Violet` with `3px` soft violet ring on selects) and removes default browser outline.

### Navigation
- **Sidebar Item:** `12px 16px` padding, `12px` radius, `14px` medium `Outfit` text in `Muted Slate`; active state applies `15%` `Neon Iris` tint, `30%` border, a `4px` left gradient bar, and glowing `Plasma Violet` icon.
- **Topbar Search:** `260px` pill (`20px` radius) with `8px 16px` padding and `Neon Iris` focus-within ring.

## Do's and Don'ts

### Do:
- **Do** keep resting surfaces dark and flat (`Deep Midnight`, `Obsidian Surface`, `Slate Panel`) separated by `1px` translucent borders.
- **Do** use `Prompt` for Thai and bilingual content and `Outfit` / `Inter` for English headings, navigation, and telemetry labels.
- **Do** reserve `Neon Iris` and `Plasma Violet` glows for active states, hover feedback, focus rings, and primary CTAs.
- **Do** preserve the `4px` left gradient indicator on active sidebar navigation items.

### Don't:
- **Don't** introduce bright white/light-mode enterprise dashboard surfaces or unstyled browser default `<select>` / `<input>` controls.
- **Don't** add heavy neon drop-shadows to resting cards or inactive list items.
- **Don't** mix arbitrary border radii; stick to the `8px` / `12px` / `20px` / `28px` scale.

