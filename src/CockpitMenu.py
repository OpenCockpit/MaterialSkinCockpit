# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0
#
# A cockpit menu. The MENU key opens a menu of the entries of the menu tree that the user has picked; the whole tree (the main menu, as it was
# before) is opened by the MENU key of that menu. It is a Screens.Menu.Menu, so the skin draws it like any other menu (the grid of the skin
# if the setting "Menu style" is "Horizontal"), and the entries are the ones of the tree, made by the same Menu.addItem / Menu.addMenu: the
# conditions of menu.xml (requires, conditional, the setup level), the translations, the icons (menuicons) and the actions are the same.
#
# The cockpit items are, in the order in which they were picked, in config.plugins.materialskincockpit.cockpit (a JSON list):
#   - the keys of an entry on the way down from the main menu ("timermenu", "setup/system/skin_setup"); the last key may also be the id of an
#     entry that a plugin adds to that menu (WHERE_MENU);
#   - "plugin:<id>" for a plugin of the list of the plugins (WHERE_PLUGINMENU, like MovieCockpit) and "extension:<id>" for one of the
#     extensions (WHERE_EXTENSIONSMENU, the blue key of the infobar); the id is the name in lower case, with "_" for the blanks, like
#     enigma2 makes it for the plugins of the menus;
#   - "bouquet:<service reference>" for a bouquet of the TV: it opens the channel selection on that bouquet (see openBouquet);
#   - "service:<bouquet reference> >> <service reference>" for a channel of a bouquet of the TV: it zaps to the channel (see zapService),
#     in that bouquet, as the channel selection does.
# A cockpit item that is not there (a plugin that is not installed) is skipped. The icon of an entry is the one of menuicons for its key: a
# plugin needs a menuicon with its id (moviecockpit), or it gets the puzzle piece (the menuicon "plugin"), not the question mark.
#
# Nothing is defined in the settings the first time (the setting is empty, not "[]", which is a cockpit that the user has emptied): the
# cockpit is then filled once, see initialCockpit, with up to 7 bouquets of the TV (the upper list) and up to 7 plugins that the user has
# installed (the lower list). From then on it is the user's.
#
# In the cockpit menu PREVIOUS / NEXT (the keys that move an entry in the list of the plugins) move the selected cockpit item up or down, the
# four colour keys open the cockpit item that is assigned to them (config.plugins.materialskincockpit.cockpit_buttons, a JSON dict colour ->
# path of a cockpit item; the name of the item is the label of the key in the footer), MENU opens the menu tree (the main menu) and TEXT
# (TXT) opens a choice of the three editors:
#   - the cockpit editor is the menu tree, level by level, with the lists of the plugins and of the extensions as menus of their own:
#     OK (and YELLOW) adds / removes the selected entry, a menu as well, RIGHT opens a menu; a cockpit item that is removed leaves the colour keys;
#   - the bouquet editor lists the bouquets of the TV: OK (and YELLOW) adds / removes the selected one, RIGHT opens a bouquet, to add /
#     remove its channels;
#   - the button editor has a row for each colour key: OK chooses the cockpit item of the key (or none).
# The cockpit menu opens with the cursor on the cockpit item that it was on when it was left or an entry was opened
# (config.plugins.materialskincockpit.cockpit_last, the path of the cockpit item).
#
# With the menus drawn as grids ("Menu style" "Horizontal") and a skin that has the screen MenuHorizontal_cockpit (SPLIT_SKIN) the menu
# is two lists, each a source of the screen with its own grid: the bouquets and the channels above (UPPER, "Cockpit - Media") and everything else below
# (LOWER, "Cockpit - Menu/Plugins"). Only the list that has the cursor (self.active) has a selection and the focus; CHANNEL UP / DOWN
# move the cursor between them (setActive), the title says which list it is in, and OK, PREVIOUS / NEXT, the description and the saved
# position all work on that list. With one list (the list style of the menus, another skin) all entries are in LOWER, as before.
#
# It is used instead of the main menu if the plugin's skin is the primary skin and config.plugins.materialskincockpit.cockpit_menu is on
# (on by default, there is no setup screen for it yet); install() puts it in place of InfoBarMenu.mainMenu. If the cockpit cannot be
# opened the main menu is.

import json
from os.path import dirname
from xml.etree.ElementTree import Element

from enigma import eServiceCenter, eServiceReference
from Plugins.Plugin import PluginDescriptor
from Tools.BoundFunction import boundFunction
from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile, ConfigYesNo, ConfigText
from Components.PluginComponent import plugins
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.ChoiceBox import ChoiceBox
from Screens.Menu import Menu, MainMenu, MenuEntryPixmap, mdom
from skin import findSkinScreen, menuicons

from . import _
from .Debug import logger
from .Version import PLUGIN

PLUGIN_PREFIX = "plugin:"
EXTENSION_PREFIX = "extension:"
BOUQUET_PREFIX = "bouquet:"
BOUQUET_ICON = "bouquet"
BOUQUET_CHOSEN = "bouquet"  # what the cockpit menu closes with when a bouquet was chosen (see install)
SERVICE_PREFIX = "service:"  # a channel: its bouquet and its reference, one after the other, SERVICE_SEP between them
SERVICE_SEP = " >> "
SERVICE_ICON = "channel"
SERVICE_CHOSEN = "service"  # what it closes with when a channel was chosen: (SERVICE_CHOSEN, bouquet reference, service reference)
MEDIA_PREFIXES = (BOUQUET_PREFIX, SERVICE_PREFIX)  # the cockpit items of the upper list
UPPER = "bouquets"  # the two lists of the cockpit menu in the skin: the bouquets and channels above, ...
LOWER = "menu"  # ... everything else below (the list of every menu)
SPLIT_SKIN = "MenuHorizontal_cockpit"  # the screen of the skin with the two lists
PLUGIN_ICON = "plugin"  # the menuicon of a plugin that has none of its own
BUTTONS = ("red", "green", "yellow", "blue")
INITIAL_COUNT = 7  # how many bouquets and how many plugins the cockpit starts with
PACKAGE_PREFIX = "enigma2-plugin-"  # the packages of the plugins: enigma2-plugin-<category>-<name>, like enigma2-plugin-extensions-moviecockpit

settings = getattr(config.plugins, PLUGIN.lower())
settings.cockpit_menu = ConfigYesNo(default=True)
settings.cockpit = ConfigText(default="", fixed_size=False)  # empty: nothing defined yet, see loadCockpit
settings.cockpit_buttons = ConfigText(default="{}", fixed_size=False)
settings.cockpit_last = ConfigText(default="", fixed_size=False)  # the path of the cockpit that the cursor was on, see CockpitMenu


def isSkinActive():
    return dirname(config.skin.primary_skin.value) == PLUGIN


initial = {"nothing": False}  # the first filling found nothing to put in (no bouquets, no plugins): it is not tried again on every call


def loadCockpit():
    """The paths of the cockpit items (see above). While nothing is defined (an empty setting, or one that is not a list) the cockpit is filled
    with initialCockpit and that is stored: the first time the cockpit menu or one of its editors is made."""
    if settings.cockpit.value:
        try:
            paths = json.loads(settings.cockpit.value)
        except ValueError:
            paths = None
        if isinstance(paths, list):
            return [path for path in paths if isinstance(path, str) and path]
    if initial["nothing"]:
        return []
    paths = initialCockpit()
    if paths:
        saveCockpit(paths)
    else:
        initial["nothing"] = True
    return paths


def saveCockpit(paths):
    settings.cockpit.value = json.dumps(paths)
    settings.cockpit.save()
    configfile.save()


def loadButtons():
    """colour -> path of the cockpit item that the colour key opens."""
    try:
        buttons = json.loads(settings.cockpit_buttons.value)
    except ValueError:
        return {}
    if not isinstance(buttons, dict):
        return {}
    return {color: path for color, path in buttons.items() if color in BUTTONS and isinstance(path, str) and path}


def saveButtons(buttons):
    settings.cockpit_buttons.value = json.dumps(buttons)
    settings.cockpit_buttons.save()
    configfile.save()


def menuNodes(parent):
    """The entries of a menu node of menu.xml: the items and the sub menus (they have a key)."""
    return [node for node in parent if node.tag in {"item", "menu"} and node.get("key")]


def pluginId(name):
    return name.lower().replace(" ", "_")


def iconKey(pluginid):
    """The key of the entry of a plugin, which is what the menu takes its icon by: the id if the skin has an icon for it."""
    return pluginid if pluginid in menuicons else PLUGIN_ICON


# the lists of plugins: the prefix of the path of a cockpit item, where the plugins are shown, the title of the list in the editor
PLUGIN_KINDS = (
    (PLUGIN_PREFIX, PluginDescriptor.WHERE_PLUGINMENU, "Plugin list"),
    (EXTENSION_PREFIX, PluginDescriptor.WHERE_EXTENSIONSMENU, "Extensions"),
)


def listedPlugins(prefix):
    """(id, descriptor) of the plugins of one kind."""
    where = next(where for kindPrefix, where, _title in PLUGIN_KINDS if kindPrefix == prefix)
    return [(pluginId(plugin.name), plugin) for plugin in plugins.getPlugins(where)]


def runPlugin(session, plugin, extension):
    """As the list of the plugins starts a plugin, and the infobar an extension (some of them want the servicelist as well)."""
    infobar = getattr(session, "infobar", None)
    if extension and infobar is not None and hasattr(infobar, "runPlugin"):
        infobar.runPlugin(plugin)
    else:
        plugin(session=session)


def pluginEntry(menu, prefix, pluginid, plugin):
    key = iconKey(pluginid)
    return (plugin.name, boundFunction(runPlugin, menu.session, plugin, prefix == EXTENSION_PREFIX), key, 50, plugin.description, MenuEntryPixmap(key, menu.png_cache))


def menuPluginEntries(menu, menuID):
    """(id, entry) of the entries that plugins add to a menu, made as Menu.createMenuList makes them (the key of the entry is the one of its icon)."""
    entries = []
    for plugin, description in plugins.getPluginsForMenuWithDescription(menuID):
        key = iconKey(plugin[2])
        entries.append((plugin[2], (plugin[0], boundFunction(plugin[1], menu.session, close=menu.close), key, plugin[3] or 50, description, MenuEntryPixmap(key, menu.png_cache))))
    return entries


def tvBouquets():
    """(name, service reference) of the bouquets of the TV, the way the channel selection lists them: the list of the bouquets with the
    setting "multibouquet" on, else the one bouquet of the favourites. The channel selection itself is not asked: it would have to be put
    into its TV mode for that, and this is called whenever the cockpit menu is made."""
    handler = eServiceCenter.getInstance()
    if not config.usage.multibouquet.value:
        from Screens.ChannelSelection import service_types_tv  # pylint: disable=import-outside-toplevel
        root = eServiceReference(f'{service_types_tv} FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet')
        info = handler.info(root)
        return [(info.getName(root), root.toString())] if info else []
    content = handler.list(eServiceReference('1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'))
    bouquets = []
    while content:
        ref = content.getNext()
        if not ref.valid():
            break
        if ref.flags & eServiceReference.isDirectory and not ref.flags & eServiceReference.isInvisible:
            info = handler.info(ref)
            if info:
                bouquets.append((info.getName(ref), ref.toString()))
    return bouquets


def pluginListOrder():
    """The plugins of the plugin list in the order the plugin browser shows them: the order the user has given them, then the rest."""
    listed = list(plugins.getPlugins(PluginDescriptor.WHERE_PLUGINMENU))
    order = getattr(getattr(config.misc, "pluginbrowser", None), "plugin_order", None)
    ordered = []
    for path in order.value.split(",") if order is not None else []:
        plugin = next((plugin for plugin in listed if getattr(plugin, "path", "")[24:] == path), None)  # [24:]: without /usr/lib/enigma2/python/
        if plugin is not None:
            ordered.append(plugin)
            listed.remove(plugin)
    return ordered + listed


def packageKey(category, name):
    """What a package and the folder of a plugin have in common: the category (extensions, systemplugins) and the name without - or _."""
    return category.lower(), name.lower().replace("-", "").replace("_", "").replace(" ", "")


def userInstalledPlugins():
    """(id, descriptor) of the plugins of the plugin list that the user has installed, in the order of the plugin browser. The packages are
    those that enigma2 lists as "User installed plugins" (Components.UserInstalledPackages: the installed packages, without the ones of the
    image and without what they depend on); a plugin belongs to the package of its folder (.../Plugins/Extensions/MovieCockpit is
    enigma2-plugin-extensions-moviecockpit). Asking for the packages takes a moment (opkg), so this is for the first filling only."""
    packages = []
    try:
        from Components.UserInstalledPackages import UserInstalledPackages  # pylint: disable=import-outside-toplevel
        UserInstalledPackages().run(packages.extend)
    except Exception as err:  # pylint: disable=broad-except
        logger.error("user installed packages: %r", err)
        return []
    keys = set()
    for package in packages:
        if package.startswith(PACKAGE_PREFIX):
            category, __separator, name = package[len(PACKAGE_PREFIX):].partition("-")
            keys.add(packageKey(category, name))
    found = []
    seen = set()
    for plugin in pluginListOrder():
        folders = getattr(plugin, "path", "").rstrip("/").split("/")
        pluginid = pluginId(plugin.name)
        if len(folders) >= 2 and packageKey(folders[-2], folders[-1]) in keys and pluginid not in seen:
            seen.add(pluginid)
            found.append((pluginid, plugin))
    return found


def initialCockpit():
    """The cockpit of a box where nothing is defined: up to INITIAL_COUNT bouquets of the TV (the upper list of the cockpit menu), in the order
    of the channel selection, then up to INITIAL_COUNT plugins that the user has installed (the lower list)."""
    try:
        bouquets = [BOUQUET_PREFIX + ref for __name, ref in tvBouquets()[:INITIAL_COUNT]]
    except Exception as err:  # pylint: disable=broad-except
        logger.error("bouquets of the TV: %r", err)
        bouquets = []
    return bouquets + [PLUGIN_PREFIX + pluginid for pluginid, __plugin in userInstalledPlugins()[:INITIAL_COUNT]]


def bouquetEntry(menu, name, ref):
    """The entry of a bouquet: choosing it closes the cockpit menu with (BOUQUET_CHOSEN, ref), the infobar then opens the channel selection
    (the channel selection is a dialog of the infobar, not a screen to open on top of the menu: the menu would be behind the channels)."""
    return (name, boundFunction(menu.close, (BOUQUET_CHOSEN, ref)), BOUQUET_ICON, 50, _("Channel list"), MenuEntryPixmap(BOUQUET_ICON, menu.png_cache))


def openBouquet(infobar, ref):
    """The channel selection of the infobar, in the TV mode, on the bouquet *ref*."""
    servicelist = getattr(infobar, "servicelist", None)
    if servicelist is None:
        return
    servicelist.setModeTv()
    servicelist.enterUserbouquet(eServiceReference(ref))
    infobar.session.execDialog(servicelist)


def servicePath(bouquet, service):
    """The path of the cockpit item of a channel *service* (a reference) in the bouquet *bouquet*."""
    return SERVICE_PREFIX + bouquet + SERVICE_SEP + service


def bouquetServices(bouquet):
    """(name, service reference) of the channels of a bouquet of the TV, in its order: the entries that can be played, not the markers
    (the names of the sections) or the sub directories."""
    handler = eServiceCenter.getInstance()
    content = handler.list(eServiceReference(bouquet))
    services = []
    while content:
        ref = content.getNext()
        if not ref.valid():
            break
        if ref.flags & (eServiceReference.isDirectory | eServiceReference.isMarker):
            continue
        info = handler.info(ref)
        services.append(((info.getName(ref) if info else "") or ref.getName(), ref.toString()))
    return services


def findService(bouquet, service):
    """The name of the channel *service* in the bouquet *bouquet*, None if it is not in it (any more). Only the one entry asks for its name:
    a bouquet may have hundreds."""
    handler = eServiceCenter.getInstance()
    content = handler.list(eServiceReference(bouquet))
    while content:
        ref = content.getNext()
        if not ref.valid():
            return None
        if ref.toString() == service and not ref.flags & (eServiceReference.isDirectory | eServiceReference.isMarker):
            info = handler.info(ref)
            return (info.getName(ref) if info else "") or ref.getName()
    return None


def serviceEntry(menu, name, bouquet, service):
    """The entry of a channel: choosing it closes the cockpit menu with (SERVICE_CHOSEN, bouquet, service), the infobar then zaps (as for the
    bouquets, see bouquetEntry)."""
    return (name, boundFunction(menu.close, (SERVICE_CHOSEN, bouquet, service)), SERVICE_ICON, 50, _("Channel"), MenuEntryPixmap(SERVICE_ICON, menu.png_cache))


def zapService(infobar, bouquet, service):
    """Zaps to the channel *service* the way the channel selection does: it is selected in the bouquet *bouquet* of the TV, then zapped to."""
    servicelist = getattr(infobar, "servicelist", None)
    if servicelist is None:
        return
    servicelist.setModeTv()
    servicelist.enterUserbouquet(eServiceReference(bouquet))
    infobar.zapToService(eServiceReference(service), eServiceReference(bouquet))


def xmlEntry(menu, node):
    """The entry of a node of menu.xml, None if it is not there on this box (requires, conditional)."""
    if int(node.get("level", 0)) > config.usage.setup_level.index:
        return None
    entry = []
    if node.tag == "menu":
        menu.addMenu(entry, node)
    else:
        menu.addItem(entry, node)
    return entry[0] if entry else None


def resolve(menu, path):
    """The entry (text, action, key, weight, description, icon) of a cockpit item, None if there is none (it is gone, or the plugin is not installed)."""
    for prefix, _where, _title in PLUGIN_KINDS:
        if path.startswith(prefix):
            return next((pluginEntry(menu, prefix, pluginid, plugin) for pluginid, plugin in listedPlugins(prefix) if pluginid == path[len(prefix):]), None)
    if path.startswith(BOUQUET_PREFIX):
        return next((bouquetEntry(menu, name, ref) for name, ref in tvBouquets() if ref == path[len(BOUQUET_PREFIX):]), None)
    if path.startswith(SERVICE_PREFIX):
        bouquet, separator, service = path[len(SERVICE_PREFIX):].partition(SERVICE_SEP)
        name = findService(bouquet, service) if separator else None
        return serviceEntry(menu, name, bouquet, service) if name else None
    node = mdom.getroot()
    keys = path.split("/")
    for index, key in enumerate(keys):
        child = next((candidate for candidate in menuNodes(node) if candidate.get("key") == key), None)
        if child is None:
            if index == len(keys) - 1:  # an entry that a plugin adds to this menu
                return next((entry for pluginid, entry in menuPluginEntries(menu, node.get("key")) if pluginid == key), None)
            return None
        node = child
    return xmlEntry(menu, node)


def setMenuList(menu, name=LOWER, items=None):
    """The end of Menu.createMenuList: the list goes to the screen. *name* is the list of the screen that gets *items* (menu.list for
    the list "menu", the one of the menus; the numbers of "show numbers" are only for that one)."""
    if name == LOWER:
        if config.usage.menu_show_numbers.value:
            menu.list = [(str(x[0] + 1) + " " + x[1][0], x[1][1], x[1][2]) for x in enumerate(menu.list)]
        items = menu.list
        if menu.menulength != len(items):  # updateList must only be used on a list of the same length
            menu.menulength = len(items)
            menu[name].setList(items)
    elif getattr(menu, "upperLength", None) != len(items):
        menu.upperLength = len(items)
        menu[name].setList(items)
    menu[name].updateList(items)
    menu.screenContentChanged()


class CockpitMenu(Menu):
    """The cockpit menu."""

    def __init__(self, session):
        self.paths = []  # the path of the cockpit item of each entry of the list (of the lower one, if there are two)
        self.upperPaths = []  # the paths of the bouquets (the upper list), if the skin has the two lists
        self.split = False  # two lists: the bouquets above (UPPER), everything else below (LOWER); else one list with all
        self.active = LOWER  # the list that has the cursor
        Menu.__init__(self, session, Element("menu", {"key": "cockpit", "text": _("Cockpit")}))
        # Menu opens the only entry of a menu at once (the hook is added to onExecBegin in Menu.__init__): not here. A single cockpit item
        # would be opened as soon as the cockpit menu is opened, and the choice of the MENU key (the menu, the editors) could not be reached.
        onlyEntry = getattr(self, "_Menu__onExecBegin", None)
        if onlyEntry in self.onExecBegin:
            self.onExecBegin.remove(onlyEntry)
        self["key_previous"] = StaticText(_("Move up"))
        self["key_next"] = StaticText(_("Move down"))
        self["key_menu"] = StaticText(_("MENU"))  # the footer shows a key only if its source has a text
        self["key_text"] = StaticText(_("TEXT"))
        for color in BUTTONS[:-1]:  # the blue one is the one of Menu
            self["key_" + color] = StaticText("")
        self.updateButtons()
        self["moveActions"] = HelpableActionMap(self, ["DirectionActions"], {
            "shiftUp": (boundFunction(self.moveCockpit, -1), _("Move the current cockpit item up")),
            "shiftDown": (boundFunction(self.moveCockpit, 1), _("Move the current cockpit item down")),
        }, prio=-1, description=_("Cockpit Actions"))
        self["cockpitActions"] = HelpableActionMap(self, ["ColorActions", "MenuActions"], {
            "red": (boundFunction(self.keyButton, "red"), _("Open the cockpit item of the red button")),
            "green": (boundFunction(self.keyButton, "green"), _("Open the cockpit item of the green button")),
            "yellow": (boundFunction(self.keyButton, "yellow"), _("Open the cockpit item of the yellow button")),
            "blue": (boundFunction(self.keyButton, "blue"), _("Open the cockpit item of the blue button")),
            "menu": (self.openMainMenu, _("Open the menu")),
        }, prio=-1, description=_("Cockpit Actions"))
        # the key TEXT, as the movie selection takes it (the action showText of the keymap context InfobarActions)
        self["textActions"] = HelpableActionMap(self, "InfobarActions", {
            "showText": (self.keyText, _("Open the cockpit editor, the bouquet editor or the button editor")),
        }, prio=-1, description=_("Cockpit Actions"))
        self["listActions"] = HelpableActionMap(self, ["NavigationActions"], {  # the keys CHANNEL UP / DOWN
            "pageUp": (self.keyUpperList, _("Jump to the media list (the bouquets)")),
            "pageDown": (self.keyLowerList, _("Jump to the functions list")),
        }, prio=-1, description=_("Cockpit Actions"))
        self.onLayoutFinish.append(self.restorePosition)  # the list of the screen exists now
        self.onShown.append(self.reapplyActive)  # the converter of a list says "selection on" when it builds the list, maybe after the first setActive
        self.onClose.append(self.savePosition)

    def activePaths(self):
        """The paths of the list that has the cursor."""
        return self.upperPaths if self.split and self.active == UPPER else self.paths

    def activeSource(self):
        return self[UPPER if self.split and self.active == UPPER else LOWER]

    def currentPath(self):
        """The path of the selected entry, "" if there is no selection."""
        index = self.activeSource().getIndex()
        paths = self.activePaths()
        return paths[index] if index is not None and 0 <= index < len(paths) else ""

    def currentEntry(self):
        return self.activeSource().getCurrent()

    def listRenderer(self, name):
        """The listbox of the skin that shows the list *name*: the renderer whose source (a converter, which has the list as its source)
        leads to it. None while the screen has no skin yet."""
        source = self[name]
        for renderer in getattr(self, "renderer", []):
            behind = getattr(renderer, "source", None)
            while behind is not None and behind is not source:
                behind = getattr(behind, "source", None)
            if behind is source and hasattr(renderer, "selection_enabled"):
                return renderer
        return None

    def setActive(self, name):
        """Gives the cursor to the list *name*: only that list has a selection (the tile of the cursor), the keys of the screen go
        to it, and the title says which list it is. With one list there is nothing to do."""
        if not self.split:
            return
        self.active = name
        for other in (UPPER, LOWER):
            renderer = self.listRenderer(other)
            if renderer is not None:
                # The renderer takes "selectionEnabled" from its converter on every change of the list (Listbox.changed): a renderer set
                # alone would be enabled again by the updateList below (and by every later one), and both lists would show a tile.
                renderer.source.selectionEnabled = other == name
                renderer.selection_enabled = other == name
                if other == name:
                    self.setFocus(renderer)
            self[other].updateList(self[other].list)  # the tiles of the list that lost / got the cursor are made again
        title = _("Cockpit - Channels") if name == UPPER else _("Cockpit - Menu")
        self.setTitle(title)
        self["title"].text = title
        self.updateDescription()

    def reapplyActive(self):
        """The list that has the cursor again: its selection on, the other one's off, the focus and the title."""
        if self.split:
            self.setActive(self.active)

    def keyUpperList(self):
        """CHANNEL UP: the bouquets, if there are any."""
        if not self.split or not self.upperPaths:
            return 0  # not used: the page up key of the list
        self.setActive(UPPER)
        return None

    def keyLowerList(self):
        """CHANNEL DOWN: the functions, if there are any."""
        if not self.split or not self.paths:
            return 0
        self.setActive(LOWER)
        return None

    def updateDescription(self):
        """The description of the selected entry of the list that has the cursor (Menu looks at the one list "menu")."""
        entry = self.currentEntry()
        self["description"].text = entry[4] if entry and len(entry) > 4 and entry[4] else ""

    def savePosition(self):
        """Remembers the cockpit item that the cursor is on (by its path: the list can change), for the next time the cockpit menu is opened.
        Only a change is written: the settings file is on the flash."""
        path = self.currentPath()
        if path and path != settings.cockpit_last.value:
            settings.cockpit_last.value = path
            settings.cockpit_last.save()
            configfile.save()

    def selectPath(self, path):
        """Puts the cursor on the entry with *path* (in the list that has it); False if no list has such an entry."""
        if path in self.paths:
            self[LOWER].setIndex(self.paths.index(path))
            self.setActive(LOWER)
            return True
        if path in self.upperPaths:
            self[UPPER].setIndex(self.upperPaths.index(path))
            self.setActive(UPPER)
            return True
        return False

    def restorePosition(self):
        """Puts the cursor on the cockpit item of the last time, if it is still there; else on the list with something in it (the functions
        first): the keys and the title are those of the list that has the cursor."""
        if not self.selectPath(settings.cockpit_last.value):
            self.setActive(LOWER if self.paths or not self.upperPaths else UPPER)

    def okbuttonClick(self):
        self.savePosition()  # an entry may restart the GUI or close the screen without a chance to save later
        if self.split and self.active == UPPER:
            entry = self.currentEntry()
            if entry and entry[1]:
                entry[1]()
            return
        Menu.okbuttonClick(self)

    def createMenuList(self):
        self.menuID = self.parentmenu.get("key")
        # two lists if the skin has the screen for them and the menus are drawn as grids: the bouquets above, the rest below
        self.split = bool(getattr(self, "menuHorizontal", False) and findSkinScreen(SPLIT_SKIN))
        self.list = []
        self.paths = []
        upper = []
        self.upperPaths = []
        for path in loadCockpit():
            entry = resolve(self, path)
            if not entry:
                continue
            if self.split and path.startswith(MEDIA_PREFIXES):
                upper.append(entry)
                self.upperPaths.append(path)
            else:
                self.list.append(entry)
                self.paths.append(path)
        if self.split:
            if UPPER not in self:  # a source of its own for the skin; its selection changes the description like the one of the menu
                self[UPPER] = List([])
                self[UPPER].onSelectionChanged.append(self.updateDescription)
            setMenuList(self, UPPER, upper)
        setMenuList(self)
        if "key_red" in self:  # not yet while Menu makes the screen
            self.updateButtons()

    def updateButtons(self):
        """The footer shows the name of the cockpit item of each colour key."""
        buttons = loadButtons()
        for color in BUTTONS:
            entry = resolve(self, buttons[color]) if color in buttons else None
            self["key_" + color].text = entry[0] if entry else ""

    def keyButton(self, color):
        path = loadButtons().get(color)
        entry = resolve(self, path) if path else None
        if entry is None:
            return 0  # nothing assigned: the key is not used
        entry[1]()
        return None

    def keyText(self):
        self.session.openWithCallback(self.editorChosen, ChoiceBox, title=_("Cockpit"), windowTitle=_("Cockpit"),
                                      list=[(_("Cockpit Editor"), "editor"), (_("Bouquet Editor"), "bouquets"), (_("Button Editor"), "buttons")])

    def editorChosen(self, choice):
        """One of the editors."""
        if not choice:
            return
        if choice[1] == "bouquets":
            self.session.openWithCallback(self.editorClosed, CockpitEditor, bouquetsLevel())
        else:
            self.session.openWithCallback(self.editorClosed, CockpitEditor if choice[1] == "editor" else ButtonEditor)

    def moveCockpit(self, direction):
        """Moves the selected cockpit item one place, the first one up to the end and the last one down to the start, like the list of the plugins."""
        paths = self.activePaths()  # the entries move within their own list
        index = self.activeSource().getIndex()
        count = len(paths)
        if count < 2 or index is None or index >= count:  # nothing to move
            return
        target = (index + direction) % count
        order = list(paths)
        order.insert(target, order.pop(index))
        cockpit = loadCockpit()
        slots = [slot for slot, path in enumerate(cockpit) if path in paths]  # the entries that are not there keep their places
        for slot, path in zip(slots, order):
            cockpit[slot] = path
        saveCockpit(cockpit)
        self.createMenuList()
        self.activeSource().setIndex(target)

    def openMainMenu(self):
        self.session.openWithCallback(self.menuClosed, MainMenu, mdom.getroot())

    def keyBlue(self):
        return 0  # the blue key is a colour key like the others (keyButton)

    def editorClosed(self, *_res):
        """The editors may have changed the cockpit items: the list is made again, with the cursor on the cockpit item that it was on (if the
        editor removed that one, on the entry that took its place)."""
        path = self.currentPath()
        index = self.activeSource().getIndex() or 0
        self.createMenuList()
        if self.selectPath(path):
            return
        paths = self.activePaths()
        if paths:
            self.activeSource().setIndex(min(index, len(paths) - 1))
        elif self.split and (self.paths or self.upperPaths):  # the list that had the cursor is empty now: the other one gets it
            self.setActive(LOWER if self.paths else UPPER)
            self.activeSource().setIndex(0)

    def isProtected(self):
        """The cockpit menu is a way into the main menu: the PIN of the main menu is asked for it as well."""
        return bool(config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.main_menu.value and not (hasattr(self.session, "infobar") and self.session.infobar is None))


class Level:
    """One menu of the editor: its title and the function that makes its rows, (entry, path, the level that it opens or None)."""

    def __init__(self, title, rows):
        self.title = title
        self.rows = rows


def treeLevel(node, keys, title):
    def rows(menu):
        result = []
        taken = set()
        for child in menuNodes(node):
            entry = xmlEntry(menu, child)
            if not entry:
                continue  # not on this box
            taken.add(child.get("key"))
            childKeys = keys + [child.get("key")]
            # (false positive: astroid does not narrow xmlEntry's "entry or None" across the "if not entry" above)
            # pylint: disable-next=unsubscriptable-object
            result.append((entry, "/".join(childKeys), treeLevel(child, childKeys, entry[0]) if child.tag == "menu" else None))
        for pluginid, entry in menuPluginEntries(menu, node.get("key")):
            if pluginid not in taken:
                result.append((entry, "/".join(keys + [pluginid]), None))
        return result
    return Level(title, rows)


def pluginsLevel(prefix, title):
    def rows(menu):
        return [(pluginEntry(menu, prefix, pluginid, plugin), prefix + pluginid, None) for pluginid, plugin in listedPlugins(prefix)]
    return Level(title, rows)


def channelsLevel(title, bouquet):
    """The channels of one bouquet, for the bouquet editor."""
    def rows(menu):
        return [(serviceEntry(menu, name, bouquet, service), servicePath(bouquet, service), None) for name, service in bouquetServices(bouquet)]
    return Level(title, rows)


def bouquetsLevel():
    """The bouquets of the TV, for the bouquet editor: OK adds / removes a bouquet, RIGHT opens it to add / remove its channels."""
    def rows(menu):
        return [(bouquetEntry(menu, name, ref), BOUQUET_PREFIX + ref, channelsLevel(name, ref)) for name, ref in tvBouquets()]
    return Level(_("Bouquet Editor"), rows)


def rootLevel():
    """The menu tree, then the lists of plugins and of extensions as menus."""
    tree = treeLevel(mdom.getroot(), [], _("Edit cockpit items"))

    def rows(menu):
        result = tree.rows(menu)
        for prefix, _where, title in PLUGIN_KINDS:
            level = pluginsLevel(prefix, _(title))
            result.append(((level.title, None, "plugin_selection", 900, "", MenuEntryPixmap("plugin_selection", menu.png_cache)), "", level))
        return result
    return Level(tree.title, rows)


class CockpitEditor(Menu):
    """A menu of the tree: OK (and YELLOW) adds / removes the selected entry, a menu as well; RIGHT opens a menu."""

    def __init__(self, session, level=None):
        self.level = level or rootLevel()
        self.paths = []  # the path of each row ("" for the lists of plugins)
        self.levels = []  # the menu that each row opens (None for an entry)
        self.okbuttontext = _("Add the selected entry as a cockpit item or remove it")
        self.exitbuttontext = _("Back")
        Menu.__init__(self, session, Element("menu", {"key": "cockpit_edit", "text": self.level.title}))
        self.skinName = ["Menu"]  # a long list: always the list of the skin, not the grid
        self["key_yellow"] = StaticText(_("Add/remove"))
        self["editActions"] = HelpableActionMap(self, ["ColorActions"], {
            "yellow": (self.toggleCurrent, _("Add the selected entry as a cockpit item or remove it")),
        }, prio=-1, description=_("Cockpit Actions"))
        self["enterActions"] = HelpableActionMap(self, ["DirectionActions"], {
            "right": (self.enterCurrent, _("Open the selected menu")),
        }, prio=-1, description=_("Cockpit Actions"))

    def createMenuList(self):
        self["key_blue"].text = ""
        self.menuID = self.parentmenu.get("key")
        cockpit = loadCockpit()
        self.list = []
        self.paths = []
        self.levels = []
        for entry, path, child in self.level.rows(self):
            text, _action, key, weight, description, icon = entry
            mark = "[x] " if path in cockpit else "[   ] "
            if child:
                # OK takes a menu in or out of the cockpit items, RIGHT opens it; the lists of plugins have no path of their own: OK opens them
                action = boundFunction(self.toggle, path) if path else boundFunction(self.enter, child)
                self.list.append(((mark if path else "") + text + "  >", action, key, weight, description, icon))
            else:
                self.list.append((mark + text, boundFunction(self.toggle, path), key, weight, description, icon))
            self.paths.append(path)
            self.levels.append(child)
        setMenuList(self)

    def enter(self, level):
        self.session.openWithCallback(self.levelClosed, CockpitEditor, level)

    def enterCurrent(self):
        index = self["menu"].getIndex()
        if index is None or not 0 <= index < len(self.levels) or not self.levels[index]:
            return 0  # an entry, not a menu: the key is not used
        self.enter(self.levels[index])
        return None

    def levelClosed(self, *res):
        if res and res[0]:
            self.close(True)
        else:
            self.refresh()

    def toggleCurrent(self):
        index = self["menu"].getIndex()
        if 0 <= index < len(self.paths) and self.paths[index]:  # the lists of plugins have no path of their own
            self.toggle(self.paths[index])

    def toggle(self, path):
        cockpit = loadCockpit()
        if path in cockpit:
            cockpit.remove(path)
            buttons = loadButtons()
            freed = [color for color, target in buttons.items() if target == path]
            if freed:  # a colour key does not keep a cockpit item that is gone
                for color in freed:
                    del buttons[color]
                saveButtons(buttons)
        else:
            cockpit.append(path)
        saveCockpit(cockpit)
        self.refresh()

    def refresh(self):
        index = self["menu"].getIndex()
        self.createMenuList()
        self["menu"].setIndex(index)

    def keyBlue(self):
        return 0


class ButtonEditor(Menu):
    """A row for each colour key: OK chooses the cockpit item that the key opens."""

    def __init__(self, session):
        self.okbuttontext = _("Choose the cockpit item of the button")
        self.exitbuttontext = _("Back")
        Menu.__init__(self, session, Element("menu", {"key": "cockpit_buttons", "text": _("Button Editor")}))
        self.skinName = ["Menu"]

    def createMenuList(self):
        self["key_blue"].text = ""
        self.menuID = self.parentmenu.get("key")
        buttons = loadButtons()
        names = {"red": _("Red"), "green": _("Green"), "yellow": _("Yellow"), "blue": _("Blue")}
        self.list = []
        for color in BUTTONS:
            entry = resolve(self, buttons[color]) if color in buttons else None
            self.list.append((f"{names[color]}: {entry[0] if entry else _('None')}", boundFunction(self.choose, color), "button_" + color, 50,
                              _("OK chooses the cockpit item of this button"), MenuEntryPixmap("button_" + color, self.png_cache)))
        setMenuList(self)

    def choose(self, color):
        current = loadButtons().get(color, "")
        choices = [(_("None"), "")]
        for path in loadCockpit():
            entry = resolve(self, path)
            if entry:
                choices.append((entry[0], path))
        selection = next((index for index, choice in enumerate(choices) if choice[1] == current), 0)
        self.session.openWithCallback(boundFunction(self.chosen, color), ChoiceBox, title=_("Cockpit item of the button"), windowTitle=_("Button Editor"),
                                      list=choices, selection=selection)

    def chosen(self, color, choice):
        if choice is None:  # cancelled
            return
        buttons = loadButtons()
        if choice[1]:
            buttons[color] = choice[1]
        else:
            buttons.pop(color, None)
        saveButtons(buttons)
        index = self["menu"].getIndex()
        self.createMenuList()
        self["menu"].setIndex(index)

    def keyBlue(self):
        return 0


def install():
    """The MENU key opens the cockpit menu where the plugin's skin is the primary skin and the setting is on."""
    from Screens.InfoBarGenerics import InfoBarMenu  # pylint: disable=import-outside-toplevel
    original = InfoBarMenu.mainMenu
    if getattr(original, "isCockpitHook", False):
        return

    def cockpitClosed(self, *val):
        self.mainMenuClosed(*val)
        result = val[0] if val and isinstance(val[0], tuple) else ()
        if len(result) == 2 and result[0] == BOUQUET_CHOSEN:  # a bouquet was chosen
            openBouquet(self, result[1])
        elif len(result) == 3 and result[0] == SERVICE_CHOSEN:  # a channel was chosen
            zapService(self, result[1], result[2])

    def mainMenu(self):
        if settings.cockpit_menu.value and isSkinActive():
            logger.info("MENU: cockpit")
            self.session.infobar = self  # as InfoBarMenu.mainMenu does: screens opened from the menu use it
            try:
                self.session.openWithCallback(boundFunction(cockpitClosed, self), CockpitMenu)
                return
            except Exception:  # pylint: disable=broad-except
                logger.exception("the cockpit could not be opened, the main menu is")
        else:
            logger.info("MENU: main menu (cockpit_menu is %s, skin %s)", settings.cockpit_menu.value, config.skin.primary_skin.value)
        original(self)

    mainMenu.isCockpitHook = True
    InfoBarMenu.mainMenu = mainMenu
    logger.info("MENU opens the cockpit if config.plugins.%s.cockpit_menu is on", PLUGIN.lower())
