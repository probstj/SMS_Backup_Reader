#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr 12 10:09:11 2020

@author: Jürgen Probst
"""

import sys, re
import tkinter as tk
from tkinter import filedialog
from xml.etree.ElementTree import XMLParser
from collections import namedtuple
#from PIL import ImageTk, Image

"""
https://stackoverflow.com/questions/7693515/why-is-elementtree-raising-a-parseerror#7693834
https://www.w3.org/TR/2008/REC-xml-20081126/#charsets
https://en.wikipedia.org/wiki/GSM_03.38

https://support.bandwidth.com/hc/en-us/articles/360010234793-What-is-SMS-Messaging-Encoding-and-Why-is-it-Important-
https://en.wikipedia.org/wiki/Plane_(Unicode)#Basic_Multilingual_Plane

https://github.com/danzek/sms-backup-and-restore-parser
https://github.com/danzek/sms-backup-and-restore-parser/blob/master/cmd/sbrparser/main.go
https://synctech.com.au/sms-backup-restore/view-or-edit-backup-files-on-computer/
https://synctech.com.au/sms-backup-restore/fields-in-xml-backup-files/
https://mattj.io/sms-backup-reader-2/main

https://stackoverflow.com/questions/38147259/how-to-work-with-surrogate-pairs-in-python
http://www.unicode.org/faq/utf_bom.html#utf16-3
https://unicodebook.readthedocs.io/unicode_encodings.html#surrogates

http://www.unicode.org/emoji/charts/index.html
http://www.unicode.org/emoji/charts/full-emoji-list.html
https://apps.timwhitlock.info/unicode/

https://stackoverflow.com/questions/17287700/how-to-parse-a-xml-file-into-a-tree-in-python/17288001#17288001
https://docs.python.org/3/library/xml.etree.elementtree.html#xmlparser-objects

"""

#TODO
# - read file line by line - ok
# - correct line on the fly - ok
# - sent/serve corrected line to xml-parser (SAX or iterparse style)
# - event is e.g. a <sms>, create a namedtuple for each entry with all data
# - make dict: add namedtuple, keys are conversation partner, items are lists of smss
# - also need list of conversation partners? (or use keys of dict?)
# - another list of all smss, sorted by date (or have a special entry 'all' in dict?)

SMSDataSet = namedtuple('SMSDataSet',
    "address date stype body read status date_sent "
    "readable_date contact_name")

class XML_Target:
    """The target class for the xml parser.
    Receives calls from the XML parser with which it builds a dict
    of SMSDataSet objects. The main dict's keys will be
    conversations partner and the items are lists of SMSDataSet objects.

    """
    def __init__(self):
        self._data = {"__all__": []} # data collector

    def start(self, tag, attrib):
        """Called for each opening tag."""
        if tag == 'sms':
            key = attrib["contact_name"]
            if key == '(Unknown)':
                key = attrib["address"]
            data = SMSDataSet(
                address = attrib["address"],
                date = attrib["date"],
                stype = int(attrib["type"]),
                body = attrib["body"],
                read = int(attrib["read"]),
                status = int(attrib["status"]),
                date_sent = attrib["date_sent"],
                readable_date = attrib["readable_date"],
                contact_name = attrib["contact_name"])
            if not key in self._data:
                self._data[key] = []
            self._data[key].append(data)
            self._data['__all__'].append(data)
        else:
            # at least print the unprocessed tags:
            print(tag, attrib)

    def end(self, tag):
        """Called for each closing tag. """
        pass

    def data(self, data):
        """Called for each encountered text data."""
        # There shouldn't be any data in the xml (no "text")
        pass

    def close(self):
        """Return the dict. Can be called when all data has been parsed."""
        return self._data

class Reader:
    def __init__(self, filename):
        """Read and parse an xml file exported from SMS Backup and Restore App.

        """
        self.filename = filename
        self.sms = {}
        self.contacts = []

        # regex to find and filter surrogate-coded UTF-16 emojis:
        # these are not allowed in xml, so must be translated manually
        regex = re.compile("&#(\d{5});&#(\d{5});")

        # Expects a match of the pattern in `regex`, with two groups.
        # returns the two utf-16 (surrogate) codes translated to proper
        # unicode codes:
        def repl(match):
            g = match.groups()
            pair = chr(int(g[0])), chr(int(g[1]))
            return "".join(pair).encode(
                        'utf-16', 'surrogatepass').decode('utf-16')

        # the xml parser's target:
        target = XML_Target()
        # the xml parser:
        parser = XMLParser(target=target)
        with open(self.filename, "r", encoding="utf-8") as f:
            for line in f:
                corrected_line = regex.sub(repl, line)
                parser.feed(corrected_line)

        self.sms = parser.close()
        self.contacts = sorted(self.sms.keys())
        self.contacts.remove('__all__')

    def get_all_sms(self):
        return self.sms['__all__']

    def get_sms_list(self, contact):
        return self.sms[contact]

    def get_contacts_list(self):
        return self.contacts


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack(fill=tk.BOTH, expand=1)
        self.create_widgets()

    def create_widgets(self):
        srcframe = tk.Frame(self, pady=5)
        srcframe.pack(side=tk.TOP, fill=tk.X, expand=0)

        tk.Label(srcframe, text="Eingabedatei:").pack(side=tk.LEFT)
        self.srcfile_edt = tk.Entry(srcframe, background='gray90')
        self.srcfile_edt.pack(side=tk.LEFT, fill=tk.X, expand=1, pady=2)
        self.srcfile_edt.bind('<Return>', self.srcfile_edt_return)
        tk.Button(
            srcframe, text="...", command=self.open_file_dialog, pady=2).pack(
                side=tk.LEFT, fill=tk.X)

        mainframe = tk.PanedWindow(self, sashwidth=3)
        mainframe.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        # listbox
        frame = tk.Frame(mainframe)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        self.listedt = tk.Listbox(
            frame,
            selectmode=tk.BROWSE,
            exportselection=0,
            yscrollcommand=scrollbar.set,
            background='gray80')
        scrollbar.config(command=self.listedt.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listedt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        #self.listedt.bind("<ButtonRelease-1>", self.select_contact)
        #self.listedt.bind("<space>", self.select_contact)
        #self.listedt.bind("<Return>", self.select_contact)
        self.listedt.bind("<<ListboxSelect>>", self.select_contact)
        mainframe.add(frame)

        # text
        frame = tk.Frame(mainframe)
        self.savebtn = tk.Button(
            frame, text="Speichern",
            command=self.save_file_dialog, state=tk.DISABLED)
        self.savebtn.pack(
                side=tk.BOTTOM, fill=tk.BOTH)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        self.textedt = tk.Text(
            frame,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            background='gray80')
        scrollbar.config(command=self.textedt.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.textedt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        mainframe.add(frame)

    def select_contact(self, event):
        selection = self.listedt.curselection()[0]
        if selection == 0:
            contact = '__all__'
        else:
            contact = self.reader.get_contacts_list()[selection - 1]

        self.textedt.config(state=tk.NORMAL, background='gray90')
        self.textedt.delete(1.0, tk.END)
        self.textedt.tag_config(
            "received", background="light blue", lmargin1=40, lmargin2=40,
            justify=tk.RIGHT)
        self.textedt.tag_config(
            "sent", background="pale green", rmargin=40,
            justify=tk.LEFT)
        self.textedt.tag_config(
            "other", background="light pink", rmargin=40,
            justify=tk.LEFT)
        self.textedt.tag_config(
            "grayed",
            foreground='gray', offset=10)
        self.textedt.insert(tk.END, contact + '\n\n')

        #img = tk.PhotoImage(file="emoji.png").subsample(2)
        #img = ImageTk.PhotoImage(Image.open('emoji.png'))
        #self.textedt.image_create(tk.END, image=img)
        # store a reference to prevent it being garbage-collected:
        #self.textedt.img = img

        for sms in self.reader.get_sms_list(contact):
            #type: 1 = Received, 2 = Sent, 3 = Draft, 4 = Outbox, 5 = Failed, 6 = Queued
            if sms.stype == 1:
                tag = "received"
            elif sms.stype == 2:
                tag = "sent"
            else:
                tag = "other"
            try:
                self.textedt.insert(tk.END, '\n' + sms.body + '\n\n', tag)
            except tk.TclError:
                pieces = ['\n']
                copied = 0
                for i in range(len(sms.body)):
                    if ord(sms.body[i]) >= 0x10000:
                        if i > copied:
                            pieces.append(sms.body[copied:i])
                        pieces.append(chr(0xFFFD)) # replacement sign
                        copied = i + 1
                pieces.append(sms.body[copied:])
                pieces.append('\n\n')
                self.textedt.insert(tk.END, "".join(pieces), tag)

            self.textedt.insert(tk.END,
                    ["Empfangen", "Gesendet", "Entwurf", "Ausgang", "Fehler", "Queue"][sms.stype - 1],
                    (tag, 'grayed'))

            if selection == 0:
                # selected all contacts
                if sms.contact_name == '(Unknown)':
                    contact = sms.address
                else:
                    contact = sms.contact_name

            self.textedt.insert(
                tk.END, ': ' + sms.readable_date + ', ' + contact + '\n', (tag, 'grayed'))
            self.textedt.insert(tk.END, '\n')

        self.textedt.config(state=tk.DISABLED)
        self.savebtn.config(state=tk.NORMAL)


    def open_file_dialog(self):
        fname = filedialog.askopenfilename()
        if fname:
            self.srcfile_edt.delete(0, tk.END)
            self.srcfile_edt.insert(0, fname)
            self.open_file()

    def open_file(self):
        print("Öffne Datei", self.srcfile_edt.get())
        self.reader = Reader(self.srcfile_edt.get())
        self.listedt.delete(0, tk.END)
        self.listedt.insert(0, 'Alle')
        self.listedt.insert(tk.END, *self.reader.get_contacts_list())
        self.listedt.config(background='gray90')

    def save_file_dialog(self):
        fname = filedialog.asksaveasfilename()
        if fname:
            with open(fname, mode='w', encoding="utf-16") as f:
                # I am using utf-16 because Windows just won't get utf-8 and
                # I don't want to write a BOM (with utf-8-sig)
                selection = self.listedt.curselection()[0]
                if selection == 0:
                    contact = '__all__'
                else:
                    contact = self.reader.get_contacts_list()[selection - 1]
                for sms in self.reader.get_sms_list(contact):
                    if selection == 0:
                        # selected all contacts
                        if sms.contact_name == '(Unknown)':
                            contact = sms.address
                        else:
                            contact = sms.contact_name
                    f.write(
                        ["Empfangen", "Gesendet", "Entwurf", "Ausgang", "Fehler", "Queue"][sms.stype - 1])
                    f.write(' ' + sms.readable_date + ', ' + contact + ':\n')
                    f.write(sms.body + '\n\n')

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
    #app.srcfile_edt.insert(0, 'sms_example.xml') #TODO remove
    app.mainloop()
