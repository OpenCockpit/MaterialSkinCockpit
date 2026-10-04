# Pixmap colours

The PNG and SVG artwork follows the same Material roles as the screens, in a
dark and a light version. Nothing is hand-edited: both versions are generated
from the original artwork by
[`tools/recolor_pixmaps.py`](../tools/recolor_pixmaps.py), which reads the role
values from `colors.xmlinc` and `colors_light.xmlinc`. Change a role value,
rerun the tool, and the artwork follows.

| Theme | Where | Contents |
|---|---|---|
| Dark | `src/skin/default/` (in place) | all 433 PNG and 57 SVG recoloured |
| Light | `src/skin/light/` | the same 433 PNG and 57 SVG, recoloured for light |

`src/skin/light/` holds only the files that change. The files left alone (see
[Left unchanged](#left-unchanged)) are not copied, so a light skin takes
`default/` and lays `light/` over it.

## How a pixel is recoloured

Each file has one of six treatments. The first matching rule in the tool's
`RULES` table wins.

| Treatment | For | Neutral (grey) pixels | Coloured pixels |
|---|---|---|---|
| `icon` | status icons, most of `icons/`, `dvr/`, `infobar/` | tone ramp | role for the hue, shading kept |
| `neutral` | menu icons, `screen_icons/`, audio/video logos, `window/`, `border/` | tone ramp | left as drawn |
| `plate` | keycaps in `buttons/` | plate ramp | none |
| `tile` | the thin EPG entry backgrounds in `epg/` | tone ramp | container role for the hue |
| `key` | `key_red/green/yellow/blue` | n/a | flat `md_key_*` colour |
| skip | see below | n/a | n/a |

**Tone ramp.** The artwork was drawn light-on-dark. Black becomes `md_surface`
and white becomes `md_on_surface`, with greys in between. In the dark theme this
keeps the original direction (light glyphs). In the light theme the same
formula flips it, because `md_surface` is then light and `md_on_surface` is dark,
so white glyphs become dark glyphs and dark chrome becomes pale.

**Plate ramp.** Keycaps are a light plate with a dark glyph. Black (the glyph)
becomes `md_on_surface` and white (the plate) becomes
`md_surface_container_highest`. That makes the keys dark chips with light
labels in the dark theme and pale chips with dark labels in the light theme.

**Hue to role.** A pixel counts as coloured when its saturation is 0.15 or more.
Its hue picks the role:

| Hue | Accent role | Container role |
|---|---|---|
| red | `md_error` | `md_error_container` |
| orange, yellow | `md_warning` | `md_warning_container` |
| green | `md_success` | `md_success_container` |
| blue | `md_primary` | `md_primary_container` |
| purple, magenta | `md_tertiary` | `md_secondary_container` |

`icon` pixels take the accent role, darkened by the pixel's brightness so
gradients and outlines survive. `tile` pixels stay close to the container role,
because they are backgrounds. The result is blended with the neutral value in
proportion to saturation, so pale highlights stay pale.

**SVG.** Hex colours and `white`/`black` in `fill`, `stroke` and `stop-color`
go through the same ramps.

**Light theme only.** Pixels with alpha 32 or below are made fully transparent.
The original icons have near-invisible white halos at alpha 1 to 26. They
vanish on a dark surface but would turn into a grey haze once inverted.

## Left unchanged

100 files are skipped in both themes because they are full-colour artwork that
reads on either surface, or are not part of the on-screen theme:

- `weather_icons/` (weather illustrations)
- `ratings/` (age-rating badges, whose colours carry meaning)
- `iconsVFD/` (front-panel display icons)
- logos, the preview image, the default picon and the `.jpg`
- the red-to-green signal bar in `infobar/`

Coloured pixels in `neutral` files (for example the Jellyfin and Emby menu
logos) are also kept, so brand logos are not repainted.

## Regenerating

Needs Python 3 and Pillow. Source artwork is always read from git revision
`27a7196` (the last commit before any pixmap was recoloured), so dark and
light are both derived from the originals and the tool can be rerun safely.

```
python tools/recolor_pixmaps.py --theme dark  --out src/skin/default
python tools/recolor_pixmaps.py --theme light --out src/skin/light
```

Add `--dry-run` to check without writing. Each run takes under a minute. If a
file needs different handling, add a rule above the generic ones in `RULES`.

## Using the light artwork

Together with the [light colours](color-concept-light.md):

1. Use `colors_light.xmlinc` and `parameters_light.xmlinc` in `skin.xml`.
2. Install `src/skin/default/` as usual, then copy `src/skin/light/` over it.

I have not verified how the build installs these files, or run either theme on
a receiver.

## Known limits

- **Judged on contact sheets, not on a screen.** I reviewed every recoloured
  PNG directory on a Material surface colour, in both themes (menu icons in the
  light theme only). I have not seen them on a receiver, at real size, or over
  video.
- **SVGs are checked by diff only.** There was no SVG renderer available, so
  the 57 SVG files were verified by reading the changed colour values, not by
  looking at them. They use the same ramps as the PNGs.
- **One role per hue.** Multi-coloured icons are flattened to the role colours.
  This works for status icons but loses any intentional palette.
- **Light-theme orange.** `md_warning` is a deep amber (`#855300`) in the light
  theme, so orange timer icons look brownish.
- **Inverted shading.** In the light theme the highlights of glossy icons
  become dark, because the whole ramp is inverted.
- **Hard-coded asset colours.** Window corner and border PNGs are recoloured as
  neutral chrome, so their edge shade may not match `md_surface` exactly. Check
  the window frames after switching.
