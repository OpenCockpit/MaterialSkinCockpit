# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0

# The setup of the skin: MENU > System > "Material skin setup" (and the plugin browser). One setting so far, the design of the channel selection:
# the classic list or the carousel (see PyServiceList.installCarousel). The channel selection is made when the GUI starts, so a change asks for a restart.

from Screens.MessageBox import MessageBox
from Screens.Setup import Setup
from Screens.Standby import TryQuitMainloop, QUIT_RESTART

from . import _
from .PyServiceList import settings, isSkinActive
from .Version import PLUGIN, VERSION


class MaterialSkinSetup(Setup):

    def __init__(self, session):
        Setup.__init__(self, session, setup=PLUGIN)
        self.setTitle(_("Material skin setup") + f" ({VERSION})")

    def createSetup(self):
        items = [(
            _("Channel selection"),
            settings.channel_selection,
            _("The channel selection that UP / DOWN, OK and the list key open: the classic list, or the carousel of tiles with the genres of the bouquet above it. The carousel needs the skin of this plugin. A change applies after a restart of the GUI.")
        )]
        if not isSkinActive():
            items.append(("---",))
            items.append((_("This skin is not the active skin: the setting applies when it is."),))
        self["config"].list = items

    def keySave(self):
        if settings.channel_selection.isChanged():
            self.session.openWithCallback(self.restartAnswer, MessageBox, _("Restart the GUI now to apply the channel selection?"), MessageBox.TYPE_YESNO, default=True)
        else:
            Setup.keySave(self)

    def restartAnswer(self, restart):
        if not restart:
            Setup.keySave(self)  # saves and closes
            return
        # Setup.keySave() closes this screen, after which it is no longer modal and session.open() raises
        # "Modal open are allowed only from a screen which is modal". So: save, open the restart dialog, then close
        # (a close of a screen that is not executing is deferred until it is again, like ConfigListScreen.restartConfirm).
        for notifier in self.onSave:
            notifier()
        self.saveAll()
        self.session.open(TryQuitMainloop, QUIT_RESTART)
        self.close()
