# Skin structure

How the sources in `src/skin/default/` are put together. The compiler features used here
(frames, `center`, `origin="screen"`, screen families, `$screen_center`) are described in the
SkinForge wiki, page "XML+ compiler".

## Layers

```
skin.yml                      lists the screens (and families of screens)
 └ screen_X.ymlinc            one screen: a frame, plus what is inside it
    └ screenpart_Window_*     a frame: a window size class (Small, Medium, Wide, Large, Full)
       └ screenpart_WindowChrome   background, title bar, clock, logo, key bar
          └ screenpart_WindowBase  the two background panels and the key bar
```

* **Frames** (`screenpart_Window_*.ymlinc`, root `frame: "true"`) are the size classes. Their
  size comes from `frames.ymlinc` (`window_medium_width`, ...); the content area of a class
  (`window_medium_content_x`, `..._content_width`, pager and list heights) is defined there too.
* A screen places its frame with `position: "center"` and positions everything else
  **relative to the frame**. A frame offset is never written into a screen; the lint
  (`tools/lint_frame_offsets.py`) fails if one is.
* Things that really belong to the screen, not the frame, say `origin: "screen"`.
* **Parts** (`screenpart_*`) sit at their own origin: the top-left of their content is 0,0 and
  the includer's `position` carries the offset. A part that is given a `size` can use
  `$width`/`$height`; other attributes on the include become variables (`clock_font`, ...).
  *Template* = used by several screens, *Panel* = content of one screen.
* **Screens that differ only in name (and title)** are a `screenfamily` in `skin.yml`, not
  one file each.
* Positions that follow the screen size use `$screen_width`, `$screen_height` and
  `$screen_center`, not `e`, `c` or `center`.

## Checks

* `tools/lint_frame_offsets.py` - no pasted frame offsets.
* `tools/unused_sources.py` - source files nothing reaches from `skin.yml` (`--delete` removes them).
* A refactor is verified by compiling before and after (`xmlinc.py`) and comparing the
  result; it should be identical.

## Known exceptions

* `screen_PluginBrowser` / `screen_PluginDownloadBrowser`: the `Window_Wide` frame is at
  `252,111`, 10px above the centre.
* `screen_ChannelSelectionRadio`: its frame is at `0,0`, the TV channel list's is centred.
* `screenpart_WlanStatusPanel`: the `Statustext` label is off-screen to the left, so the part
  does not start at its origin.
* `screenpart_MenuTemplate` builds its frame in a Python applet, with coordinates in the code.
* `screenpart_RcPanel`: hidden arrows at -100,-100.
