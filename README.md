# Material Skin for Open Enigma2 settop boxes

This skin is based on E2-DarkOS-skin by DimitarCC

# Colour concept

The skin uses a **Material Design 3 dark** colour scheme. Every colour a screen
uses is a symbolic *role* (`md_surface`, `md_primary`, ...) defined once in
[`src/skin/default/colors.xmlinc`](src/skin/default/colors.xmlinc). Screens
never contain hex values and never use the old colour names.

A [light variant](docs/color-concept-light.md) with the same role names is available
as an alternative.

## Principles

1. **Roles, not colours.** A screen says what a colour is *for*
   (`md_on_surface` = primary text), not what it looks like. Changing the look
   of the whole skin means editing one file.
2. **Depth from lightness, not from colour.** On a dark theme, surfaces that
   sit higher are lighter. Panels, rows and bars are told apart by seven grey
   steps, not by hue.
3. **One accent family.** A single blue `md_primary` carries emphasis. A muted
   slate `md_secondary` carries supporting text. Everything else is neutral.
4. **Colour means something.** Green, amber and red are used only for state
   (ok, caution, error/record) and for the remote's colour keys. They are not
   decoration.
5. **Readable first.** Every text role reaches at least WCAG AA (4.5:1) on the
   surface it is used on (see [Contrast](#contrast)).

## Palette

Values are enigma2 `#AARRGGBB`; alpha `00` is opaque.

### Surfaces (lighter = higher)

| Role | Value | Use |
|---|---|---|
| `md_surface` | `#02121212` | window and list background |
| `md_surface_solid` | `#00121212` | surface that must stay fully opaque |
| `md_surface_container_lowest` | `#000e0e0e` | top bars, deepest wells |
| `md_surface_container_low` | `#001d1d1d` | cards, secondary panels |
| `md_surface_container` | `#00232323` | default container |
| `md_surface_container_high` | `#022c2c2c` | selected row, raised container |
| `md_surface_container_highest` | `#00363636` | chips, bars, inactive fills |

### Overlays

| Role | Value | Use |
|---|---|---|
| `md_scrim` | `#7f000000` | dimming layer behind dialogs |
| `md_surface_overlay_soft` | `#18121212` | light translucent surface |
| `md_surface_overlay` | `#2d121212` | translucent surface |
| `md_surface_overlay_strong` | `#fa121212` | almost opaque translucent surface |

### Outline and text

| Role | Value | Use |
|---|---|---|
| `md_outline` | `#00919191` | borders, inactive text |
| `md_outline_variant` | `#01424242` | dividers, separators |
| `md_on_surface` | `#00e3e3e3` | primary text |
| `md_on_surface_variant` | `#00c4c4c4` | secondary text |

### Accents

| Role | Value | Use |
|---|---|---|
| `md_primary` | `#00a8c7fa` | titles, key info, selected text, scrollbar sliders |
| `md_primary_container` | `#000842a0` | selected / active container |
| `md_primary_container_translucent` | `#250842a0` | progress track |
| `md_primary_container_soft` | `#080842a0` | faint tonal wash |
| `md_on_primary_container` | `#00d3e3fd` | text on a primary container |
| `md_secondary` | `#00bdc7dc` | supporting text (next event, sub-lines) |
| `md_secondary_container` | `#003f4759` | marked rows |
| `md_on_secondary_container` | `#00d9e3f8` | text on a secondary container |
| `md_tertiary` | `#007fd6c8` | times and durations |

### State

| Role | Value | Use |
|---|---|---|
| `md_success` / `md_success_container` | `#0081c995` / `#000f5223` | ok, on |
| `md_warning` / `md_warning_container` | `#00ffb74d` / `#006b3f00` | caution |
| `md_error` / `md_error_container` | `#00f28b82` / `#008c1d18` | error, recording |

### Remote colour keys

`md_key_red` `#00f28b82`, `md_key_green` `#0081c995`, `md_key_yellow`
`#00fdd663`, `md_key_blue` `#008ab4f8`. These stay clearly recognisable on
purpose, so the on-screen keys match the buttons on the remote.
## Links
- Installation: https://xcentaurix.github.io/MaterialSkinCockpit
