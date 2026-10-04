# Light colour concept (alternative)

A **Material Design 3 light** variant of the [dark concept](color-concept.md).
It uses the **same role names**, so no screen changes: only the values differ.

- [`colors_light.xmlinc`](../src/skin/default/colors_light.xmlinc): all roles, light values
- [`parameters_light.xmlinc`](../src/skin/default/parameters_light.xmlinc): the ten parameters enigma2 reads as raw hex

## Status

The matching light PNG and SVG artwork is in `src/skin/light/`; see
[pixmap-colors.md](pixmap-colors.md). Without it the light colours would sit on
artwork drawn for dark. Nothing here has been run on a receiver.

## Switching

In [`skin.xml`](../src/skin/default/skin.xml):

1. Replace `<xmlinc file="colors.xmlinc"/>` with `<xmlinc file="colors_light.xmlinc"/>`.
2. Add `<xmlinc file="parameters_light.xmlinc"/>` after `parameters.xmlinc`.

3. Copy `src/skin/light/` over the installed `default/` artwork.

Do all three. The parameters file overrides the dark hex values and relies on a
later definition replacing an earlier one. I have not verified that on a
receiver, so check the keyboard and separator colours after switching.

## How light differs from dark

| | Dark | Light |
|---|---|---|
| Depth | higher surface = lighter | higher surface = darker; `md_surface_container_lowest` is white |
| Text | light on dark | dark on light |
| Accent | pale blue `#a8c7fa` | deep blue `#0b57d0` |
| Containers | deep blue `#0842a0` | pale blue `#d3e3fd` |
| State colours | pastel tones | deep, saturated tones |

The hue family is unchanged: blue primary, slate secondary, teal tertiary.
Containers swap roles with their text: a container is pale and its `on_` text
is dark, the reverse of the dark theme.

## Palette

Values are `#AARRGGBB`; alpha `00` is opaque.

### Surfaces (darker = higher, white at the bottom)

| Role | Value |
|---|---|
| `md_surface` | `#02f8f9fa` |
| `md_surface_solid` | `#00f8f9fa` |
| `md_surface_container_lowest` | `#00ffffff` |
| `md_surface_container_low` | `#00f2f3f5` |
| `md_surface_container` | `#00eceef0` |
| `md_surface_container_high` | `#02e6e8eb` |
| `md_surface_container_highest` | `#00dfe2e5` |

### Overlays

| Role | Value |
|---|---|
| `md_scrim` | `#7f000000` |
| `md_surface_overlay_soft` | `#18f8f9fa` |
| `md_surface_overlay` | `#2df8f9fa` |
| `md_surface_overlay_strong` | `#faf8f9fa` |

### Outline and text

| Role | Value |
|---|---|
| `md_outline` | `#00676a69` |
| `md_outline_variant` | `#01c4c6ca` |
| `md_on_surface` | `#001b1c1e` |
| `md_on_surface_variant` | `#00444746` |

### Accents

| Role | Value |
|---|---|
| `md_primary` | `#000b57d0` |
| `md_primary_container` | `#00d3e3fd` |
| `md_primary_container_translucent` | `#25d3e3fd` |
| `md_primary_container_soft` | `#08d3e3fd` |
| `md_on_primary_container` | `#00041e49` |
| `md_secondary` | `#00565f71` |
| `md_secondary_container` | `#00dae2f9` |
| `md_on_secondary_container` | `#00131c2b` |
| `md_tertiary` | `#00006a60` |

### State

| Role | Value |
|---|---|
| `md_success` / `md_success_container` | `#00146c2e` / `#00c4eed0` |
| `md_warning` / `md_warning_container` | `#00855300` / `#00ffe0b2` |
| `md_error` / `md_error_container` | `#00b3261e` / `#00f9dedc` |

### Remote colour keys

`md_key_red` `#00d93025`, `md_key_green` `#001e8e3e`, `md_key_yellow`
`#00f9ab00`, `md_key_blue` `#001a73e8`. As in the dark theme, they stay
recognisably red, green, yellow and blue.

### Fixed

`md_shadow` `#00000000` and `md_transparent` `#ff000000` are the same in both
themes.

## Contrast

Computed from the hex values, against `md_surface` (`#f8f9fa`) unless noted.
WCAG AA needs 4.5:1 for normal text.

| Pair | Ratio |
|---|---|
| `md_on_surface` | 16.2 |
| `md_on_surface_variant` | 8.9 |
| `md_primary` | 6.1 |
| `md_secondary` | 6.1 |
| `md_tertiary` | 6.2 |
| `md_success` | 6.2 |
| `md_warning` | 6.2 |
| `md_error` | 6.2 |
| `md_outline` | 5.2 |
| `md_primary` on `md_surface_container_high` | 5.2 |
| `md_on_primary_container` on `md_primary_container` | 12.6 |
| `md_on_secondary_container` on `md_secondary_container` | 13.2 |

`md_outline_variant` is 1.6:1 by design: dividers only, never text.

## Things to watch

- **Remote colour keys as text.** The key colours are meant as fills. In the
  light theme `md_key_yellow` is too light to carry text on a light surface.
- **Selected keyboard cell.** In the dark theme the selected on-screen-keyboard
  cell is light blue; in the light theme it is deep blue. If the key label there
  is dark, it will be hard to read. I did not check how enigma2 colours that
  label.
- **Fixed black.** `md_shadow` stays black, so anything that uses it as a
  background, such as the poster well in PlutoTV, stays black in both themes.
- **Over video.** Infobar overlays become light translucent panels. Check that
  they stay legible over bright and dark video.

## Legacy names

`colors_light.xmlinc` also defines the old colour names for plugin skins. All
follow their Material role, except `white` (`#00f0f0f0`) and `black`
(`#00000000`), which stay literal. A plugin that pairs `white` text with its own
dark background keeps working; if `white` followed `md_on_surface` it would turn
dark-on-dark.
