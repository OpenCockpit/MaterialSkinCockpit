# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0
#
# The python files of this plugin (src/<dir>/<file>.py, installed to the plugin directory, the skin excepted) replace files of
# enigma2 (<dir>/<file>.py of /usr/lib/enigma2/python) while this skin is the primary skin of the box. They are put in place when the
# user selects the skin and the originals are put back when another skin is selected: the skin selector writes
# config.skin.primary_skin before it reloads the skin or restarts the GUI, so the files are there when enigma2 imports them again.
#
# PyReplace (see there for the rules) puts the files in place and the originals back. It saves the original of a file only if the file is not the
# one that it has put in place itself, so a file that enigma2 has updated in the meantime is never replaced by an old original. The originals are
# put back when the plugin is removed while the skin is active (the prerm), and the state is in /usr/share/enigma2/<plugin>/state.json.
#
# The menus of this skin are grids: when the skin is selected the setting "Menu style" (config.usage.menu_style) is set to "horizontal", and
# when another skin is selected it is put back to what it was (syncMenuStyle). What it was is kept in config.plugins.materialskincockpit.menu_style_before
# while the skin is active; the setting can be changed in between, that choice is left alone until the skin is deselected.
# If the plugin is removed while its skin is the primary skin the setting is put back when enigma2 ends (autoStart): the prerm cannot do it,
# enigma2 has its settings in memory and writes the file when it ends. It ends with the settings written and then calls the plugins that are
# still in its list with reason 1 (StartEnigma, plugins.shutdown()), so they are written once more there.

from os.path import dirname, isfile, join

from Components.config import config, configfile, ConfigText
from Plugins.Plugin import PluginDescriptor
from .Debug import logger
from .PyReplace import sync, restore
from .Version import PLUGIN, VERSION


GRID = "horizontal"  # config.usage.menu_style: "standard" (the lists) or "horizontal" (the grids of the skin)

settings = getattr(config.plugins, PLUGIN.lower())  # made by Debug.py
settings.menu_style_before = ConfigText(default="", fixed_size=False)  # "Menu style" before the skin set it to GRID; empty: the skin has not


def isSkinActive():
    return dirname(config.skin.primary_skin.value) == PLUGIN


def syncMenuStyle(active=None):
    """The menus are grids while this skin is the primary skin, and the setting is what it was before otherwise. The first time the skin is
    seen active (the value before is empty) is its activation: the setting is kept and set to GRID; later the choice of the user is left alone.
    *active* is None for "look at the primary skin"; False says that the skin is gone (see autoStart)."""
    style = getattr(config.usage, "menu_style", None)  # only OpenViX has it
    if style is None:
        return
    before = settings.menu_style_before
    if isSkinActive() if active is None else active:
        if before.value:
            return
        before.value = style.value
        before.save()
        if style.value != GRID:
            style.value = GRID
            style.save()
            logger.info("menu style: grid (was %s)", before.value)
        configfile.save()
    elif before.value:
        style.value = before.value
        style.save()
        logger.info("menu style: %s again", before.value)
        before.value = ""
        before.save()
        configfile.save()


def syncPYs():
    """The files of the plugin are in place while the skin is the primary skin, the originals are otherwise."""
    if isSkinActive():
        sync()
    else:
        restore()


SKIN_FILE = join("/usr/share/enigma2", PLUGIN, "skin.xml")


def autoStart(reason, **__kwargs):
    """Reason 1 is the end of enigma2. If the skin is gone then (the plugin was removed while enigma2 was running) the menu style is put back
    in the memory of enigma2 and the settings are written again, after enigma2 has written them with the style of the skin."""
    if reason == 1 and not isfile(SKIN_FILE):
        syncMenuStyle(False)


def onSkinSelected(_configElement=None):
    syncPYs()
    syncMenuStyle()


def Plugins(**__):
    logger.info("  +++ Version: %s starts...", VERSION)
    syncPYs()  # what the skin selector may not have done (an update of the plugin, the skin set by hand)
    syncMenuStyle()
    try:  # the MENU key opens a menu of cockpit, unless config.plugins.materialskincockpit.cockpit_menu is off (see CockpitMenu)
        from .CockpitMenu import install  # pylint: disable=import-outside-toplevel
        install()
    except Exception:  # pylint: disable=broad-except
        logger.exception("CockpitMenu not installed")
    # the skin selector writes the setting before it reloads the skin or restarts the GUI
    config.skin.primary_skin.addNotifier(onSkinSelected, initial_call=False)
    return [PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, fnc=autoStart)]
