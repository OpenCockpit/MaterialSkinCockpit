# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0
#
# A favorites menu. The MENU key opens a menu of the entries of the menu tree that the user has picked, and an entry "Menu" that
# opens the whole tree (the main menu) as before. It is a Screens.Menu.Menu, so the skin draws it like any other menu (the grid of the skin
# if the setting "Menu style" is "Horizontal"), and the entries are the ones of the tree, made by the same Menu.addItem / Menu.addMenu: the
# conditions of menu.xml (requires, conditional, the setup level), the translations, the icons (menuicons) and the actions are the same.
#
# The favorites are, in the order in which they were picked, in config.plugins.materialskincockpit.favorites (a JSON list):
#   - the keys of an entry on the way down from the main menu ("timermenu", "setup/system/skin_setup"); the last key may also be the id of an
#     entry that a plugin adds to that menu (WHERE_MENU);
#   - "plugin:<id>" for a plugin of the list of the plugins (WHERE_PLUGINMENU, like MovieCockpit) and "extension:<id>" for one of the
#     extensions (WHERE_EXTENSIONSMENU, the blue key of the infobar); the id is the name in lower case, with "_" for the blanks, like
#     enigma2 makes it for the plugins of the menus.
# A favorite that is not there (a plugin that is not installed) is skipped. The icon of an entry is the one of menuicons for its key: a
# plugin needs a menuicon with its id (moviecockpit), or it gets the puzzle piece (the menuicon "plugin"), not the question mark.
#
# In the favorites menu PREVIOUS / NEXT (the keys that move an entry in the list of the plugins) move the selected favorite up or down, the
# four colour keys open the favorite that is assigned to them (config.plugins.materialskincockpit.favorites_buttons, a JSON dict colour ->
# path of a favorite; the name of the favorite is the label of the key in the footer), and MENU opens a choice of the two editors:
#   - the favorites editor is the menu tree, level by level, with the lists of the plugins and of the extensions as menus of their own:
#     OK opens a menu or adds / removes an entry, YELLOW adds / removes the selected entry, a menu as well;
#   - the button editor has a row for each colour key: OK chooses the favorite of the key (or none).
#
# It is used instead of the main menu if the plugin's skin is the primary skin and config.plugins.materialskincockpit.favorites_menu is on
# (on by default, there is no setup screen for it yet); install() puts it in place of InfoBarMenu.mainMenu. If the favorites cannot be
# opened the main menu is.

import json
from os.path import dirname
from xml.etree.ElementTree import Element

from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile, ConfigYesNo, ConfigText
from Components.PluginComponent import plugins
from Components.Sources.StaticText import StaticText
from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.Menu import Menu, MainMenu, MenuEntryPixmap, mdom
from skin import menuicons
from Tools.BoundFunction import boundFunction

from . import _
from .Debug import logger
from .Version import PLUGIN

PLUGIN_PREFIX = "plugin:"
EXTENSION_PREFIX = "extension:"
PLUGIN_ICON = "plugin"  # the menuicon of a plugin that has none of its own
BUTTONS = ("red", "green", "yellow", "blue")
DEFAULT_FAVORITES = ["timermenu", PLUGIN_PREFIX + "moviecockpit"]

settings = getattr(config.plugins, PLUGIN.lower())
settings.favorites_menu = ConfigYesNo(default=True)
settings.favorites = ConfigText(default=json.dumps(DEFAULT_FAVORITES), fixed_size=False)
settings.favorites_buttons = ConfigText(default="{}", fixed_size=False)


def isSkinActive():
    return dirname(config.skin.primary_skin.value) == PLUGIN


def loadFavorites():
    """The paths of the favorites (see above)."""
    try:
        paths = json.loads(settings.favorites.value)
    except ValueError:
        return list(DEFAULT_FAVORITES)
    if not isinstance(paths, list):
        return list(DEFAULT_FAVORITES)
    return [path for path in paths if isinstance(path, str) and path]


def saveFavorites(paths):
    settings.favorites.value = json.dumps(paths)
    settings.favorites.save()
    configfile.save()


def loadButtons():
    """colour -> path of the favorite that the colour key opens."""
    try:
        buttons = json.loads(settings.favorites_buttons.value)
    except ValueError:
        return {}
    if not isinstance(buttons, dict):
        return {}
    return {color: path for color, path in buttons.items() if color in BUTTONS and isinstance(path, str) and path}


def saveButtons(buttons):
    settings.favorites_buttons.value = json.dumps(buttons)
    settings.favorites_buttons.save()
    configfile.save()


def menuNodes(parent):
    """The entries of a menu node of menu.xml: the items and the sub menus (they have a key)."""
    return [node for node in parent if node.tag in ("item", "menu") and node.get("key")]


def pluginId(name):
    return name.lower().replace(" ", "_")


def iconKey(pluginid):
    """The key of the entry of a plugin, which is what the menu takes its icon by: the id if the skin has an icon for it."""
    return pluginid if pluginid in menuicons else PLUGIN_ICON


# the lists of plugins: the prefix of the path of a favorite, where the plugins are shown, the title of the list in the editor
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
    """The entry (text, action, key, weight, description, icon) of a favorite, None if there is none (it is gone, or the plugin is not installed)."""
    for prefix, _where, _title in PLUGIN_KINDS:
        if path.startswith(prefix):
            return next((pluginEntry(menu, prefix, pluginid, plugin) for pluginid, plugin in listedPlugins(prefix) if pluginid == path[len(prefix):]), None)
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


def setMenuList(menu):
    """The end of Menu.createMenuList: the list goes to the screen."""
    if config.usage.menu_show_numbers.value:
        menu.list = [(str(x[0] + 1) + " " + x[1][0], x[1][1], x[1][2]) for x in enumerate(menu.list)]
    if menu.menulength != len(menu.list):  # updateList must only be used on a list of the same length
        menu.menulength = len(menu.list)
        menu["menu"].setList(menu.list)
    menu["menu"].updateList(menu.list)
    menu.screenContentChanged()


class FavoritesMenu(Menu):
    """The favorites and the entry that opens the main menu."""

    def __init__(self, session):
        self.paths = []  # the favorite of each entry of the list (the last entry, Menu, is none)
        Menu.__init__(self, session, Element("menu", {"key": "favorites", "text": _("Favorites")}))
        self["key_previous"] = StaticText(_("Move up"))
        self["key_next"] = StaticText(_("Move down"))
        self["key_menu"] = StaticText(_("MENU"))  # the footer shows a key only if its source has a text
        for color in BUTTONS[:-1]:  # the blue one is the one of Menu
            self["key_" + color] = StaticText("")
        self.updateButtons()
        self["moveActions"] = HelpableActionMap(self, ["DirectionActions"],
        {
            "shiftUp": (boundFunction(self.moveFavorite, -1), _("Move the current favorite up")),
            "shiftDown": (boundFunction(self.moveFavorite, 1), _("Move the current favorite down")),
        }, prio=-1, description=_("Favorites Actions"))
        self["favoritesActions"] = HelpableActionMap(self, ["ColorActions", "MenuActions"],
        {
            "red": (boundFunction(self.keyButton, "red"), _("Open the favorite of the red button")),
            "green": (boundFunction(self.keyButton, "green"), _("Open the favorite of the green button")),
            "yellow": (boundFunction(self.keyButton, "yellow"), _("Open the favorite of the yellow button")),
            "blue": (boundFunction(self.keyButton, "blue"), _("Open the favorite of the blue button")),
            "menu": (self.keyMenu, _("Open the favorites editor or the button editor")),
        }, prio=-1, description=_("Favorites Actions"))

    def createMenuList(self):
        self.menuID = self.parentmenu.get("key")
        self.list = []
        self.paths = []
        for path in loadFavorites():
            entry = resolve(self, path)
            if entry:
                self.list.append(entry)
                self.paths.append(path)
        self.list.append((_("Menu"), self.openMainMenu, "mainmenu", 1000, _("All menus"), MenuEntryPixmap("mainmenu", self.png_cache)))
        setMenuList(self)
        if "key_red" in self:  # not yet while Menu makes the screen
            self.updateButtons()

    def updateButtons(self):
        """The footer shows the name of the favorite of each colour key."""
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

    def keyMenu(self):
        self.session.openWithCallback(self.editorChosen, ChoiceBox, title=_("Favorites"), windowTitle=_("Favorites"),
                                      list=[(_("Favorites Editor"), "editor"), (_("Button Editor"), "buttons")])

    def editorChosen(self, choice):
        if choice:
            self.session.openWithCallback(self.editorClosed, FavoritesEditor if choice[1] == "editor" else ButtonEditor)

    def moveFavorite(self, direction):
        """Moves the selected favorite one place, the first one up to the end and the last one down to the start, like the list of the plugins."""
        index = self["menu"].getIndex()
        count = len(self.paths)
        if count < 2 or index >= count:  # nothing to move, or the entry Menu
            return
        target = (index + direction) % count
        order = list(self.paths)
        order.insert(target, order.pop(index))
        favorites = loadFavorites()
        slots = [slot for slot, path in enumerate(favorites) if path in self.paths]  # the favorites that are not there keep their places
        for slot, path in zip(slots, order):
            favorites[slot] = path
        saveFavorites(favorites)
        self.createMenuList()
        self["menu"].setIndex(target)

    def openMainMenu(self):
        self.session.openWithCallback(self.menuClosed, MainMenu, mdom.getroot())

    def keyBlue(self):
        return 0  # the blue key is a colour key like the others (keyButton)

    def editorClosed(self, *_res):
        self.createMenuList()

    def isProtected(self):
        """The favorites are a way into the main menu: the PIN of the main menu is asked for them as well."""
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


def rootLevel():
    """The menu tree, then the lists of plugins and of extensions as menus."""
    tree = treeLevel(mdom.getroot(), [], _("Edit favorites"))

    def rows(menu):
        result = tree.rows(menu)
        for prefix, _where, title in PLUGIN_KINDS:
            level = pluginsLevel(prefix, _(title))
            result.append(((level.title, None, "plugin_selection", 900, "", MenuEntryPixmap("plugin_selection", menu.png_cache)), "", level))
        return result
    return Level(tree.title, rows)


class FavoritesEditor(Menu):
    """A menu of the tree: OK opens a menu or adds / removes an entry, YELLOW adds / removes the selected entry."""

    def __init__(self, session, level=None):
        self.level = level or rootLevel()
        self.paths = []  # the path of each row ("" for the lists of plugins)
        self.okbuttontext = _("Open the menu, or add the entry to the favorites or remove it")
        self.exitbuttontext = _("Back")
        Menu.__init__(self, session, Element("menu", {"key": "favorites_edit", "text": self.level.title}))
        self.skinName = ["Menu"]  # a long list: always the list of the skin, not the grid
        self["key_yellow"] = StaticText(_("Add/remove"))
        self["editActions"] = HelpableActionMap(self, ["ColorActions"],
        {
            "yellow": (self.toggleCurrent, _("Add the selected entry to the favorites or remove it")),
        }, prio=-1, description=_("Favorites Actions"))

    def createMenuList(self):
        self["key_blue"].text = ""
        self.menuID = self.parentmenu.get("key")
        favorites = loadFavorites()
        self.list = []
        self.paths = []
        for entry, path, child in self.level.rows(self):
            text, _action, key, weight, description, icon = entry
            mark = "[x] " if path in favorites else "[   ] "
            if child:
                self.list.append(((mark if path else "") + text + "  >", boundFunction(self.enter, child), key, weight, description, icon))
            else:
                self.list.append((mark + text, boundFunction(self.toggle, path), key, weight, description, icon))
            self.paths.append(path)
        setMenuList(self)

    def enter(self, level):
        self.session.openWithCallback(self.levelClosed, FavoritesEditor, level)

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
        favorites = loadFavorites()
        if path in favorites:
            favorites.remove(path)
        else:
            favorites.append(path)
        saveFavorites(favorites)
        self.refresh()

    def refresh(self):
        index = self["menu"].getIndex()
        self.createMenuList()
        self["menu"].setIndex(index)

    def keyBlue(self):
        return 0


class ButtonEditor(Menu):
    """A row for each colour key: OK chooses the favorite that the key opens."""

    def __init__(self, session):
        self.okbuttontext = _("Choose the favorite of the button")
        self.exitbuttontext = _("Back")
        Menu.__init__(self, session, Element("menu", {"key": "favorites_buttons", "text": _("Button Editor")}))
        self.skinName = ["Menu"]

    def createMenuList(self):
        self["key_blue"].text = ""
        self.menuID = self.parentmenu.get("key")
        buttons = loadButtons()
        names = {"red": _("Red"), "green": _("Green"), "yellow": _("Yellow"), "blue": _("Blue")}
        self.list = []
        for color in BUTTONS:
            entry = resolve(self, buttons[color]) if color in buttons else None
            self.list.append(("%s: %s" % (names[color], entry[0] if entry else _("none")), boundFunction(self.choose, color), "button_" + color, 50,
                              _("OK chooses the favorite of this button"), MenuEntryPixmap("button_" + color, self.png_cache)))
        setMenuList(self)

    def choose(self, color):
        current = loadButtons().get(color, "")
        choices = [(_("None"), "")]
        for path in loadFavorites():
            entry = resolve(self, path)
            if entry:
                choices.append((entry[0], path))
        selection = next((index for index, choice in enumerate(choices) if choice[1] == current), 0)
        self.session.openWithCallback(boundFunction(self.chosen, color), ChoiceBox, title=_("Favorite of the button"), windowTitle=_("Button Editor"),
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
    """The MENU key opens the favorites where the plugin's skin is the primary skin and the setting is on."""
    from Screens.InfoBarGenerics import InfoBarMenu  # pylint: disable=import-outside-toplevel
    original = InfoBarMenu.mainMenu
    if getattr(original, "isFavoritesHook", False):
        return

    def mainMenu(self):
        if settings.favorites_menu.value and isSkinActive():
            logger.info("MENU: favorites")
            self.session.infobar = self  # as InfoBarMenu.mainMenu does: screens opened from the menu use it
            try:
                self.session.openWithCallback(self.mainMenuClosed, FavoritesMenu)
                return
            except Exception:  # pylint: disable=broad-except
                logger.exception("the favorites could not be opened, the main menu is")
        else:
            logger.info("MENU: main menu (favorites_menu is %s, skin %s)", settings.favorites_menu.value, config.skin.primary_skin.value)
        original(self)

    mainMenu.isFavoritesHook = True
    InfoBarMenu.mainMenu = mainMenu
    logger.info("MENU opens the favorites if config.plugins.%s.favorites_menu is on", PLUGIN.lower())
