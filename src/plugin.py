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

from os.path import dirname

from Components.config import config
from .Debug import logger
from .PyReplace import sync, restore
from .Version import PLUGIN, VERSION


def isSkinActive():
    return dirname(config.skin.primary_skin.value) == PLUGIN


def syncPYs():
    """The files of the plugin are in place while the skin is the primary skin, the originals are otherwise."""
    if isSkinActive():
        sync()
    else:
        restore()


def onSkinSelected(_configElement=None):
    syncPYs()


def Plugins(**__):
    logger.info("  +++ Version: %s starts...", VERSION)
    syncPYs()  # what the skin selector may not have done (an update of the plugin, the skin set by hand)
    try:  # the MENU key opens a menu of favorites, unless config.plugins.materialskincockpit.favorites_menu is off (see FavoritesMenu)
        from .FavoritesMenu import install  # pylint: disable=import-outside-toplevel
        install()
    except Exception:  # pylint: disable=broad-except
        logger.exception("FavoritesMenu not installed")
    # the skin selector writes the setting before it reloads the skin or restarts the GUI
    config.skin.primary_skin.addNotifier(onSkinSelected, initial_call=False)
    return []
