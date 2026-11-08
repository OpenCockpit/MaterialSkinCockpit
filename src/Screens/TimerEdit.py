# _ is the gettext function that enigma2 installs as a builtin: this file runs from enigma2's Screens directory (see PyReplace), where it cannot
# import the one of the plugin. pylint and flake8 do not know the builtin.
# pylint: disable=undefined-variable
# flake8: noqa: F821
from functools import cmp_to_key
from time import time

from RecordTimer import RecordTimerEntry, parseEvent, AFTEREVENT
from ServiceReference import ServiceReference
from Tools.Alternatives import GetWithAlternative
from Tools.BoundFunction import boundFunction
from Tools.Directories import SCOPE_GUISKIN, resolveFilename
from Tools.FuzzyDate import FuzzyTime
from Tools.LoadPixmap import LoadPixmap
from timer import TimerEntry as RealTimerEntry
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import config
from Components.MenuList import MenuList
from Components.Renderer.Picon import getPiconName
from Components.TimerList import TimerList
from Components.TimerSanityCheck import TimerSanityCheck
from Components.UsageConfig import preferredTimerPath
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen, ScreenSummary
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.ParentalControlSetup import ProtectedScreen
from Screens.Recordings import RecordingSettings
from Screens.TimerEntry import TimerEntry, TimerLog
from skin import domScreens, parameters

# The icons of the states of a timer: the paths of the pictures in the skin. The list draws pixmaps only, so they are loaded when the screen is built.
# A skin names its own with the parameters TimerIconWait, TimerIconRec, ...; these are the ones enigma2's skins have.
STATE_ICONS = {
    "wait": "icons/timer_wait.png",
    "rec": "icons/timer_rec.png",
    "prep": "icons/timer_prep.png",
    "done": "icons/timer_done.png",
    "rep": "icons/timer_rep.png",
    "zap": "icons/timer_zap.png",
    "off": "icons/timer_off.png",
    "failed": "icons/timer_failed.png",
    "autotimer": "icons/timer_autotimer.png"
}


class TimerEditList(Screen, ProtectedScreen):
    EMPTY = 0
    ENABLE = 1
    DISABLE = 2
    CLEANUP = 3
    DELETE = 4
    STOP = 5

    def __init__(self, session, selectItem=None):
        Screen.__init__(self, session)
        self.selectItem = selectItem
        ProtectedScreen.__init__(self)
        self.setTitle(_("Timer List"))
        self.skinName = ["TemplatedTimerEditList", "TimerEditList"]
        # A skin that has a TemplatedTimerEditList screen draws the rows itself (a TemplatedMultiContent of the list source "timerlist"); every
        # other skin gets the TimerList component that draws them, as before.
        self.templated = "TemplatedTimerEditList" in domScreens
        if self.templated:
            self.icons = {name: LoadPixmap(resolveFilename(SCOPE_GUISKIN, parameters.get("TimerIcon" + name.capitalize(), path))) for name, path in STATE_ICONS.items()}
            try:
                from Plugins.SystemPlugins.IceTV import loadIceTVIcon
                self.icons["icetv"] = loadIceTVIcon("timer_icetv.png")
            except ImportError:
                self.icons["icetv"] = None

        self.onChangedEntry = []
        self.list = []
        self.entries = []
        if self.templated:
            self["timerlist"] = List(self.entries)
        else:
            self["timerlist"] = TimerList(self.list)

        self.key_red_choice = self.EMPTY
        self.key_yellow_choice = self.EMPTY
        self.key_blue_choice = self.EMPTY

        self["key_red"] = StaticText("")
        self["key_green"] = StaticText(_("Add"))
        self["key_yellow"] = StaticText("")
        self["key_blue"] = StaticText("")

        self["key_menu"] = StaticText(_("MENU"))
        self["key_info"] = StaticText(_("INFO"))

        self["description"] = Label()

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ShortcutActions", "TimerEditActions"], {
            "ok": self.openEdit,
            "cancel": self.leave,
            "green": self.addCurrentTimer,
            "log": self.showLog,  # KEY_INFO
            "left": self.left,
            "right": self.right,
            "up": self.up,
            "down": self.down,
            "moveTop": self.moveTop,
            "moveEnd": self.moveEnd,
            "menu": self.createSetup
        }, -1)
        self.session.nav.RecordTimer.on_state_change.append(self.onStateChange)
        self.onLayoutFinish.append(self.onCreate)

    def onCreate(self):
        self.fillTimerList()
        if not self.templated:
            self["timerlist"].setList(self.list)

        if self.selectItem is not None:
            (event, service) = self.selectItem
            if event is not None:
                eventid = event.getEventId()
                refstr = ':'.join(service.ref.toString().split(':')[:11])
                idx = 0
                for (timer, _processed) in self.list:
                    if timer.eit == eventid and ':'.join(timer.service_ref.ref.toString().split(':')[:11]) == refstr:
                        self.moveToIndex(idx)
                        break
                    idx += 1
        self.updateState()

    def getCurrentTimer(self):
        if self.templated:
            index = self["timerlist"].index
            return self.list[index][0] if index is not None and 0 <= index < len(self.list) else None
        return self["timerlist"].getCurrent()

    def moveToIndex(self, index):
        if self.templated:
            self["timerlist"].setIndex(index)
        else:
            self["timerlist"].moveToIndex(index)

    def createSetup(self):
        def onSetupClose(_test=None):
            self.refill()

        self.session.openWithCallback(onSetupClose, RecordingSettings)

    def isProtected(self):
        return config.ParentalControl.setuppinactive.value and (not config.ParentalControl.config_sections.main_menu.value or hasattr(self.session, 'infobar') and self.session.infobar is None) and config.ParentalControl.config_sections.timer_menu.value and config.ParentalControl.servicepin[0].value

    def createSummary(self):
        return TimerEditListSummary

    def up(self):
        if self.templated:
            self["timerlist"].up()
        else:
            self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveUp)
        self.updateState()

    def down(self):
        if self.templated:
            self["timerlist"].down()
        else:
            self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveDown)
        self.updateState()

    def left(self):
        if self.templated:
            self["timerlist"].pageUp()
        else:
            self["timerlist"].instance.moveSelection(self["timerlist"].instance.pageUp)
        self.updateState()

    def right(self):
        if self.templated:
            self["timerlist"].pageDown()
        else:
            self["timerlist"].instance.moveSelection(self["timerlist"].instance.pageDown)
        self.updateState()

    def moveTop(self):
        if self.templated:
            self["timerlist"].top()
        else:
            self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveTop)
        self.updateState()

    def moveEnd(self):
        if self.templated:
            self["timerlist"].bottom()
        else:
            self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveEnd)
        self.updateState()

    def toggleDisabledState(self):
        cur = self.getCurrentTimer()
        if cur:
            t = cur
            orig_state = t.disabled
            if t.disabled:
                t.enable()
                timersanitycheck = TimerSanityCheck(self.session.nav.RecordTimer.timer_list, cur)
                if not timersanitycheck.check():
                    t.disable()
                    print("[TimerEdit] Sanity check failed")
                    simulTimerList = timersanitycheck.getSimulTimerList()
                    if simulTimerList is not None:
                        self.session.openWithCallback(self.finishedEdit, TimerSanityConflict, simulTimerList)
                else:
                    print("[TimerEdit] Sanity check passed")
                    if timersanitycheck.doubleCheck():
                        t.disable()
            elif t.isRunning():
                if t.repeated:
                    choices = (
                        (_("Stop current event but not future events"), "stoponlycurrent"),
                        (_("Stop current event and disable future events"), "stopall"),
                        (_("Don't stop current event but disable future events"), "stoponlycoming")
                    )
                    self.session.openWithCallback(boundFunction(self.runningEventCallback, t), ChoiceBox, title=_("Repeating event currently recording... What do you want to do?"), list=choices)
            else:
                t.disable()
            self.session.nav.RecordTimer.timeChanged(t)
            if t.disabled != orig_state:
                cur.log(0, f"[TimerEdit] Timer has been {'disabled' if t.disabled else 'enabled'}")
            self.refill()
            self.updateState()

    def runningEventCallback(self, t, result):
        if result is not None:
            if result[1] == "stoponlycurrent" or result[1] == "stopall":
                t.enable()
                t.processRepeated(findRunningEvent=False)
                self.session.nav.RecordTimer.doActivate(t)
            if result[1] == "stoponlycoming" or result[1] == "stopall":
                t.disable()
            self.session.nav.RecordTimer.timeChanged(t)
            self.refill()
            self.updateState()

    def removeAction(self, descr):
        actions = self["actions"].actions
        if descr in actions:
            del actions[descr]

    def updateState(self):
        cur = self.getCurrentTimer()
        if cur:
            self["description"].setText(cur.description)
            if cur.state == 2 and self.key_red_choice != self.STOP:
                self["actions"].actions.update({"red": self.stopTimerQuestion})
                self["key_red"].setText(_("Stop"))
                self.key_red_choice = self.STOP
            elif cur.state != 2 and self.key_red_choice != self.DELETE:
                self["actions"].actions.update({"red": self.removeTimerQuestion})
                self["key_red"].setText(_("Delete"))
                self.key_red_choice = self.DELETE

            if cur.disabled and (self.key_yellow_choice != self.ENABLE):
                self["actions"].actions.update({"yellow": self.toggleDisabledState})
                self["key_yellow"].setText(_("Enable"))
                self.key_yellow_choice = self.ENABLE
            elif cur.isRunning() and not cur.repeated and (self.key_yellow_choice != self.EMPTY):
                self.removeAction("yellow")
                self["key_yellow"].setText("")
                self.key_yellow_choice = self.EMPTY
            elif ((not cur.isRunning()) or cur.repeated) and (not cur.disabled) and (self.key_yellow_choice != self.DISABLE):
                self["actions"].actions.update({"yellow": self.toggleDisabledState})
                self["key_yellow"].setText(_("Disable"))
                self.key_yellow_choice = self.DISABLE
        else:
            if self.key_red_choice != self.EMPTY:
                self.removeAction("red")
                self["key_red"].setText("")
                self.key_red_choice = self.EMPTY
            if self.key_yellow_choice != self.EMPTY:
                self.removeAction("yellow")
                self["key_yellow"].setText("")
                self.key_yellow_choice = self.EMPTY

        showCleanup = True
        for x in self.list:
            if (not x[0].disabled) and (x[1] is True):
                break
        else:
            showCleanup = False

        if showCleanup and (self.key_blue_choice != self.CLEANUP):
            self["actions"].actions.update({"blue": self.cleanupQuestion})
            self["key_blue"].setText(_("Cleanup"))
            self.key_blue_choice = self.CLEANUP
        elif (not showCleanup) and (self.key_blue_choice != self.EMPTY):
            self.removeAction("blue")
            self["key_blue"].setText("")
            self.key_blue_choice = self.EMPTY
        if len(self.list) == 0:
            return
        timer = self.getCurrentTimer()

        if timer:
            try:
                name = str(timer.name)
                timeText = f"{FuzzyTime(timer.begin)[0]} {FuzzyTime(timer.begin)[1]} ... {FuzzyTime(timer.end)[1]}"
                duration = ("(%d " + _("mins") + ")") % ((timer.end - timer.begin) / 60)
                service = str(timer.service_ref.getServiceName())

                if timer.state == RealTimerEntry.StateWaiting:
                    state = _("waiting")
                elif timer.state == RealTimerEntry.StatePrepared:
                    state = _("about to start")
                elif timer.state == RealTimerEntry.StateRunning:
                    if timer.justplay:
                        state = _("zapped")
                    else:
                        state = _("recording...")
                elif timer.state == RealTimerEntry.StateEnded:
                    state = _("done!")
                else:
                    state = _("<unknown>")
            except Exception:  # pylint: disable=broad-except
                name = ""
                timeText = ""
                duration = ""
                service = ""
                state = ""
        else:
            name = ""
            timeText = ""
            duration = ""
            service = ""
            state = ""
        for cb in self.onChangedEntry:
            cb(name, timeText, duration, service, state)

    def fillTimerList(self):
        # helper function to move finished timers to end of list
        def _cmp(a, b):
            return (a > b) - (a < b)

        def eol_compare(x, y):
            if x[0].state != y[0].state and x[0].state == RealTimerEntry.StateEnded or y[0].state == RealTimerEntry.StateEnded:
                return _cmp(x[0].state, y[0].state)
            return _cmp(x[0].begin, y[0].begin)

        xlist = self.list
        del xlist[:]
        xlist.extend([(timer, False) for timer in self.session.nav.RecordTimer.timer_list])
        now = time()
        if config.usage.timerlist_finished_timer_position.index == 2:
            # if the "hide" option is set, continue to add disabled timers so
            # timer conflicts remain visible
            xlist.extend([(timer, True) for timer in self.session.nav.RecordTimer.processed_timers if timer.disabled and timer.end > now])
        else:
            xlist.extend([(timer, True) for timer in self.session.nav.RecordTimer.processed_timers])
        if config.usage.timerlist_finished_timer_position.index:  # end of list
            xlist.sort(key=cmp_to_key(eol_compare))
        else:
            xlist.sort(key=lambda x: x[0].begin)
        if self.templated:
            self.updateEntries()

    def updateEntries(self):
        # the rows of the list source: what the template of the skin draws, in the order of self.list
        self.entries = [self.buildEntry(timer, processed) for timer, processed in self.list]
        if "timerlist" in self:  # not while the screen is built
            lst = self["timerlist"]
            lst.style = "picons" if config.usage.timerlist_showpicons.value else "default"  # the skin has a template of each
            index = lst.index
            lst.setList(self.entries)
            if self.entries and index is not None:
                lst.setIndex(min(index, len(self.entries) - 1))

    def buildEntry(self, timer, processed):
        # (timer, state icon, name, service, state, orbital position, days and times, repeat icon, picon): the indexes the template of the skin uses
        icons = self.icons
        repeatIcon = None
        begin = FuzzyTime(timer.begin)
        if timer.repeated:
            days = (_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun"))
            repeatedtext = []
            flags = timer.repeated
            for x in range(7):
                if flags & 1 == 1:
                    repeatedtext.append(days[x])
                flags >>= 1
            if repeatedtext == [_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun")]:
                repeatedtext = _("Everyday")
            elif repeatedtext == [_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri")]:
                repeatedtext = _("Weekday")
            elif repeatedtext == [_("Sat"), _("Sun")]:
                repeatedtext = _("Weekend")
            else:
                repeatedtext = ", ".join(repeatedtext)
            repeatIcon = icons["rep"]
        else:
            repeatedtext = begin[0]  # date
        if timer.justplay:
            extra_text = _("(ZAP)")
            if timer.pipzap:
                extra_text = _("(ZAP as PiP)")
            text = repeatedtext + ((" %s " + extra_text) % (begin[1]))
        else:
            text = repeatedtext + ((" %s ... %s (%d " + _("mins") + ")") % (begin[1], FuzzyTime(timer.end)[1], (timer.end - timer.begin) // 60))
        icon = None
        if not processed:
            if timer.state == RealTimerEntry.StateWaiting:
                state = _("waiting")
                if icons["icetv"] and hasattr(timer, "ice_timer_id") and timer.ice_timer_id:
                    icon = icons["icetv"]
                elif timer.isAutoTimer:
                    icon = icons["autotimer"]
                else:
                    icon = icons["wait"]
            elif timer.state == RealTimerEntry.StatePrepared:
                state = _("about to start")
                icon = icons["prep"]
            elif timer.state == RealTimerEntry.StateRunning:
                if timer.justplay:
                    state = _("zapped")
                    icon = icons["zap"]
                else:
                    state = _("recording...")
                    icon = icons["rec"]
            elif timer.state == RealTimerEntry.StateEnded:
                state = _("done!")
                icon = icons["done"]
            else:
                state = _("<unknown>")
        elif timer.disabled:
            state = _("disabled")
            icon = icons["off"]
        elif timer.failed:
            state = _("failed")
            icon = icons["failed"]
        else:
            state = _("done!")
            icon = icons["done"]
        picon = None
        if config.usage.timerlist_showpicons.value:
            picon = getPiconName(str(timer.service_ref.sref if hasattr(timer.service_ref, "sref") else timer.service_ref))
            picon = LoadPixmap(picon) if picon else None
        return (timer, icon, timer.name, timer.service_ref.getServiceName(), state, self.getOrbitalPos(timer.service_ref), text, repeatIcon, picon)

    def getOrbitalPos(self, ref):
        refstr = str(ref.sref if hasattr(ref, "sref") else ref)
        refstr = refstr and GetWithAlternative(refstr)
        if "%3a//" in refstr:
            return _("Stream")
        op = int(refstr.split(":", 10)[6][:-4] or "0", 16)
        if op == 0xeeee:
            return _("DVB-T")
        if op == 0xffff:
            return _("DVB-C")
        direction = "E"
        if op > 1800:
            op = 3600 - op
            direction = "W"
        return f"{op // 10}.{op % 10}\xb0{direction}"

    def showLog(self):
        cur = self.getCurrentTimer()
        if cur:
            self.session.openWithCallback(self.finishedEdit, TimerLog, cur)

    def openEdit(self):
        cur = self.getCurrentTimer()
        if cur:
            self.session.openWithCallback(self.finishedEdit, TimerEntry, cur)

    def cleanupQuestion(self):
        self.session.openWithCallback(self.cleanupTimer, MessageBox, _("Really delete completed timers?"))

    def cleanupTimer(self, delete):
        if delete:
            self.session.nav.RecordTimer.cleanup()
            self.refill()
            self.updateState()

    def stopTimerQuestion(self):
        cur = self.getCurrentTimer()
        if cur:
            self.session.openWithCallback(self.removeTimer, MessageBox, _("Do you really want to stop the current recording and delete timer %s?") % cur.name, default=False)

    def removeTimerQuestion(self):
        cur = self.getCurrentTimer()
        if cur:
            self.session.openWithCallback(self.removeTimer, MessageBox, _("Do you really want to delete %s?") % cur.name, default=False)

    def removeTimer(self, result):
        if not result:
            return
        cur = self.getCurrentTimer()
        if cur:
            timer = cur
            timer.afterEvent = AFTEREVENT.NONE
            self.session.nav.RecordTimer.removeEntry(timer)
            self.refill()
            self.updateState()

    def refill(self):
        oldsize = len(self.list)
        self.fillTimerList()
        if self.templated:  # fillTimerList has given the list source its new rows
            return
        lst = self["timerlist"]
        newsize = len(self.list)
        if oldsize and oldsize != newsize:
            idx = lst.getCurrentIndex()
            lst.entryRemoved(idx)
        else:
            lst.invalidate()

    def addCurrentTimer(self):
        event = None
        service = self.session.nav.getCurrentService()
        if service is not None:
            info = service.info()
            if info is not None:
                event = info.getEvent(0)

        # FIXME only works if already playing a service
        serviceref = ServiceReference(self.session.nav.getCurrentlyPlayingServiceOrGroup())

        if event is None:
            data = (int(time()), int(time() + 60), "", "", None)
        else:
            data = parseEvent(event, description=True)

        self.addTimer(RecordTimerEntry(serviceref, checkOldTimers=True, dirname=preferredTimerPath(), *data))

    def addTimer(self, timer):
        self.session.openWithCallback(self.finishedAdd, TimerEntry, timer)

    def finishedEdit(self, answer):
        if answer[0]:
            entry = answer[1]
            timersanitycheck = TimerSanityCheck(self.session.nav.RecordTimer.timer_list, entry)
            success = False
            if not timersanitycheck.check():
                simulTimerList = timersanitycheck.getSimulTimerList()
                if simulTimerList is not None:
                    for x in simulTimerList:
                        if x.setAutoincreaseEnd(entry):
                            self.session.nav.RecordTimer.timeChanged(x)
                    if not timersanitycheck.check():
                        simulTimerList = timersanitycheck.getSimulTimerList()
                        if simulTimerList is not None:
                            self.session.openWithCallback(self.finishedEdit, TimerSanityConflict, timersanitycheck.getSimulTimerList())
                    else:
                        success = True
            else:
                success = True
            if success:
                print("[TimerEdit] Sanity check passed")
                self.session.nav.RecordTimer.timeChanged(entry)

            self.fillTimerList()
            self.updateState()

    def finishedAdd(self, answer):
        if answer[0]:
            entry = answer[1]
            simulTimerList = self.session.nav.RecordTimer.record(entry)
            if simulTimerList is not None:
                for x in simulTimerList:
                    if x.setAutoincreaseEnd(entry):
                        self.session.nav.RecordTimer.timeChanged(x)
                simulTimerList = self.session.nav.RecordTimer.record(entry)
                if simulTimerList is not None:
                    self.session.openWithCallback(self.finishSanityCorrection, TimerSanityConflict, simulTimerList)
            self.fillTimerList()
            self.updateState()

    def finishSanityCorrection(self, answer):
        self.finishedAdd(answer)

    def leave(self):
        self.session.nav.RecordTimer.on_state_change.remove(self.onStateChange)
        self.close()

    def onStateChange(self, _entry):
        self.refill()
        self.updateState()


class TimerSanityConflict(Screen):
    EMPTY = 0
    ENABLE = 1
    DISABLE = 2
    EDIT = 3

    def __init__(self, session, timer):
        Screen.__init__(self, session)
        self.setTitle(_("Timer Sanity Error"))

        self.timer = timer
        print("[TimerEdit] TimerSanityConflict")

        self["timer1"] = TimerList(self.getTimerList(timer[0]))
        self.list = []
        self.list2 = []
        count = 0
        for x in timer:
            if count != 0:
                self.list.append((_("Conflicting timer") + " " + str(count), x))
                self.list2.append((timer[count], False))
            count += 1
        if count == 1:
            self.list.append((_("Channel not in services list")))

        self["list"] = MenuList(self.list)
        self["timer2"] = TimerList(self.list2)

        self["key_red"] = StaticText(_("Edit new entry"))
# 		self["key_green"] = StaticText("")
        self["key_yellow"] = StaticText("")
        self["key_blue"] = StaticText("")

        self.key_green_choice = self.EMPTY
        self.key_yellow_choice = self.EMPTY
        self.key_blue_choice = self.EMPTY

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ShortcutActions", "TimerEditActions"], {
            "ok": self.leave_ok,
            "cancel": self.leave_cancel,
            "red": self.editTimer1,
            "up": self.up,
            "down": self.down
        }, -1)
        self.onShown.append(self.updateState)

    def getTimerList(self, timer):
        return [(timer, False)]

    def editTimer1(self):
        self.session.openWithCallback(self.finishedEdit, TimerEntry, self["timer1"].getCurrent())

    def editTimer2(self):
        self.session.openWithCallback(self.finishedEdit, TimerEntry, self["timer2"].getCurrent())

    def toggleTimer(self):
        x = self["list"].getSelectedIndex() + 1  # the first is the new timer so we do +1 here
        if self.timer[x].disabled:
            self.timer[x].disabled = False
            self.session.nav.RecordTimer.timeChanged(self.timer[x])
            if not self.timer[0].isRunning():
                self.timer[0].disabled = True
                self.session.nav.RecordTimer.timeChanged(self.timer[0])

        elif not self.timer[x].isRunning():
            self.timer[x].disabled = True
            self.session.nav.RecordTimer.timeChanged(self.timer[x])
            if self.timer[x].disabled:
                self.timer[0].disabled = False
                self.session.nav.RecordTimer.timeChanged(self.timer[0])
        self.finishedEdit((True, self.timer[0]))

    def finishedEdit(self, _answer):
        self.leave_ok()

    def leave_ok(self):
        self.close((True, self.timer[0]))

    def leave_cancel(self):
        self.close((False, self.timer[0]))

    def up(self):
        self["list"].instance.moveSelection(self["list"].instance.moveUp)
        self["timer2"].moveToIndex(self["list"].getSelectedIndex())

    def down(self):
        self["list"].instance.moveSelection(self["list"].instance.moveDown)
        self["timer2"].moveToIndex(self["list"].getSelectedIndex())

    def removeAction(self, descr):
        actions = self["actions"].actions
        if descr in actions:
            del actions[descr]

    def updateState(self):
        if len(self.timer) > 1:
            x = self["list"].getSelectedIndex() + 1  # the first is the new timer so we do +1 here
            if self.timer[x] is not None:
                if self.key_yellow_choice == self.EMPTY:
                    self["actions"].actions.update({"yellow": self.editTimer2})
                    self["key_yellow"].setText(_("Edit"))
                    self.key_yellow_choice = self.EDIT
                if self.timer[x].disabled and self.key_blue_choice != self.ENABLE:
                    self["actions"].actions.update({"blue": self.toggleTimer})
                    self["key_blue"].setText(_("Enable"))
                    self.key_blue_choice = self.ENABLE
                elif self.timer[x].isRunning() and not self.timer[x].repeated and self.key_blue_choice != self.EMPTY:
                    self.removeAction("blue")
                    self["key_blue"].setText("")
                    self.key_blue_choice = self.EMPTY
                elif (not self.timer[x].isRunning() or self.timer[x].repeated) and self.key_blue_choice != self.DISABLE:
                    self["actions"].actions.update({"blue": self.toggleTimer})
                    self["key_blue"].setText(_("Disable"))
                    self.key_blue_choice = self.DISABLE
        else:
            if self.key_yellow_choice != self.EMPTY:
                self.removeAction("yellow")
                self["key_yellow"].setText("")
                self.key_yellow_choice = self.EMPTY
            if self.key_blue_choice != self.EMPTY:
                self.removeAction("blue")
                self["key_blue"].setText("")
                self.key_blue_choice = self.EMPTY


class TimerEditListSummary(ScreenSummary):
    def __init__(self, session, parent):
        ScreenSummary.__init__(self, session, parent=parent)
        self["name"] = StaticText("")
        self["service"] = StaticText("")
        self["time"] = StaticText("")
        self["duration"] = StaticText("")
        self["state"] = StaticText("")
        self.onShow.append(self.addWatcher)
        self.onHide.append(self.removeWatcher)

    def addWatcher(self):
        self.parent.onChangedEntry.append(self.selectionChanged)
        self.parent.updateState()

    def removeWatcher(self):
        self.parent.onChangedEntry.remove(self.selectionChanged)

    def selectionChanged(self, name, timeText, duration, service, state):
        self["name"].text = name
        self["service"].text = service
        self["time"].text = timeText
        self["duration"].text = duration
        self["state"].text = state
