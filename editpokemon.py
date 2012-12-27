#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, sys, struct
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import QtCore, QtGui 
from editdlg import EditDlg, EditWidget

import config
from language import translate
import pokeversion
from nds import narc, txt
from nds.fmt import dexfmt

files = pokeversion.pokemonfiles

stats = ("hp", "atk", "def", "speed", "spatk", "spdef")

class EditEVs(EditWidget):
    def __init__(self, parent=None):
        super(EditEVs, self).__init__(EditWidget.NONE, parent)
        self.valuers = []
        x = 0
        y = 0
        for stat in stats:
            sb = EditWidget(EditWidget.SPINBOX, self)
            sb.setValues([0, 3])
            sb.setName(translate("pokemonstat_"+stat)+" EV")
            width, height = sb.getGeometry()
            sb.setGeometry(QRect(x, y, width, height))
            sb.changed = self.changed
            self.valuers.append(sb)
            y += height
        self.setGeometry(0, 0, width, y)
    def setValue(self, value):
        for i in range(6):
            self.valuers[i].setValue(value&3)
            value >>= 2
    def getValue(self):
        value = 0
        for i in range(6):
            value |= self.values[i].getValue()<<(i*2)
        return value
    def getGeometry(self):
        return (self.geometry().width(), self.geometry().height())
        
class EditTMs(EditWidget):
    def __init__(self, parent=None):
        super(EditTMs, self).__init__(EditWidget.TAB, parent)
        self.tabname = "TMs/HMs"
        self.valuers = []
        x = 0
        y = 0
        off = 0
        txt = "%s%%02i"%translate("pokemontm")
        if pokeversion.gens[config.project["versioninfo"][0]] == 4:
            tmmax = 92
        else:
            tmmax = 95
        for i in range(104):
            sb = EditWidget(EditWidget.CHECKBOX, self)
            if i == 60:
                x = width
                mheight = y
                y = 0
            elif i == tmmax:
                txt = "%s%%02i"%translate("pokemonhm")
                off = tmmax
            sb.setName(txt%(i-off+1))
            width, height = sb.getGeometry()
            sb.setGeometry(QRect(x, y, width, height))
            sb.changed = self.changed
            self.valuers.append(sb)
            y += height
        self.setGeometry(0, 0, width*2, mheight)
    def setValue(self, value):
        tmdata = struct.unpack("B"*13, value)
        for i, d in enumerate(tmdata):
            for j in range(8):
                idx = i*8+j
                self.valuers[idx].setValue((tmdata[i]>>j)&1)
    def getValue(self):
        value = 0
        return value

class EditPokemon(EditDlg):
    wintitle = "Pokemon Editor"
    def __init__(self, parent=None):
        super(EditPokemon, self).__init__(parent)
        game = config.project["versioninfo"][0]
        self.personalfname = config.project["directory"]+"fs"+files[
            game]["Personal"]
        self.textfname = config.project["directory"]+"fs"+pokeversion.textfiles[
            game]["Main"]
        self.textnarc = narc.NARC(open(self.textfname, "rb").read())
        self.pokemonnames = self.getTextEntry("Pokemon")
        self.typenames = self.getTextEntry("Types")
        self.itemnames = self.getTextEntry("Items")
        self.abilitynames = self.getTextEntry("Abilities")
        self.chooser.addItems(self.pokemonnames)
        self.addEditableTab("Personal", dexfmt[game.lower()],
            self.personalfname, self.getPokemonWidget)
    def getTextEntry(self, entry):
        version = config.project["versioninfo"]
        entrynum = pokeversion.textentries[version[0]][pokeversion.langs[
            version[1]]][entry]
        if pokeversion.gens[version[0]] == 4:
            text = txt.gen4get(self.textnarc.gmif.files[entrynum])
        elif pokeversion.gens[version[0]] == 5:
            text = txt.gen5get(self.textnarc.gmif.files[entrynum])
        else:
            raise ValueError
        ret = []
        for t in text:
            ret.append(t[1])
        return ret
    def getPokemonWidget(self, name, size, parent):
        choices = None
        if name[:4] == "type":
            choices = self.typenames
        elif name[:4] == "item":
            choices = self.itemnames
        elif name[:7] == "ability":
            choices = self.abilitynames
        elif name[:8] == "egggroup":
            choices = translate("pokemonegggroups")
        elif name == "evs":
            return EditEVs(parent)
        elif name == "tms":
            return EditTMs(None)
        elif name in ("exprate", "color"):
            choices = translate("pokemon"+name+"s")
        if choices:
            cb = EditWidget(EditWidget.COMBOBOX, parent)
            cb.setValues(choices)
            cb.setName(translate(name))
            return cb
        sb = EditWidget(EditWidget.SPINBOX, parent)
        if size == 'H':
            sb.setValues([0, 0xFFFF])
        else:
            sb.setValues([0, 0xFF])
        sb.setName(translate(name))
        return sb
    
def create():
    if not config.project:
        QMessageBox.critical(None, translations["error_noromloaded_title"], 
            translations["error_noromloaded"])
        return
    EditPokemon(config.mw).show()