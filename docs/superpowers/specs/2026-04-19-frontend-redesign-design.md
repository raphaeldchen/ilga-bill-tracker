# Frontend Redesign — Editorial Design System

**Date:** 2026-04-19
**Scope:** `static/style.css`, `static/index.html`, `static/admin.html`, `static/login.html`
**Approach:** Deep PicoCSS theming + editorial layer (Option C)

---

## Goal

Transform the app's visual identity from "plain PicoCSS default" to a polished editorial aesthetic — clean, typographically rich, and readable. Target audience is internal staff. Light mode only.

---

## Design Principles

- **Editorial over app-like** — structure and typography do the heavy lifting, not color or decoration
- **Ink on paper** — warm off-white base, near-black text, restrained accent use
- **Hierarchy through type** — Playfair Display for display/label contexts only; Inter for all data
- **Consistent design language** — `#003366` left/top border treatment used across header, expanded rows, and login card

---

## Color Palette

Override PicoCSS CSS custom properties (`--pico-*`) at the `:root` level.

| Token | Value | Role |
|---|---|---|
| Background | `#faf9f7` | Page background, warm off-white |
| Surface | `#ffffff` | Sidebar, table rows, cards |
| Border | `#e0ddd8` | Dividers, row separators |
| Text primary | `#1a1a1a` | Near-black ink |
| Text muted | `#6b6560` | Dates, labels, secondary info |
| Accent | `#003366` | Illinois blue — buttons, bill IDs, borders |
| Accent hover | `#00254d` | Darker accent for hover states |
| Error | `#9b2335` | Errors, delete/remove actions |

---

## Typography

Load from Google Fonts:
- **Playfair Display** — display/label use only (masthead, sidebar section labels, expanded panel headings)
- **Inter** — all body text, table data, inputs, buttons

### Usage rules
- Playfair Display: app title (1.4rem, normal weight), section labels (0.7rem, uppercase, letter-spacing), expanded panel headings
- Inter: everything else — table data (0.875rem), toolbar (0.8rem), buttons, inputs
- Tabular numbers on date columns (`font-variant-numeric: tabular-nums`)

---

## Section Designs

### Header / Masthead
- App title: Playfair Display, 1.4rem, normal weight
- Masthead rule: 2px `#003366` bottom border below the standard 1px separator
- Slightly increased vertical padding
- Admin badge: pill-shaped, `#003366` fill, tighter sizing
- Fetch Updates / Log out buttons: match new scale

### Sidebar
- Section label ("Tracked Bills"): Playfair Display, small uppercase, wide letter-spacing
- Bill list hover: `#003366` 2px left border flash (replaces background fill)
- Add bill input (admin): flat bottom-border-only style
- Add button: small solid `#003366` rectangle
- Remove button: muted, turns `#9b2335` on hover
- Sidebar background: `#ffffff` against `#faf9f7` page

### Main Table
- Header row: Inter uppercase 0.7rem, `#003366` text, wide letter-spacing
- Bill ID cell: monospace, `#003366`, slightly bolder — acts as row headline
- Date cell: Inter, muted `#6b6560`, tabular numbers
- Chamber cell: inline outlined pill badge (`HOUSE` / `SENATE`), `#003366` outline, no fill
- Action cell: regular Inter, full-width
- Row separators: thin `#e0ddd8` rules (no zebra striping)
- Clickable rows: subtle `→` indicator in Bill ID cell signals expandability
- Toolbar count: Inter small-caps; filter dropdown matches new scale

### Expanded Row Panel
- Background: `#ffffff` with `#003366` 3px left border
- "Action History" heading: Playfair Display, small muted uppercase label
- Inner history table: tight Inter rows, 0.72rem, same date/chamber/action columns
- Chamber badges: same outlined pills as main table
- Notes section: separated by `#e0ddd8` rule; label in Playfair uppercase
- Admin Save button: small flat `#003366` filled rectangle
- Expand/collapse: CSS `max-height` animation, ~150ms

### Login Page
- Page background: `#faf9f7`
- Card: `#ffffff`, `#003366` 3px top border
- App title: Playfair Display, same masthead style
- "Admin Login" subheading: Inter, muted
- Password input: flat bottom-border-only style
- Sign in button: full-width, solid `#003366`, Inter medium weight
- Error message: `#9b2335`, small Inter
- Back link: small, muted, centered

---

## Files Changed

| File | Changes |
|---|---|
| `static/style.css` | Override PicoCSS tokens at `:root`; rewrite section-specific rules |
| `static/index.html` | Add Google Fonts `<link>`; minor markup adjustments (chamber badge spans) |
| `static/admin.html` | Same as index.html |
| `static/login.html` | Restyle card; add Google Fonts `<link>`; move inline styles to shared sheet |

No JS changes required. No new dependencies beyond Google Fonts CDN.

---

## Out of Scope

- Dark mode
- Mobile/responsive layout changes
- Any backend or API changes
- Admin.js / app.js logic changes
