#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr 12 10:09:11 2020

@author: Jürgen Probst
"""

import sys
import tkinter as tk
from tkinter import filedialog
from xml.etree import ElementTree

class Reader:
    def __init__(self, filename):
        """Read and parse an xml file exported from SMS Backup and Restore App.

        """
        self.filename = filename
        self.root = ElementTree.parse(filename).getroot()

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack(fill=tk.BOTH, expand=1)
        self.create_widgets()

    def create_widgets(self):

        self.srcframe = tk.Frame(self, pady=5)
        self.srcframe.pack(side=tk.TOP, fill=tk.X, expand=0)

        tk.Label(self.srcframe, text="Eingabedatei:").pack(side=tk.LEFT)
        self.srcfile_edt = tk.Entry(self.srcframe)
        self.srcfile_edt.pack(side=tk.LEFT, fill=tk.X, expand=1, pady=2)
        self.srcfile_edt.bind('<Return>', self.srcfile_edt_return)
        tk.Button(
            self.srcframe, text="...", command=self.open_file_dialog, pady=2).pack(
                side=tk.LEFT, fill=tk.X)

        self.mainframe = tk.PanedWindow(self, sashwidth=3)
        self.mainframe.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)


        self.listedt = tk.Listbox(self.mainframe)
        self.mainframe.add(self.listedt)

        self.textedt = tk.Text(self.mainframe)
        self.mainframe.add(self.textedt)


    def open_file_dialog(self):
        fname = filedialog.askopenfilename()
        if fname:
            self.srcfile_edt.delete(0, tk.END)
            self.srcfile_edt.insert(0, fname)
            self.open_file()

    def open_file(self):
        self.reader = Reader(self.srcfile_edt.get())

    def srcfile_edt_return(self, event):
        if not self.srcfile_edt.get():
            # no filename entered yet:
            self.open_file_dialog()
        else:
            self.open_file()


def main(argv=sys.argv[1:]):
    if len(argv) < 1:
        print("Bitte Dateinamen angeben beim Starten.")
        return
    filename = argv[0]
    print("Öffne Datei %s" % filename)



if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    # set window title
    root.wm_title("SMS Backup Reader")
    root.geometry("640x600")
    app.mainloop()