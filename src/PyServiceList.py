# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0
#
# PROTOTYPE: a channel list that is drawn by the skin, not by the C++ eListboxServiceContent of enigma2.
#
# PyServiceList has the methods of Components.ServiceList.ServiceList, so that Screens.ChannelSelection (and whatever else uses its servicelist)
# works with it, but the list is an eListboxPythonMultiContent: the services are read with eServiceCenter, the rows are built in python (only the
# rows that are shown, see buildEntry) and the skin says how a row looks, with a template like the one of the TemplatedMultiContent converter.
#
# It is used instead of the C++ list when the plugin's skin is the primary skin and config.plugins.materialskincockpit.python_servicelist is
# on (off by default, there is no setup screen for it yet); install() puts it in place of Components.ServiceList.ServiceList.
#
# The template is the "template" attribute of the list widget: a python dict like the one of TemplatedMultiContent,
#
#     template="{'fonts': [gFont('Regular', 24), ...], 'itemHeight': 52, 'template': [MultiContentEntryText(pos=(0, 0), size=(300, 52), text=ROW_NAME), ...]}"
#
# or with several styles, {'fonts': [...], 'templates': {'default': (itemHeight, [entries]), 'two_lines': (itemHeight, [entries])}}: the one of
# "two_lines" is used if the two lines mode of the setup is on. What a row has is named by constants, see ROW_FIELDS: ROW_<FIELD> is the index of
# the field for a text or a pixmap (text=ROW_NAME), COLOR_<FIELD> for a color (color=COLOR_FG) and PERCENT_PROGRESS for the percent of a progress
# bar (percent=PERCENT_PROGRESS). A progress bar can't have its colors from the row (give them in the template), a row without an event has a
# PROGRESS of -1, which the listbox does not draw. The colors of a template are the skin's ones (names or numbers), as enigma2 has them: the first
# byte of a color is its transparency, 0 is not transparent. A skin without a template gets the one of defaultTemplate(), made
# from the attributes that the C++ list has (the fonts, itemHeight, sidesMargin, piconMargin, progressBarWidth ...) so that a skin works as it is.
#
# A horizontal list (a carousel of tiles): the skin gives listOrientation="horizontal" and the template has an "itemWidth" (or a style a third
# element, the width: 'default': (itemHeight, [entries], itemWidth)); the entries are those of one tile, which is itemWidth x itemHeight, and the list
# is as many tiles wide as fit in the widget. The keys left and right move by one tile (the native keys of the listbox), moveUp and moveDown of this
# class too (the listbox would take them for pages).
#
# Not done yet: the groups of the record indicator (a service group that has a recorded service), the channel numbers of moved services, the
# two-lines text of the C++ list (a template with two lines does it), "serviceitems_per_page" for a skin template (the template has fixed positions).

from json import dump, load
from os import makedirs, replace
from os.path import dirname
from time import localtime, strftime, time

from enigma import eListbox, eListboxPythonMultiContent, eServiceCenter, eServiceReference, eSize, gFont, RT_HALIGN_LEFT, RT_HALIGN_CENTER, RT_HALIGN_RIGHT, RT_VALIGN_CENTER, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_HALIGN_CENTER, BT_VALIGN_CENTER, BT_ALPHABLEND, RT_BLEND  # noqa: F401
from Components.ActionMap import ActionMap
from Components.GUIComponent import GUIComponent
from Components.config import config, ConfigYesNo
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryProgress, MultiContentEntryRectangle, MultiContentTemplateColor  # noqa: F401
from Components.Renderer.Picon import getPiconName
from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap
from skin import parseColor, parseFont, parseScale

from . import _
from .Debug import logger
from .Version import PLUGIN

settings = getattr(config.plugins, PLUGIN.lower())
settings.python_servicelist = ConfigYesNo(default=False)

# The fields of a row, in the order of the tuple that buildEntry returns. ROW_<NAME> is the index of a field.
ROW_FIELDS = (
    "REF",  # the eServiceReference
    "NAME",  # the name of a service; None for a marker or a folder (they have MARKER_NAME and DIRECTORY_NAME)
    "NUMBER",  # the channel number, "" if the service has none (or the setup hides it)
    "PICON",  # the picon (a pixmap), None if there is none or the setup has no picons
    "MARKER_NAME",  # the name of a marker, None for the other rows
    "DIRECTORY_NAME",  # the name of a folder (a bouquet, a provider), None for the other rows
    "EVENT",  # the name of the current event
    "NEXT_EVENT",  # the name of the next event
    "EVENT_TIME",  # "12:00 - 13:00"
    "NEXT_EVENT_TIME",  # the same for the next event
    "REMAINING",  # "23 min", the time that is left of the current event
    "PROGRESS",  # the percent of the current event that is over, 0 - 100; -1 if there is no event
    "PROGRESS_TEXT",  # "45%"
    "TYPE_ICON",  # a pixmap: the resolution (SD, HD, 4K), if the setup shows it
    "CRYPT_ICON",  # a pixmap: the service is encrypted, if the setup shows it
    "RECORD_ICON",  # a pixmap: the service is recorded now, if the setup shows it
    "FOLDER_ICON",  # a pixmap, of the rows of folders
    "MARKER_ICON",  # a pixmap, of the rows of markers
    "FG",  # colors, an int of enigma2 or None (= the one of the listbox): the text of the service, ...
    "FG_SELECTED",
    "BG",  # the background of the row (a rectangle that has it) if it is marked (selected for the multi-edit) or moved, else None
    "BG_SELECTED",
    "EVENT_FG",  # the text of the event
    "EVENT_FG_SELECTED",
    "REMAINING_FG",
    "REMAINING_FG_SELECTED",
    "FLAGS",  # the FLAG_* bits
)
ROW = {name: index for index, name in enumerate(ROW_FIELDS)}
COLOR = {name: MultiContentTemplateColor(index) for name, index in ROW.items()}  # a color of the row, in a template

FLAG_MARKER = 1
FLAG_DIRECTORY = 2
FLAG_PLAYABLE = 4
FLAG_RECORDED = 8
FLAG_CRYPTED = 16
FLAG_MARKED = 32
FLAG_UNAVAILABLE = 64
FLAG_FALLBACK = 128
FLAG_MOVING = 256

RECORDED_DEFAULT = 0x00b40431  # the colors of enigma2: the first byte is the transparency, 0 is not transparent
NOT_AVAILABLE_DEFAULT = 0x00bbbbbb

# the attributes of the list widget that the C++ list reads and the generic listbox doesn't have: they are taken out of the skin attributes
CPP_ATTRIBUTES = (
    "foregroundColorMarked", "foregroundColorMarkedSelected", "backgroundColorMarked", "backgroundColorMarkedSelected", "foregroundColorServiceNotAvail",
    "foregroundColorServiceSelected", "foregroundColorEvent", "foregroundColorNextEvent", "foregroundColorEventRemaining", "colorServiceDescription",
    "foregroundColorEventSelected", "foregroundColorEventNextSelected", "foregroundColorEventRemainingSelected", "colorServiceDescriptionSelected",
    "foregroundColorEventborder", "foregroundColorEventborderSelected", "colorEventProgressbar", "colorEventProgressbarSelected",
    "colorEventProgressbarBorder", "colorEventProgressbarBorderSelected", "colorServiceRecorded", "colorFallbackItem", "colorServiceSelectedFallback",
    "colorServiceDescriptionFallback", "colorServiceDescriptionSelectedFallback", "colorServiceNextDescriptionFallback",
    "colorServiceNextDescriptionSelectedFallback", "colorServiceRemainingDescriptionFallback", "colorServiceRemainingDescriptionSelectedFallback",
    "picServiceEventProgressbar", "serviceNameFont", "serviceInfoFont", "serviceRemainingInfoFont", "serviceNumberFont", "progressbarHeight",
    "progressbarBorderWidth", "progressBarWidth", "progressPercentWidth", "fieldMargins", "nonplayableMargins", "itemsDistances", "piconMargin",
    "sidesMargin", "textSeparator", "serviceEventSeparator", "itemHeightTwoLine", "itemHeight", "serviceItemHeight", "markerLine", "markerLineColor",
    "markerTextAlignment",
)

PIXMAPS = {
    "FOLDER": "icons/folder.png", "MARKER": "icons/marker.png", "DVB_S": "icons/ico_dvb-s.png", "DVB_C": "icons/ico_dvb-c.png", "DVB_T": "icons/ico_dvb-t.png",
    "STREAM": "icons/ico_stream.png", "CRYPT": "icons/icon_crypt.png", "RECORD": "icons/record.png", "HD": "icons/ico_hd-fs8.png",
    "SD": "icons/ico_sd-fs8.png", "UHD": "icons/ico_uhd-fs8.png",
}


STATE_FILE = f"/etc/enigma2/{PLUGIN}/lastselection.json"
_state = None


def selectionState():
    """The last genre and channel of each bouquet: the string of the bouquet -> {"genre": the string of the marker ("" for All), "channel": the string of the service}."""
    global _state  # pylint: disable=global-statement
    if _state is None:
        try:
            with open(STATE_FILE, encoding="utf-8") as fd:
                _state = load(fd)
        except (OSError, ValueError):
            _state = {}
        if not isinstance(_state, dict):
            _state = {}
    return _state


def writeSelectionState():
    """Writes the file, a new one that replaces the old one (a power failure does not leave half of it)."""
    try:
        makedirs(dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE + ".tmp", "w", encoding="utf-8") as fd:
            dump(selectionState(), fd)
        replace(STATE_FILE + ".tmp", STATE_FILE)
    except OSError as err:
        logger.error("%s not written: %r", STATE_FILE, err)


def isSkinActive():
    return dirname(config.skin.primary_skin.value) == PLUGIN


def color(value, default=None):
    """The ARGB int of a color name or value of the skin, default if there is none."""
    try:
        return parseColor(value).argb() if value else default
    except Exception:  # pylint: disable=broad-except
        return default


def defaultTemplate(width, height, values, fonts):
    """The entries of the template of a skin that has none: number, picon, name, event, progress, remaining time, the icons of the status. The sizes are from the
    attributes of the C++ list (values), fonts are the gFonts of the name, number, info and remaining time."""
    sides = values.get("sidesMargin", 0)
    margin = values.get("piconMargin", 4)
    numberWidth = int(fonts[1].pointSize * 3.4) if config.usage.show_channel_numbers_in_servicelist.value else 0
    piconWidth = int((height - 2 * margin) * 5 / 3) if config.usage.service_icon_enable.value else 0
    iconSize = max(height // 3, 12)
    progressMode = config.usage.show_event_progress_in_servicelist.value
    progressWidth = values.get("progressPercentWidth", 80) if "perc" in progressMode else values.get("progressBarWidth", 60)
    remainingWidth = int(fonts[3].pointSize * 5)
    gap = 12

    x = sides
    entries = [MultiContentEntryRectangle(pos=(0, 0), size=(width, height), backgroundColor=COLOR["BG"], backgroundColorSelected=COLOR["BG_SELECTED"], cornerRadius=values.get("itemCornerRadius", 0))]
    if numberWidth:
        entries.append(MultiContentEntryText(pos=(x, 0), size=(numberWidth, height), font=1, flags=RT_HALIGN_RIGHT | RT_VALIGN_CENTER, text=ROW["NUMBER"], color=COLOR["FG"], color_sel=COLOR["FG_SELECTED"]))
        x += numberWidth + gap
    if piconWidth:
        entries.append(MultiContentEntryPixmapAlphaBlend(pos=(x, margin), size=(piconWidth, height - 2 * margin), png=ROW["PICON"], flags=BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER))
        x += piconWidth + gap
    right = width - sides
    icons = []
    for field in ("RECORD_ICON", "CRYPT_ICON", "TYPE_ICON"):
        right -= iconSize + 4
        icons.append(MultiContentEntryPixmapAlphaBlend(pos=(right, (height - iconSize) // 2), size=(iconSize, iconSize), png=ROW[field], flags=BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER))
    entries += icons
    right -= gap
    nameWidth = max(int((right - x) * 0.38), 100)
    entries.append(MultiContentEntryText(pos=(x, 0), size=(nameWidth, height), font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=ROW["NAME"], color=COLOR["FG"], color_sel=COLOR["FG_SELECTED"]))
    entries.append(MultiContentEntryText(pos=(x, 0), size=(right - x, height), font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=ROW["DIRECTORY_NAME"], color=COLOR["FG"], color_sel=COLOR["FG_SELECTED"]))
    entries.append(MultiContentEntryText(pos=(sides, 0), size=(right - sides, height), font=0, flags=(RT_HALIGN_CENTER if values.get("markerTextAlignment") == "center" else RT_HALIGN_LEFT) | RT_VALIGN_CENTER, text=ROW["MARKER_NAME"], color=COLOR["FG"], color_sel=COLOR["FG_SELECTED"]))
    x += nameWidth + gap
    if progressMode != "no":
        entries.append(MultiContentEntryProgress(pos=(right - remainingWidth - gap - progressWidth, (height - values.get("progressbarHeight", 10)) // 2), size=(progressWidth, values.get("progressbarHeight", 10)), percent=-ROW["PROGRESS"], borderWidth=values.get("progressbarBorderWidth", 1), foreColor=values.get("colorEventProgressbar"), foreColorSelected=values.get("colorEventProgressbarSelected")))
    eventWidth = right - remainingWidth - gap - (progressWidth + gap if progressMode != "no" else 0) - x
    entries.append(MultiContentEntryText(pos=(x, 0), size=(max(eventWidth, 50), height), font=2, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=ROW["EVENT"], color=COLOR["EVENT_FG"], color_sel=COLOR["EVENT_FG_SELECTED"]))
    entries.append(MultiContentEntryText(pos=(right - remainingWidth, 0), size=(remainingWidth, height), font=3, flags=RT_HALIGN_RIGHT | RT_VALIGN_CENTER, text=ROW["REMAINING"], color=COLOR["REMAINING_FG"], color_sel=COLOR["REMAINING_FG_SELECTED"]))
    return entries


class ContentFacade:
    """What Screens.ChannelSelection calls on servicelist.l (the eListboxServiceContent of the C++ list): the rest is not needed here and ignored."""

    def __init__(self, owner):
        self.owner = owner
        self.ignored = set()

    def setHideNumberMarker(self, hide):
        self.owner.setHideNumberMarker(hide)

    def sort(self):
        self.owner.sort()

    def FillFinished(self):  # noqa: N802
        self.owner.finishFill()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self.ignored:
            self.ignored.add(name)
            logger.info("servicelist.l.%s is not supported", name)
        return lambda *args, **kwargs: None


class PyServiceList(GUIComponent):
    MODE_NORMAL = 0
    MODE_FAVOURITES = 1
    GUI_WIDGET = eListbox

    def __init__(self, serviceList):
        GUIComponent.__init__(self)
        self.serviceList = serviceList
        self.content = eListboxPythonMultiContent()
        self.content.setBuildFunc(self.buildEntry)
        self.l = ContentFacade(self)  # noqa: E741
        self.all = []  # the services of the root, in the order of the list
        self.shownRefs = []  # those of them that are shown (not the invisible ones, the markers with a number if the setup hides them)
        self.rows = []  # for the content: a one-tuple of the service for each visible one, buildEntry makes the row of it
        self.root = None
        self.mode = self.MODE_NORMAL
        self.filling = False
        self.cursor = 0
        self.marked = set()  # of ref.toString()
        self.currentMarked = False
        self.hideNumberMarker = False
        self.ignoreService = eServiceReference()
        self.onSelectionChanged = []
        self.onRootChanged = []  # called when the services of the list are new: a root was set, or its fill is finished
        self.focused = True  # the keys of the listbox are bound only while it is focused (see setFocus)
        self.values = {}  # the attributes of the C++ list that the skin has: name -> value, the colors, fonts and sizes parsed
        self.template = None  # the template that the skin has
        self.fonts = []
        self.scale = None
        self.listWidth = 0
        self.listHeight = 0
        self.listHeightOrig = 0
        self.listWidthOrig = 0
        self.itemHeight = 0
        self.itemWidth = 0
        self.horizontal = False
        self.pixmaps = {}
        self.piconNames = {}
        self.piconPixmaps = {}
        self.events = {}  # ref.toString() -> (valid until, event, next event)
        self.recordedAt = 0
        self.recorded = set()
        self.reported = set()
        self.genre = None  # a carousel shows the services of the section of this marker only, None: all of them (see setGenre)
        self.genreBar = None  # the list of the genres (PyGenreBar) of this one, if it has one

    # the skin

    def applySkin(self, desktop, parent):
        rest = []
        for attribute, value in self.skinAttributes:  # pylint: disable=access-member-before-definition
            if attribute == "template":
                try:
                    self.template = self.evalTemplate(value)
                except Exception as err:  # pylint: disable=broad-except
                    logger.error("template of the list is not valid, the default one is used: %r", err)
            elif attribute in CPP_ATTRIBUTES:
                self.values[attribute] = self.parseValue(attribute, value, parent)
            else:
                if attribute == "listOrientation":
                    self.horizontal = value in {"orHorizontal", "horizontal"}
                if attribute == "itemCornerRadius":  # the listbox has it, the default template needs it too
                    self.values[attribute] = parseScale(value)
                rest.append((attribute, value))
        self.skinAttributes = rest
        result = GUIComponent.applySkin(self, desktop, parent)
        self.listHeight = self.instance.size().height()
        self.listWidth = self.instance.size().width()
        self.listHeightOrig = self.listHeight
        self.listWidthOrig = self.listWidth
        self.scale = parent.scale
        self.setMode(self.mode)
        try:  # what the listbox has of the skin (a carousel that does not show: is it set at all, is the orientation the one of the skin)
            logger.info("%s: skin applied: attributes %s | orientation %s, carousel %s, size %s, item %sx%s", type(self).__name__, [name for name, _ in rest],
                        self.instance.getOrientation(), getattr(self.instance, "getCarousel", lambda: "not in this enigma2")(), self.instance.size().width(),
                        self.itemWidth, self.itemHeight)
        except Exception as err:  # pylint: disable=broad-except
            logger.info("%s: skin applied, the state of the listbox can not be read: %r", type(self).__name__, err)
        return result

    @staticmethod
    def parseValue(attribute, value, parent):
        if attribute.endswith("Font"):
            return parseFont(value, parent.scale)
        if attribute.startswith(("foregroundColor", "backgroundColor", "color")) or attribute == "markerLineColor":
            return color(value)
        if attribute in {"progressbarHeight", "progressbarBorderWidth", "progressBarWidth", "progressPercentWidth", "fieldMargins", "nonplayableMargins", "itemsDistances", "piconMargin", "sidesMargin", "itemHeightTwoLine", "itemHeight", "serviceItemHeight"}:
            return parseScale(value)
        return value

    def evalTemplate(self, text):
        """The template of the skin: its names are the ones of the TemplatedMultiContent converter and the ROW_* constants."""
        names = {"ROW_" + name: index for name, index in ROW.items()}
        names.update({"COLOR_" + name: value for name, value in COLOR.items()})
        names["PERCENT_PROGRESS"] = -ROW["PROGRESS"]
        names.update(gFont=gFont, parseFont=parseFont, MultiContentEntryText=MultiContentEntryText, MultiContentEntryPixmapAlphaBlend=MultiContentEntryPixmapAlphaBlend,
                     MultiContentEntryProgress=MultiContentEntryProgress, MultiContentEntryRectangle=MultiContentEntryRectangle, MultiContentTemplateColor=MultiContentTemplateColor,
                     RT_HALIGN_LEFT=RT_HALIGN_LEFT, RT_HALIGN_CENTER=RT_HALIGN_CENTER, RT_HALIGN_RIGHT=RT_HALIGN_RIGHT, RT_VALIGN_CENTER=RT_VALIGN_CENTER, RT_WRAP=RT_WRAP, RT_BLEND=RT_BLEND,
                     BT_SCALE=BT_SCALE, BT_KEEP_ASPECT_RATIO=BT_KEEP_ASPECT_RATIO, BT_HALIGN_CENTER=BT_HALIGN_CENTER, BT_VALIGN_CENTER=BT_VALIGN_CENTER, BT_ALPHABLEND=BT_ALPHABLEND)
        template = eval(text, {}, names)  # pylint: disable=eval-used
        if "fonts" not in template or ("template" not in template and "templates" not in template):
            raise ValueError("fonts and template or templates are needed")
        return template

    def setMode(self, mode=None):
        """Sets the template: the one of the skin, or the default one. Called when the setup of the list has changed (ChannelSelection, with a
        string for the mode, which is not needed here)."""
        if isinstance(mode, int):
            self.mode = mode
        if not self.instance:
            return
        twoLines = int(config.usage.servicelist_twolines.value)
        fonts = [self.values.get("serviceNameFont", gFont("Regular", 22)), self.values.get("serviceNumberFont", gFont("Regular", 22)),
                 self.values.get("serviceInfoFont", gFont("Regular", 18)), self.values.get("serviceRemainingInfoFont", gFont("Regular", 18))]
        if self.template:
            self.fonts = self.template["fonts"]
            styles = self.template.get("templates", {})
            style = styles.get("two_lines" if twoLines else "default") or styles.get("default")
            width = self.template.get("itemWidth")
            if style:
                height, entries = style[0], style[1]
                if len(style) > 2 and style[2] is not None:
                    width = style[2]
            else:
                height, entries = self.template["itemHeight"], self.template["template"]
            if self.scale and (self.scale[0][0] != self.scale[0][1] or self.scale[1][0] != self.scale[1][1]):
                entries, height, width = self.scaleTemplate(entries, height, width)
        else:
            width = None
            height = self.values.get("itemHeightTwoLine" if twoLines else "itemHeight", 52)
            rows = config.usage.serviceitems_per_page.value
            if rows > 0 and not twoLines:
                height = self.listHeightOrig // rows
            self.fonts = fonts
            entries = defaultTemplate(self.listWidth, height, self.values, fonts)
        for index, font in enumerate(self.fonts):
            self.content.setFont(index, font)
        self.content.setTemplate(entries)
        self.itemHeight = int(height)
        self.content.setItemHeight(self.itemHeight)
        if self.horizontal:
            self.itemWidth = int(width or self.listWidthOrig)
            self.content.setOrientation(eListbox.orHorizontal)
            self.content.setItemWidth(self.itemWidth)
            self.instance.resize(eSize(max(self.listWidthOrig // self.itemWidth, 1) * self.itemWidth, self.listHeightOrig))
            self.listWidth = self.instance.size().width()
            self.listHeight = self.listHeightOrig
        else:
            self.itemWidth = self.listWidth
            self.instance.resize(eSize(self.listWidth, self.listHeightOrig // self.itemHeight * self.itemHeight))
            self.listHeight = self.instance.size().height()
        self.content.invalidate()
        if self.horizontal and self.all:  # the services were set before the skin was applied: the markers are hidden now
            self.refresh(keep=True)

    def scaleTemplate(self, entries, height, width=None):
        """The template of a skin for the resolution of the screen, like TemplatedMultiContent does it."""
        vertical = self.scale[1][0] / self.scale[1][1]
        horizontal = self.scale[0][0] / self.scale[0][1]
        scaled = []
        for entry in entries:
            elements = list(entry)
            elements[1] = int(elements[1] * horizontal)
            elements[2] = int(elements[2] * vertical)
            elements[3] = int(elements[3] * horizontal)
            elements[4] = int(elements[4] * vertical)
            scaled.append(tuple(elements))
        self.fonts = [gFont(font.family, int(font.pointSize * vertical)) for font in self.fonts]
        return scaled, int(height * vertical), int(width * horizontal) if width else width

    setItemsPerPage = setMode  # noqa: N815

    def setFontsize(self):
        pass  # the fonts are the ones of the template: the font size of the setup of the list is for the C++ list

    def postWidgetCreate(self, instance):
        instance.setWrapAround(True)
        instance.setContent(self.content)
        instance.selectionChanged.get().append(self.selectionChanged)
        self.content.setList(self.rows)
        self.moveToIndex(self.cursor)

    def preWidgetRemove(self, instance):
        instance.setContent(None)
        instance.selectionChanged.get().remove(self.selectionChanged)

    def setFocus(self, focused):
        """Two lists on one screen (the bouquets and the services): the native keys (left, right ...) go to the focused one only."""
        self.focused = focused
        if self.instance is not None:
            self.instance.allowNativeKeys(focused)

    def selectionEnabled(self, enabled):
        if self.instance is not None:
            self.instance.setSelectionEnable(enabled)

    def getSelectionPosition(self):
        if self.horizontal:
            perPage = max(self.listWidth // self.itemWidth, 1)
            selx = self.instance.position().x() + self.itemWidth * (self.getCurrentIndex() % perPage)
            return selx, self.instance.position().y() + self.listHeight
        rowsPerPage = max(self.listHeight // self.itemHeight, 1)
        index = self.getCurrentIndex() % rowsPerPage
        sely = self.instance.position().y() + self.itemHeight * index
        if sely >= self.instance.position().y() + self.listHeight:
            sely -= self.listHeight
        return self.listWidth + self.instance.position().x(), sely

    # the selection

    def connectSelChanged(self, fnc):
        if fnc not in self.onSelectionChanged:
            self.onSelectionChanged.append(fnc)

    def disconnectSelChanged(self, fnc):
        if fnc in self.onSelectionChanged:
            self.onSelectionChanged.remove(fnc)

    def skipsMarkers(self):
        """In a carousel that shows all services the markers are tiles that the selection does not stop on (not while services are marked or moved)."""
        return self.horizontal and self.genre is None and not self.marked and not self.currentMarked

    def skipMarkers(self, index):
        """The selection is on a marker: it moves on in the direction of the move (the first service if it was set), wrapping around. True if it has moved."""
        count = len(self.shownRefs)
        if not self.skipsMarkers() or not 0 <= index < count or not self.shownRefs[index].flags & eServiceReference.isMarker:
            return False
        delta = index - self.cursor
        direction = (-1 if delta > 0 else 1) if abs(delta) > count // 2 else (1 if delta >= 0 else -1)  # a move from the first to the last one is a move back
        target = index
        for _step in range(count):
            if not self.shownRefs[target].flags & eServiceReference.isMarker:
                self.moveToIndex(target)  # selectionChanged is called again by the listbox
                return True
            target = (target + direction) % count
        return False  # only markers

    def selectionChanged(self):
        if self.instance:
            index = self.instance.getCurrentIndex()
            if self.skipMarkers(index):
                return
            self.cursor = index
        for fnc in self.onSelectionChanged:
            fnc()

    def getCurrentIndex(self):
        return self.instance.getCurrentIndex() if self.instance else self.cursor

    # What the Pager addon of the skin asks its list for (Components/Addons/Pager.py): the index of the selection and the number of rows.
    # Without them it asks servicelist.l, which ignores every call that the C++ list has and returns None for it: initPager then divided
    # None by the rows per page and enigma2 crashed when the channel list was shown.
    @property
    def index(self):
        return self.getCurrentIndex()

    @property
    def listCount(self):
        return len(self.shownRefs)

    def moveToIndex(self, index):
        index = max(min(index, len(self.shownRefs) - 1), 0)
        self.cursor = index
        if self.instance:
            self.instance.moveSelectionTo(index)

    def getCurrent(self):
        index = self.getCurrentIndex()
        return self.shownRefs[index] if 0 <= index < len(self.shownRefs) else eServiceReference()

    def neighbour(self, step):
        """The service before or after the current one in the list (wrapping around). The invisible ones count, as in the C++ list."""
        current = self.getCurrent()
        if not self.all or not current.valid():
            return eServiceReference()
        return self.all[(self.all.index(current) + step) % len(self.all)]

    def getPrev(self):
        return self.neighbour(-1)

    def getNext(self):
        return self.neighbour(1)

    def getList(self):
        return list(self.all)

    def atBegin(self):
        return self.instance.atBegin()

    def atEnd(self):
        return self.instance.atEnd()

    def moveUp(self):
        if self.currentMarked:
            self.moveCurrent(-1)
        else:  # in a horizontal list the listbox takes moveUp for a page
            self.instance.moveSelection(self.instance.prevItem if self.horizontal else self.instance.moveUp)

    def moveDown(self):
        if self.currentMarked:
            self.moveCurrent(1)
        else:
            self.instance.moveSelection(self.instance.nextItem if self.horizontal else self.instance.moveDown)

    def moveCurrent(self, step):
        """Move mode: the current service changes its place with the one before or after it, and stays the current one."""
        index = self.getCurrentIndex()
        other = index + step
        if not 0 <= other < len(self.shownRefs):
            return
        first, second = self.all.index(self.shownRefs[index]), self.all.index(self.shownRefs[other])
        self.all[first], self.all[second] = self.all[second], self.all[first]
        self.shownRefs[index], self.shownRefs[other] = self.shownRefs[other], self.shownRefs[index]
        self.rows[index], self.rows[other] = self.rows[other], self.rows[index]
        self.content.invalidate()
        self.moveToIndex(other)

    def moveToChar(self, char):
        """The first service whose name begins with char (upper or lower case: the first of them in the list)."""
        found = []
        for index, ref in enumerate(self.shownRefs):
            name = self.serviceName(ref)
            first = next((c for c in name if c.isprintable()), "")
            if first in (char, char.upper()):
                found.append(index)
        self.moveToIndex(found[0] if found else 0)

    def moveToNextMarker(self):
        index = self.getCurrentIndex()
        if self.horizontal and self.genreBar is not None:  # the next genre
            self.genreBar.step(1)
            return
        self.moveToIndex(next((i for i in range(index + 1, len(self.shownRefs)) if self.shownRefs[i].flags == eServiceReference.isMarker), len(self.shownRefs) - 1))

    def moveToPrevMarker(self):
        index = self.getCurrentIndex()
        if self.horizontal and self.genreBar is not None:  # the previous genre
            self.genreBar.step(-1)
            return
        markers = [i for i in range(index) if self.shownRefs[i].flags == eServiceReference.isMarker]
        if markers and markers[-1] + 1 == index:  # at the first service of a section: the marker before that one
            markers.pop()
        self.moveToIndex(markers[-1] if markers else 0)

    def setCurrent(self, ref, adjust=True):
        if self.select(ref):
            return None
        from Components.ServiceEventTracker import InfoBarCount  # pylint: disable=import-outside-toplevel
        if adjust and config.usage.multibouquet.value and InfoBarCount == 1 and ref and ref.type != 8192:
            logger.info("search for service in userbouquets")
            isRadio = ref.toString().startswith(("1:0:2:", "1:0:A:"))
            if self.serviceList:
                revertMode = config.servicelist.lastmode.value
                revertRoot = self.getRoot()
                if not isRadio:
                    self.serviceList.setModeTv()
                else:
                    self.serviceList.setModeRadio()
                revertSearchRoot = self.getRoot()
                for bouquet in self.serviceList.getBouquetList():
                    self.serviceList.enterUserbouquet(bouquet[1])
                    if self.select(ref):
                        config.servicelist.lastmode.save()
                        self.serviceList.saveChannel(ref)
                        return True
                self.serviceList.enterUserbouquet(revertSearchRoot)
                logger.info("service not found in any userbouquets")
                if revertMode == "tv":
                    self.serviceList.setModeTv()
                elif revertMode == "radio":
                    self.serviceList.setModeRadio()
                self.serviceList.enterUserbouquet(revertRoot)
        return False

    def selectShown(self, ref):
        """Makes the service the current one if it is shown."""
        for index, service in enumerate(self.shownRefs):
            if service == ref:
                self.moveToIndex(index)
                return True
        return False

    def select(self, ref):
        """Makes the service the current one if it is in the list. A service that is not of the genre that is shown is selected by showing all of them."""
        if self.selectShown(ref):
            return True
        if self.genre is not None and ref.valid() and ref in self.all:
            self.setGenre(None)
            if self.genreBar is not None:
                self.genreBar.update()
            return self.selectShown(ref)
        return False

    def setGenre(self, genre):
        """Shows the services of the section of a marker only, None: all of them. The current service stays the current one if it is of the section, else the first
        service of it is."""
        if genre is not None and not genre.valid():
            genre = None
        if (genre is None and self.genre is None) or (genre is not None and self.genre is not None and genre == self.genre):
            return
        self.genre = genre
        self.refresh(keep=True)
        self.selectionChanged()

    def sectionRefs(self):
        """The shown services of the section of the genre."""
        result = []
        inside = False
        for ref in self.all:
            if ref.flags & eServiceReference.isMarker:
                inside = ref == self.genre
            elif inside and not self.isHidden(ref):
                result.append(ref)
        return result

    # the services

    def getRoot(self):
        return self.root

    def getRootServices(self):
        services = eServiceCenter.getInstance().list(self.root)
        result = []
        while services is not None:
            service = services.getNext()
            if not service.valid():
                break
            result.append(service.toString())
        return result

    def setPlayableIgnoreService(self, ref):
        self.ignoreService = ref

    def setHideNumberMarker(self, hide):
        if hide != self.hideNumberMarker:
            self.hideNumberMarker = hide
            self.refresh(keep=True)

    def isHidden(self, ref):
        return bool(ref.flags & eServiceReference.isInvisible) or (not self.marked and self.hideNumberMarker and bool(ref.flags & eServiceReference.isNumberedMarker))

    def refresh(self, keep=False):
        """The shown services and the rows are made again from the list. keep: the current service stays the current one (where it is shown)."""
        current = self.getCurrent() if keep else None
        self.shownRefs = [ref for ref in self.all if not self.isHidden(ref)] if self.genre is None else self.sectionRefs()
        self.rows = [(ref,) for ref in self.shownRefs]
        self.content.setList(self.rows)
        self.cursor = 0
        if current is not None and current.valid() and self.selectShown(current):
            return
        if self.instance:
            self.instance.moveSelectionTo(0)
            self.skipMarkers(self.instance.getCurrentIndex())

    def setRoot(self, root, justSet=False):
        if self.root is None or root.toString() != self.root.toString():
            if self.genreBar is not None and self.root is not None:
                self.genreBar.remember()  # of the bouquet that is left
            self.genre = None  # the genres are the markers of the root
        self.root = root
        self.all = []
        self.currentMarked = False
        self.piconNames.clear()
        if justSet:
            self.filling = True  # the services come with addService, finishFill ends it
        else:
            services = eServiceCenter.getInstance().list(root)
            if services is None:
                logger.info("no list available for %s", root.toString())
            else:
                self.all = list(services.getContent("R", False))
            self.filling = False
            self.sort()  # also makes the rows
        self.selectionChanged()
        if not self.filling:
            self.rootChanged()

    def resetRoot(self):
        index = self.getCurrentIndex()
        self.setRoot(self.root, False)
        self.moveToIndex(index)

    def sort(self):
        """Sorts the services in the way the list that the root is would: the order that the sorted content of it has (the services that it
        doesn't have stay behind it, in the order that they were added: so a list that was filled with addService, with services that have another
        name than in the root, is not sorted yet)."""
        services = eServiceCenter.getInstance().list(self.root) if self.root else None
        if services is not None:
            order = {ref.toString(): index for index, ref in enumerate(services.getContent("R", True))}
            self.all.sort(key=lambda ref: order.get(ref.toString(), len(order)))
        self.refresh()

    def rootChanged(self):
        for fnc in list(self.onRootChanged):
            fnc()

    def finishFill(self):
        self.filling = False
        self.refresh()
        self.rootChanged()

    def addService(self, service, beforeCurrent=False):
        if beforeCurrent and self.all and self.shownRefs:
            current = self.getCurrent()
            self.all.insert(self.all.index(current) if current in self.all else 0, service)
        else:
            self.all.append(service)
        if not self.filling:
            self.refresh(keep=True)

    def removeCurrent(self):
        current = self.getCurrent()
        if current.valid() and current in self.all:
            index = self.getCurrentIndex()
            self.all.remove(current)
            self.currentMarked = False
            self.refresh()
            self.moveToIndex(index)

    # the marks (multi-edit) and the move mode

    def clearMarks(self):
        self.setMarks(set())

    def setMarks(self, marked):
        hiddenChanges = self.hideNumberMarker and bool(marked) != bool(self.marked)
        self.marked = marked
        if hiddenChanges:
            self.refresh(keep=True)
        else:
            self.content.invalidate()

    def isMarked(self, ref):
        return ref.toString() in self.marked

    def addMarked(self, ref):
        self.setMarks(self.marked | {ref.toString()})

    def removeMarked(self, ref):
        self.setMarks(self.marked - {ref.toString()})

    def getMarked(self):
        return sorted(self.marked)

    def setCurrentMarked(self, state):
        """Move mode: the current service is moved with the cursor. At the end the move is written to the list."""
        previous = self.currentMarked
        self.currentMarked = state
        if state == previous:
            return
        self.content.invalidate()
        if state:
            return
        current = self.getCurrent()
        services = eServiceCenter.getInstance().list(self.root)
        mutable = services.startEdit() if services is not None else None
        if mutable is None or not current.valid():
            logger.info("no editable list or no service selected")
            return
        if mutable.moveService(current, self.getCurrentIndex()):
            logger.info("move of %s failed", current.toString())

    # the rows

    def serviceName(self, ref):
        info = eServiceCenter.getInstance().info(ref)
        return (info and info.getName(ref)) or ref.getName() or ""

    def pixmap(self, name):
        if name not in self.pixmaps:
            self.pixmaps[name] = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, PIXMAPS[name]), cached=True)
        return self.pixmaps[name]

    def piconOf(self, ref):
        key = ref.toString()
        if key not in self.piconNames:
            path = getPiconName(key)
            self.piconNames[key] = path
            if path and path not in self.piconPixmaps:
                self.piconPixmaps[path] = LoadPixmap(path, cached=True)
        return self.piconPixmaps.get(self.piconNames[key])

    def recordedServices(self):
        """The services that are recorded now (looked up once in a second, a row asks for it)."""
        now = time()
        if now - self.recordedAt >= 1:
            self.recordedAt = now
            self.recorded = set()
            try:
                import NavigationInstance  # pylint: disable=import-outside-toplevel
                from RecordTimer import RecordTimerEntry  # pylint: disable=import-outside-toplevel
                self.recorded = {entry.service_ref.ref.toString() for entry in NavigationInstance.instance.RecordTimer.timer_list if entry.state == RecordTimerEntry.StateRunning and not entry.justplay}
            except Exception as err:  # pylint: disable=broad-except
                self.report("recorded services", err)
        return self.recorded

    def report(self, what, err):
        if what not in self.reported:  # once: a row is built many times
            self.reported.add(what)
            logger.error("%s: %r", what, err)

    def eventsOf(self, ref, info, now):
        """The current and the next event of a service, kept until the current one is over (a minute if there is none)."""
        key = ref.toString()
        cached = self.events.get(key)
        if cached and now < cached[0]:
            return cached[1], cached[2]
        event = nextEvent = None
        validUntil = now + 60
        try:
            event = info.getEvent(ref)
            if event:
                begin, duration = event.getBeginTime(), event.getDuration()
                if begin > 0 and duration > 0 and begin + duration > now:
                    validUntil = begin + duration
                nextEvent = info.getEvent(ref, begin + duration) if begin > 0 else None
        except Exception as err:  # pylint: disable=broad-except
            self.report("events", err)
        self.events[key] = (validUntil, event, nextEvent)
        return event, nextEvent

    def buildEntry(self, ref):
        """The row of a service, the tuple of the ROW_FIELDS. The listbox calls this for the rows it draws, each time it draws them."""
        values = self.values
        now = int(time())
        isMarker = bool(ref.flags & eServiceReference.isMarker)
        isDirectory = bool(ref.flags & eServiceReference.isDirectory)
        isPlayable = not (isDirectory or isMarker)
        flags = (FLAG_MARKER if isMarker else 0) | (FLAG_DIRECTORY if isDirectory else 0) | (FLAG_PLAYABLE if isPlayable else 0)
        marked = ref.toString() in self.marked
        moving = self.currentMarked and ref == self.getCurrent()
        info = eServiceCenter.getInstance().info(ref)
        name = (info and info.getName(ref)) or ref.getName() or ""

        fg = fgSelected = bg = bgSelected = None
        eventFg, eventFgSelected = values.get("colorServiceDescription"), values.get("colorServiceDescriptionSelected")
        remainingFg, remainingFgSelected = values.get("foregroundColorEventRemaining"), values.get("foregroundColorEventRemainingSelected")
        if marked or moving:
            flags |= FLAG_MOVING if moving else FLAG_MARKED
            bg, bgSelected = values.get("backgroundColorMarked"), values.get("backgroundColorMarkedSelected")
            fg, fgSelected = values.get("foregroundColorMarked"), values.get("foregroundColorMarkedSelected")
        if isPlayable and info and self.ignoreService.valid() and not marked:
            playable = info.isPlayable(ref, self.ignoreService)
            if playable == 0:
                flags |= FLAG_UNAVAILABLE
                fg = fgSelected = values.get("foregroundColorServiceNotAvail", NOT_AVAILABLE_DEFAULT)
            elif playable == 2:
                flags |= FLAG_FALLBACK
                fg = values.get("colorFallbackItem", fg)
                fgSelected = values.get("colorServiceSelectedFallback", fgSelected)

        recordMode = int(config.usage.record_indicator_mode.value)
        recordIcon = None
        if isPlayable and ref.toString() in self.recordedServices():
            flags |= FLAG_RECORDED
            if recordMode == 3:
                fg = fgSelected = values.get("colorServiceRecorded", RECORDED_DEFAULT)
            elif recordMode:
                recordIcon = self.pixmap("RECORD")

        number = ""
        if isPlayable and config.usage.show_channel_numbers_in_servicelist.value:
            try:
                number = str(ref.getChannelNum() or "")
            except AttributeError as err:  # not in the python interface of every image
                self.report("channel number", err)

        event = nextEvent = None
        if isPlayable and info:
            event, nextEvent = self.eventsOf(ref, info, now)
        eventName = event.getEventName() if event else ""
        eventTime = remaining = ""
        progress = -1  # no bar
        if event:
            begin, duration = event.getBeginTime(), event.getDuration()
            eventTime = f"{strftime('%H:%M', localtime(begin))} - {strftime('%H:%M', localtime(begin + duration))}"
            if duration > 0:
                progress = max(min((now - begin) * 100 // duration, 100), 0)
                remaining = _("%d min") % max((begin + duration - now) // 60, 0)
        nextName = nextEvent.getEventName() if nextEvent else ""
        nextTime = ""
        if nextEvent:
            nextBegin = nextEvent.getBeginTime()
            nextTime = f"{strftime('%H:%M', localtime(nextBegin))} - {strftime('%H:%M', localtime(nextBegin + nextEvent.getDuration()))}"

        typeIcon = cryptIcon = None
        if isPlayable:
            if int(config.usage.servicetype_icon_mode.value):
                resolution = ref.toString().split(":")[2].lower()
                typeIcon = self.pixmap("UHD" if resolution in {"1f", "20"} else "HD" if resolution in {"19", "11"} else "SD")
            if int(config.usage.crypto_icon_mode.value) and info and info.isCrypted():
                flags |= FLAG_CRYPTED
                cryptIcon = self.pixmap("CRYPT")
        picon = self.piconOf(ref) if isPlayable and config.usage.service_icon_enable.value else None

        return (ref, name if isPlayable else None, number, picon, name if isMarker else None, name if isDirectory else None, eventName, nextName, eventTime, nextTime, remaining,
                progress, f"{max(progress, 0)}%", typeIcon, cryptIcon, recordIcon, self.pixmap("FOLDER") if isDirectory else None, self.pixmap("MARKER") if isMarker else None,
                fg, fgSelected, bg, bgSelected, eventFg, eventFgSelected, remainingFg, remainingFgSelected, flags)


class PyBouquetBar(PyServiceList):
    """The bouquets as a (horizontal) list of their own beside the services: the widget "bouquetlist" of the channel selection. It shows the bouquet
    of the services list, and while it has the focus a move in it selects another bouquet. The rows are those of the folders of PyServiceList,
    so the template of a chip has a ROW_DIRECTORY_NAME."""

    def __init__(self, selection):
        PyServiceList.__init__(self, selection.servicelist)
        self.selection = selection
        self.focused = False
        self.syncing = False  # the list is made to show the bouquet: a change of the selection is not the user's

    def postWidgetCreate(self, instance):
        PyServiceList.postWidgetCreate(self, instance)
        instance.allowNativeKeys(self.focused)

    def update(self):
        """Shows the bouquets of the channel selection, and the one of its services list as the selected one."""
        if self.syncing:
            return
        self.syncing = True
        try:
            bouquets = self.selection.getBouquetList() or []
            refs = [ref for _name, ref in bouquets]
            if refs != self.all:
                self.all = refs
                self.refresh()
            self.select(self.selection.getRoot())
        except Exception as err:  # pylint: disable=broad-except
            self.report("bouquet bar", err)
        finally:
            self.syncing = False


class PyGenreBar(PyServiceList):
    """The markers of the services list as a (horizontal) list of their own above the services, the genres: the widget "genrelist" of the channel selection.
    The first one is "All" (an invalid reference: all services), the selected one is the genre that the services list shows: it has the services of the
    section of the marker only. It has no focus and not the keys of the listbox (left and right move in the services): the keys for the next and the previous
    marker move in it (see PyServiceList.moveToNextMarker). The template of a chip has a ROW_DIRECTORY_NAME."""

    def __init__(self, selection):
        PyServiceList.__init__(self, selection.servicelist)
        self.services = selection.servicelist  # the list of the services
        self.allGenres = eServiceReference()  # "All"
        self.focused = False
        self.syncing = False  # the list is made to show the section of the service: a change of the selection is not the user's
        self.restoredRoot = None  # the bouquet that has got its genre and channel back

    def postWidgetCreate(self, instance):
        PyServiceList.postWidgetCreate(self, instance)
        instance.setWrapAround(False)  # only the genres are shown, the empty slots after the last one stay empty
        instance.allowNativeKeys(self.focused)

    def isHidden(self, ref):
        return False  # the markers are what this list shows

    def skipsMarkers(self):
        return False

    def buildEntry(self, ref):
        row = [None] * len(ROW_FIELDS)
        row[ROW["NUMBER"]] = ""
        row[ROW["DIRECTORY_NAME"]] = self.serviceName(ref) if ref.valid() else _("All")
        row[ROW["PROGRESS"]] = -1
        row[ROW["FLAGS"]] = FLAG_DIRECTORY
        return tuple(row)

    def update(self):
        """Shows "All" and the markers of the services list, and the genre that the services list shows as the selected one."""
        if self.syncing:
            return
        self.syncing = True
        try:
            markers = [ref for ref in self.services.all if ref.flags & eServiceReference.isMarker]
            genres = [self.allGenres] + markers
            if genres != self.all:
                self.all = genres
                self.refresh()
            genre = self.services.genre
            if genre is not None and genre not in markers:  # the marker is gone
                self.services.setGenre(None)
                genre = None
            self.select(self.allGenres if genre is None else genre)
        except Exception as err:  # pylint: disable=broad-except
            self.report("genre bar", err)
        finally:
            self.syncing = False

    def remember(self):
        """Keeps the genre and the channel of the bouquet (written when they are new, this is called when the bouquet is left or the screen is hidden)."""
        root = self.services.getRoot()
        current = self.services.getCurrent()
        if root is None or not root.valid() or self.services.filling:
            return
        if all(ref.flags & eServiceReference.isDirectory for ref in self.services.all):
            return  # the list of the bouquets, which is shown for a moment when the bouquet is changed
        genre = self.services.genre
        entry = {"genre": genre.toString() if genre is not None else "", "channel": current.toString() if current.valid() else ""}
        state = selectionState()
        if state.get(root.toString()) != entry:
            state[root.toString()] = entry
            writeSelectionState()

    def restore(self):
        """Gives the bouquet its last genre and channel back (what the channel selection has selected by itself, the playing service, is replaced by it)."""
        root = self.services.getRoot()
        entry = selectionState().get(root.toString()) if root is not None and root.valid() and not self.services.filling else None
        if entry:
            genre = None
            if entry.get("genre"):
                genre = next((ref for ref in self.services.all if ref.flags & eServiceReference.isMarker and ref.toString() == entry["genre"]), None)
            self.services.setGenre(genre)  # a marker that is gone: all services
            channel = next((ref for ref in self.services.shownRefs if ref.toString() == entry.get("channel")), None)
            if channel is not None:
                self.services.selectShown(channel)
        self.update()

    def rootChanged(self):
        """The services list has a new root, or the same one with new services: a new bouquet gets its genre and channel back."""
        root = self.services.getRoot()
        key = root.toString() if root is not None else ""
        if key != self.restoredRoot:
            self.restoredRoot = key
            self.restore()
        else:
            self.update()

    def genreChanged(self):
        """The user has moved to another genre: the services list shows the services of it ("All": all of them)."""
        if not self.syncing:
            self.services.setGenre(self.getCurrent())

    def step(self, direction):
        """The key for the next or the previous marker: the next or the previous genre (the one after the last is "All")."""
        if self.shownRefs:
            self.moveToIndex((self.getCurrentIndex() + direction) % len(self.shownRefs))


def switchBouquet(selection, bouquet):
    """The services list of the channel selection shows another bouquet: what ChannelSelectionBase.changeBouquet does, for a bouquet that is given."""
    bouquets = selection.bouquetBar
    if selection.pathChangeDisabled or not bouquet.valid() or bouquet == selection.getRoot():
        return
    bouquets.syncing = True
    try:
        if selection.inBouquet() and len(selection.servicePath) > 1:
            selection.pathUp()  # the list of the bouquets
            selection.servicelist.setCurrent(bouquet, adjust=False)
            selection.enterPath(selection.getCurrentSelection())
            previous = None
            root = selection.getRoot()
            for path in selection.history:  # the service that was the current one of this bouquet
                if len(path) > 2 and path[1] == root:
                    previous = path[2]
            if previous is not None:
                selection.setCurrentSelection(previous)
        else:
            selection.enterUserbouquet(bouquet)
    finally:
        bouquets.syncing = False
        bouquets.update()


def bouquetBarChanged(selection):
    bouquets = selection.bouquetBar
    if not bouquets.syncing and bouquets.focused:
        switchBouquet(selection, bouquets.getCurrent())


def attachBouquetBar(selection):
    """Adds the bouquet list ("bouquetlist" of the skin, if it has one)."""
    bouquets = PyBouquetBar(selection)
    selection["bouquetlist"] = bouquets
    selection.bouquetBar = bouquets
    selection.servicelist.onRootChanged.append(bouquets.update)
    bouquets.onSelectionChanged.append(boundFunction(bouquetBarChanged, selection))
    selection.onShown.append(bouquets.update)


def attachGenreBar(selection):
    """Adds the genre list ("genrelist" of the skin). It has no focus: left and right move in the services, the keys for the next and the previous marker in the genres."""
    genres = selection["genrelist"] = selection.genreBar = PyGenreBar(selection)
    selection.servicelist.onRootChanged.append(genres.rootChanged)
    selection.servicelist.genreBar = genres
    genres.onSelectionChanged.append(genres.genreChanged)
    selection.onShown.append(genres.restore)
    selection.onHide.append(genres.remember)
    selection.onClose.append(genres.remember)


def enableCarouselKeys(selection):
    selection["CarouselKeyActions"].setEnabled(selection.servicelist.horizontal)  # known when the skin is applied


def attachCarouselKeys(selection):
    """Up and down are the same as left and right in a carousel (the listbox takes them for a page). Not in a list that is vertical, where they are the keys of the listbox."""
    selection["CarouselKeyActions"] = ActionMap(["DirectionActions"], {"up": selection.servicelist.moveUp, "down": selection.servicelist.moveDown}, prio=2)
    selection.onShown.append(boundFunction(enableCarouselKeys, selection))


def installBouquetBar(selection):
    """Screens.ChannelSelection: ChannelSelectionBase gets the bouquet list and the genre list if its services list is a PyServiceList."""
    base = selection.ChannelSelectionBase
    if getattr(base, "isBouquetBarInstalled", False):
        return
    originalInit = base.__init__

    def init(self, *args, **kwargs):
        originalInit(self, *args, **kwargs)
        if isinstance(getattr(self, "servicelist", None), PyServiceList):
            try:
                attachBouquetBar(self)
                attachGenreBar(self)
                attachCarouselKeys(self)
            except Exception:  # pylint: disable=broad-except
                logger.exception("bouquet list not attached")

    base.__init__ = init
    base.isBouquetBarInstalled = True


def install():
    """Puts PyServiceList in place of Components.ServiceList.ServiceList where the plugin's skin is the primary skin and the setting is on."""
    import Components.ServiceList as module  # pylint: disable=import-outside-toplevel
    original = module.ServiceList
    if getattr(original, "isPyServiceListFactory", False):
        return

    def createServiceList(serviceList):
        if settings.python_servicelist.value and isSkinActive():
            try:
                return PyServiceList(serviceList)
            except Exception as err:  # pylint: disable=broad-except
                logger.error("PyServiceList failed, the list of enigma2 is used: %r", err)
        return original(serviceList)

    createServiceList.isPyServiceListFactory = True
    # The name stands for the class where it is imported: Screens.ChannelSelection reads ServiceList.MODE_NORMAL and
    # ServiceList.MODE_FAVOURITES from it (setRoot), which a function does not have - enigma2 crashed at the start with
    # "'function' object has no attribute 'MODE_FAVOURITES'". The constants of the class go with it.
    for name in dir(original):
        if name.isupper():
            setattr(createServiceList, name, getattr(original, name))
    module.ServiceList = createServiceList
    try:
        import Screens.ChannelSelection as selection  # pylint: disable=import-outside-toplevel
        if getattr(selection, "ServiceList", None) is original:  # it has been imported with the name already
            selection.ServiceList = createServiceList
        installBouquetBar(selection)
    except ImportError as err:
        logger.error("Screens.ChannelSelection: %r", err)
