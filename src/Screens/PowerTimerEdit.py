# _ is the gettext function that enigma2 installs as a builtin: this file runs from enigma2's Screens directory (see PyReplace), where it cannot
# import the one of the plugin. pylint and flake8 do not know the builtin.
# pylint: disable=undefined-variable
# flake8: noqa: F821
from functools import cmp_to_key
from time import time

from PowerTimer import PowerTimerEntry, AFTEREVENT, TIMERTYPE
from Tools.BoundFunction import boundFunction
from Tools.Directories import SCOPE_GUISKIN, resolveFilename
from Tools.FuzzyDate import FuzzyTime
from Tools.LoadPixmap import LoadPixmap
from timer import TimerEntry as RealTimerEntry
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.config import config
from Components.PowerTimerList import PowerTimerList
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen, ScreenSummary
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.PowerTimerEntry import TimerEntry, TimerLog
from skin import domScreens, parameters

# The icons of the states of a timer: the paths of the pictures in the skin. The list draws pixmaps only, so they are loaded when the screen is built.
# A skin names its own with the parameters PowerTimerIconWait, PowerTimerIconRec, ...; these are the ones enigma2's skins have.
STATE_ICONS = {
    "wait": "icons/timer_wait.png",
    "rec": "icons/timer_rec.png",
    "prep": "icons/timer_prep.png",
    "done": "icons/timer_done.png",
    "rep": "icons/timer_rep.png",
    "zap": "icons/timer_zap.png",
    "off": "icons/timer_off.png",
    "failed": "icons/timer_failed.png"
}


class PowerTimerEditList(Screen):
    EMPTY = 0
    ENABLE = 1
    DISABLE = 2
    CLEANUP = 3
    DELETE = 4

    def __init__(self, session):
        Screen.__init__(self, session)
        self.skinName = ["PowerTimerEditList", "TimerEditList"]
        self.setTitle(_("Power Timer List"))
        # A skin that has a PowerTimerEditList screen draws the rows itself (a TemplatedMultiContent of the list source "timerlist"); every
        # other skin gets the PowerTimerList component that draws them, as before.
        self.templated = "PowerTimerEditList" in domScreens
        if self.templated:
            self.icons = {name: LoadPixmap(resolveFilename(SCOPE_GUISKIN, parameters.get("PowerTimerIcon" + name.capitalize(), path))) for name, path in STATE_ICONS.items()}

        self.onChangedEntry = []
        self.list = []
        self.entries = []
        self.fillTimerList()

        if self.templated:
            self["timerlist"] = List(self.entries)
        else:
            self["timerlist"] = PowerTimerList(self.list)

        self.key_red_choice = self.EMPTY
        self.key_yellow_choice = self.EMPTY
        self.key_blue_choice = self.EMPTY

        self["key_red"] = Button("")
        self["key_green"] = Button(_("Add"))
        self["key_yellow"] = Button("")
        self["key_blue"] = Button("")
        self["key_info"] = StaticText(_("INFO"))

        if not self.templated:
            self["description"] = Label()  # the panel of the skin of the timer list: a power timer has none, the label stays empty

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ShortcutActions", "TimerEditActions"], {
            "ok": self.openEdit,
            "cancel": self.leave,
            "green": self.addCurrentTimer,
            "log": self.showLog,
            "left": self.left,
            "right": self.right,
            "up": self.up,
            "down": self.down
        }, -1)
        self.session.nav.PowerTimer.on_state_change.append(self.onStateChange)
        self.onShown.append(self.updateState)
        if not self.templated:
            self["timerlist"].selectionChanged()

    def createSummary(self):
        return PowerTimerEditListSummary

    def getCurrentTimer(self):
        if self.templated:
            index = self["timerlist"].index
            return self.list[index][0] if index is not None and 0 <= index < len(self.list) else None
        return self["timerlist"].getCurrent()

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

    def toggleDisabledState(self):
        cur = self.getCurrentTimer()
        if cur:
            t = cur
            if t.disabled:
                print("[PowerTimerEdit] try to ENABLE timer")
                t.enable()
            elif t.isRunning():
                if t.repeated:
                    tlist = (
                        (_("Stop current event but not future events"), "stoponlycurrent"),
                        (_("Stop current event and disable future events"), "stopall"),
                        (_("Don't stop current event but disable future events"), "stoponlycoming")
                    )
                    self.session.openWithCallback(boundFunction(self.runningEventCallback, t), ChoiceBox, title=_("Repeating the event currently recording... What do you want to do?"), list=tlist)
            else:
                t.disable()
            self.session.nav.PowerTimer.timeChanged(t)
            self.refill()
            self.updateState()

    def runningEventCallback(self, t, result):
        if result is not None:
            if result[1] == "stoponlycurrent" or result[1] == "stopall":
                t.enable()
                t.processRepeated(findRunningEvent=False)
                self.session.nav.PowerTimer.doActivate(t)
            if result[1] == "stoponlycoming" or result[1] == "stopall":
                t.disable()
            self.session.nav.PowerTimer.timeChanged(t)
            self.refill()
            self.updateState()

    def removeAction(self, descr):
        actions = self["actions"].actions
        if descr in actions:
            del actions[descr]

    def updateState(self):
        cur = self.getCurrentTimer()
        if cur:
            if self.key_red_choice != self.DELETE:
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
            print("[PowerTimerEditList] updateState timer", timer)
            print("[PowerTimerEditList] updateState timer.timer", timer.timer)
            print("[PowerTimerEditList] updateState timer.timerType", timer.timerType)
            timerType = timer.timerType
            timeText = f"{FuzzyTime(timer.begin)[0]} {FuzzyTime(timer.begin)[1]} ... {FuzzyTime(timer.end)[1]}"
            duration = ("(%d " + _("mins") + ")") % ((timer.end - timer.begin) / 60)

            if timer.state == RealTimerEntry.StateWaiting:
                state = _("waiting")
            elif timer.state == RealTimerEntry.StatePrepared:
                state = _("about to start")
            elif timer.state == RealTimerEntry.StateRunning:
                state = _("running...")
            elif timer.state == RealTimerEntry.StateEnded:
                state = _("done!")
            else:
                state = _("<unknown>")
        else:
            timerType = 0
            timeText = ""
            duration = ""
            state = ""
        for cb in self.onChangedEntry:
            cb(timerType, timeText, duration, state)

    def fillTimerList(self):
        # helper function to move finished timers to end of list

        def xcmp(a, b):
            return (a > b) - (a < b)

        def eol_compare(x, y):
            if x[0].state != y[0].state and x[0].state == RealTimerEntry.StateEnded or y[0].state == RealTimerEntry.StateEnded:
                return xcmp(x[0].state, y[0].state)
            return xcmp(x[0].begin, y[0].begin)

        flist = self.list
        del flist[:]
        flist.extend([(timer, False) for timer in self.session.nav.PowerTimer.timer_list])
        flist.extend([(timer, True) for timer in self.session.nav.PowerTimer.processed_timers])
        if config.usage.timerlist_finished_timer_position.index:  # end of list
            flist.sort(key=cmp_to_key(eol_compare))
        else:
            flist.sort(key=lambda x: x[0].begin)
        if self.templated:
            self.updateEntries()

    def updateEntries(self):
        # the rows of the list source: what the template of the skin draws, in the order of self.list
        self.entries = [self.buildEntry(timer, processed) for timer, processed in self.list]
        if "timerlist" in self:  # not while the screen is built
            lst = self["timerlist"]
            index = lst.index
            lst.setList(self.entries)
            if self.entries and index is not None:
                lst.setIndex(min(index, len(self.entries) - 1))

    def buildEntry(self, timer, processed):
        # (timer, icon, type, at end, state, time, repeat icon): the indexes the template of the skin uses
        icons = self.icons
        if timer.timerType in (TIMERTYPE.AUTOSTANDBY, TIMERTYPE.AUTODEEPSTANDBY):
            atEnd = _("Delay:") + " " + str(timer.autosleepdelay) + "(" + _("mins") + ")"
            timeText = ""
            repeatIcon = icons["rep"] if timer.autosleeprepeat != "once" else None
            icon = None
            if not processed:
                if timer.state == RealTimerEntry.StateWaiting:
                    state = _("waiting")
                    icon = icons["wait"]
                elif timer.state in (RealTimerEntry.StatePrepared, RealTimerEntry.StateRunning):
                    state = _("running...")
                    icon = icons["zap"]
                elif timer.state == RealTimerEntry.StateEnded:
                    state = _("done!")
                    icon = icons["done"]
                else:
                    state = _("<unknown>")
            else:
                state = _("done!")
                icon = icons["done"]
        else:
            afterevent = {
                AFTEREVENT.NONE: _("Nothing"),
                AFTEREVENT.WAKEUPTOSTANDBY: _("Wake Up To Standby"),
                AFTEREVENT.STANDBY: _("Standby"),
                AFTEREVENT.DEEPSTANDBY: _("Deep Standby")
            }[timer.afterEvent]
            atEnd = _("At End:") + " " + afterevent
            days = (_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun"))
            begin = FuzzyTime(timer.begin)
            repeatIcon = None
            if timer.repeated:
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
            timeText = repeatedtext + ((" %s ... %s (%d " + _("mins") + ")") % (begin[1], FuzzyTime(timer.end)[1], (timer.end - timer.begin) / 60))
            icon = None
            if not processed:
                if timer.state == RealTimerEntry.StateWaiting:
                    state = _("waiting")
                    icon = icons["wait"]
                elif timer.state == RealTimerEntry.StatePrepared:
                    state = _("about to start")
                    icon = icons["prep"]
                elif timer.state == RealTimerEntry.StateRunning:
                    state = _("running...")
                    icon = icons["zap"]
                elif timer.state == RealTimerEntry.StateEnded:
                    state = _("done!")
                    icon = icons["done"]
                else:
                    state = _("<unknown>")
            else:
                state = _("done!")
                icon = icons["done"]
        if timer.disabled:
            state = _("disabled")
            icon = icons["off"]
        if timer.failed:
            state = _("failed")
            icon = icons["failed"]
        return (timer, icon, PowerTimerList.timertype[timer.timerType], atEnd, state, timeText, repeatIcon)

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
            self.session.nav.PowerTimer.cleanup()
            self.refill()
            self.updateState()

    def removeTimerQuestion(self):
        cur = self.getCurrentTimer()
        if not cur:
            return

        self.session.openWithCallback(self.removeTimer, MessageBox, _("Do you really want to delete this timer ?"), default=False)

    def removeTimer(self, result):
        if not result:
            return
        cur = self.getCurrentTimer()
        if cur:
            timer = cur
            timer.afterEvent = AFTEREVENT.NONE
            self.session.nav.PowerTimer.removeEntry(timer)
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
        data = (int(time() + 60), int(time() + 120))
        self.addTimer(PowerTimerEntry(checkOldTimers=True, *data))

    def addTimer(self, timer):
        self.session.openWithCallback(self.finishedAdd, TimerEntry, timer)

    def finishedEdit(self, answer):
        if answer[0]:
            entry = answer[1]
            self.session.nav.PowerTimer.timeChanged(entry)
            self.fillTimerList()
            self.updateState()
        else:
            print("[PowerTimerEdit] PowerTimeredit aborted")

    def finishedAdd(self, answer):
        if answer[0]:
            entry = answer[1]
            self.session.nav.PowerTimer.record(entry)
            self.fillTimerList()
            self.updateState()
        else:
            print("[PowerTimerEdit] Timeredit aborted")

    def finishSanityCorrection(self, answer):
        self.finishedAdd(answer)

    def leave(self):
        self.session.nav.PowerTimer.on_state_change.remove(self.onStateChange)
        self.close()

    def onStateChange(self, _entry):
        self.refill()
        self.updateState()


class PowerTimerEditListSummary(ScreenSummary):
    def __init__(self, session, parent):
        ScreenSummary.__init__(self, session, parent=parent)
        self["timertype"] = StaticText("")
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

    def selectionChanged(self, timerType, timeText, duration, state):
        self["timertype"].text = PowerTimerList.timertype.get(timerType, "")
        self["time"].text = timeText
        self["duration"].text = duration
        self["state"].text = state
