#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr 12 10:09:11 2020

@author: Jürgen Probst
"""

import os, re, base64, time #, io
import tkinter as tk
from tkinter import filedialog
from xml.etree.ElementTree import XMLParser

try:
    from PIL import ImageTk
except ModuleNotFoundError:
    ImageTk = False

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

#plan:
# - read file line by line - ok
# - correct line on the fly - ok
# - sent/serve corrected line to xml-parser (SAX or iterparse style) ok
# - event is e.g. a <sms>, create a namedtuple for each entry with all data
# - make dict: add namedtuple, keys are conversation partner, items are lists of smss
# - also need list of conversation partners? (or use keys of dict?)
# - another list of all smss, sorted by date (or have a special entry 'all' in dict?)


class Message:
    def __init__(self, attrib):
        """Creates an SMS message data set. *attrib* is the attribute dict
        returned by the xml reader.

        """

        # from here: https://synctech.com.au/sms-backup-restore/fields-in-xml-backup-files/
        #
        #    protocol - Protocol used by the message, its mostly 0 in case of SMS messages.
        #    address - The phone number of the sender/recipient.
        #    date - The Java date representation (including millisecond) of the time when the message was sent/received. Check out www.epochconverter.com for information on how to do the conversion from other languages to Java.
        #    type - 1 = Received, 2 = Sent, 3 = Draft, 4 = Outbox, 5 = Failed, 6 = Queued
        #    subject - Subject of the message, its always null in case of SMS messages.
        #    body - The content of the message.
        #    toa - n/a, defaults to null.
        #    sc_toa - n/a, defaults to null.
        #    service_center - The service center for the received message, null in case of sent messages.
        #    read - Read Message = 1, Unread Message = 0.
        #    status - None = -1, Complete = 0, Pending = 32, Failed = 64.
        #    readable_date - Optional field that has the date in a human readable format.
        #    contact_name - Optional field that has the name of the contact.
        #    All the field values are read as is from the underlying database and no conversion is done by the app in most cases.
        self._address = attrib["address"]
        self._date = attrib["date"]
        self._stype = int(attrib["type"])
        self._text = attrib["body"]
        self._readable_date = attrib.get(
                "readable_date",
                time.strftime(
                        '%d.%m.%Y %H:%M:%S',
                        time.localtime(float(self._date) / 1000)))
        self._contact_name = attrib["contact_name"]

        self.contact = self._contact_name
        if self.contact == '(Unknown)':
            self.contact = self._address

    def is_received(self):
        """message was received"""
        return self._stype == 1

    def is_sent(self):
        """message was sent"""
        return self._stype == 2

    def is_neither_sent_nor_received(self):
        """message is a draft, outbox, failed or queued."""
        return self._stype != 1 and self._stype != 2

    def get_type_text(self):
        return [
            "Empfangen", "Gesendet", "Entwurf",
            "Ausgang", "Fehler", "Queue"][self._stype - 1]

    def get_contact(self):
        return self.contact

    def get_address(self):
        return self._address

    def get_date(self):
        return self._readable_date

    def get_text(self):
        return self._text

    def has_data(self):
        return False

    def has_multi_addresses(self):
        return False

class MMS(Message):
    def __init__(self, attrib):
        """Creates an MMS message data set. *attrib* is the attribute dict
        returned by the xml reader. parts and addrs must be added with
        the appropiate methods.

        """

        # from here: https://synctech.com.au/sms-backup-restore/fields-in-xml-backup-files/
        #
        # An MMS message comprises of a few different elements with a structure like this:
        # <mms>
        #    <parts>
        #       <part/>
        #       <part/>
        #   </parts>
        #   <addrs>
        #       <addr/>
        #       <addr/>
        #   </addr>
        # </mms>
        #
        # The mms element contains most of the metadata about the message like the phone numbers, date/time etc.
        # The part elements contain the actual content of the message like a photo or video or the text message.
        # The addr elements contain the list of recipients of the messages in case of group messages.
        # The actual attributes in the elements vary depending on the phone but here are some of the common attributes:
        #     mms
        #         date - The Java date representation (including millisecond) of the time when the message was sent/received. Check out www.epochconverter.com for information on how to do the conversion from other languages to Java.
        #         ct_t - The Content-Type of the message, usually "application/vnd.wap.multipart.related"
        #         msg_box - The type of message, 1 = Received, 2 = Sent, 3 = Draft, 4 = Outbox
        #         rr - The read-report of the message.
        #         sub - The subject of the message, if present.
        #         read_status - The read-status of the message.
        #         address - The phone number of the sender/recipient.
        #         m_id - The Message-ID of the message
        #         read - Has the message been read
        #         m_size - The size of the message.
        #         m_type - The type of the message defined by MMS spec.
        #         readable_date - Optional field that has the date in a human readable format.
        #         contact_name - Optional field that has the name of the contact.
        #     part
        #         seq - The order of the part.
        #         ct - The content type of the part.
        #         name - The name of the part.
        #         chset - The charset of the part.
        #         cl - The content location of the part.
        #         text - The text content of the part.
        #         data - The base64 encoded binary content of the part.
        #     addr
        #         address - The phone number of the sender/recipient.
        #         type - The type of address, 129 = BCC, 130 = CC, 151 = To, 137 = From
        #         charset - Character set of this entry
        self._address = attrib["address"]
        self._date = attrib["date"]
        self._stype = int(attrib["msg_box"])
        self._readable_date = attrib.get(
                "readable_date",
                time.strftime(
                        '%d.%m.%Y %H:%M:%S',
                        time.localtime(float(self._date) / 1000)))
        self._contact_name = attrib["contact_name"]
        self._text = '' # can be updated later if parts contain text
        self._parts = []
        self._addrs = []
        self._num_data_blocks = 0
        self._num_text_blocks = 0

        self.contact = self._contact_name
        if self.contact == '(Unknown)':
            self.contact = self._address

    # DONE with parts:
    # if ct is application/smil, just skip it (hope this is not too risky to miss something important)
    # if ct is text/plain, add the text as message
    # otherwise, if there is text != 'null', same as above. (should maybe never be, but who knows, I don't want something to fall under the table)
    #    also otherwise, if there is data, save it as base64bytes for later
    #    also save 'name' field, could be file name.
    #    also save content type, because if image we can show it later
    #       Put these three together as dict in a list
    #
    # Then later, when message is shown:
    # Show all parts, i.e.
    #    all texts if any
    #    and all images (we know it from content type)
    #    and note when there were other files with filename. Say the file can be created when messages are saved
    #      maybe allow saving this file if clicked on file name?
    #      For these files, create a filename including date and contact

    def add_part(self, attrib):
        content_type = attrib["ct"]
        if content_type == "application/smil":
            # ignore this for now. Is attached as kind of header to every mms data:
            return
        elif content_type == "text/plain":
            if not self._text:
                self._text = attrib["text"]
            else:
                # there is already some text, add the new text
                # after some newlines:
                self._text = "\n\n".join([self._text, attrib["text"]])
        else:
            if "text" in attrib and attrib["text"] != "null":
                # some other kind of text which is not 'text/plain'
                if not self._text:
                    self._text = attrib["text"]
                else:
                    # there is already some text, add the new text
                    # after some newlines:
                    self._text = "\n\n".join([self._text, attrib["text"]])
            if "data" in attrib and attrib["data"] != "null":
                filename = attrib["name"]
                timestr = time.strftime(
                        "_%Y-%m-%d_%H-%M-%S",
                        time.localtime(float(self._date) / 1000))
                if filename == 'null':
                    # no filename given
                    # very hackish: just take 'jpeg' part of e.g. 'image/jpeg':
                    ext = content_type.partition('/')[2]
                    # build filename from contact and time:
                    filename = ''.join(
                        ["MMS_", self.contact, timestr, '.', ext])
                else:
                    # Add contact name and time to filename, to make it unique:
                    filename = ''.join(
                        ["MMS_", self.contact, timestr, '_', filename])
                base64bytes = attrib["data"].encode()
                self._parts.append({
                        'data': base64bytes,
                        'name': filename,
                        'ctype': content_type})

    # TODO with addrs:
    # if there are multiple senders, print them
    # (if only one, assume it is the same as contact and ignore)
    # if there are multiple recepients, print them
    # (if only one, assume it is the same as receiver and ignore)
    def add_addr(self, attrib):
        self._addrs.append(attrib)

    def has_data(self):
        return bool(self._parts)

    def has_multi_addresses(self):
        return bool(self._addrs)

    def get_data(self):
        return self._parts

    def get_recipients(self):
        return self._addrs

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
            return #TODO remove urgently!
            data = Message(attrib)
            key = data.get_contact()
            if not key in self._data:
                self._data[key] = []
            self._data[key].append(data)
            self._data['__all__'].append(data)
        elif tag == 'mms':
            key = attrib["contact_name"]
            if key == '(Unknown)':
                key = attrib["address"]
            data = MMS(attrib)
            key = data.get_contact()
            if not key in self._data:
                self._data[key] = []
            self._data[key].append(data)
            self._data['__all__'].append(data)
        elif tag == "part":
            self._data['__all__'][-1].add_part(attrib)
        elif tag == "addr":
            self._data['__all__'][-1].add_addr(attrib)
        elif tag == 'parts' or tag == 'addrs':
            if attrib:
                print(tag, attrib, "should actually be empty")
        else:
            # at least print the unprocessed tags:
            print(tag, attrib)

    def end(self, tag):
        """Called for each closing tag. """
        if tag == 'mms':
            # create new pointers pointing to empty lists:
            self._last_parts = []
            self._last_addrs = []

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
        self.messages = {}
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

        self.messages = parser.close()
        # sort by date. This is neccessary because mms items always come
        # after the sms items in the xml:
        for key, msglist in self.messages.items():
            self.messages[key] = sorted(
                    msglist, key=lambda s: s._date)
        self.contacts = sorted(
            self.messages.keys(), key=lambda s: s.casefold())
        self.contacts.remove('__all__')

    def get_all_messages(self):
        return self.messages['__all__']

    def get_message_list(self, contact):
        return self.messages[contact]

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
        scrollbar2 = tk.Scrollbar(frame, orient=tk.HORIZONTAL)
        self.textedt = tk.Text(
            frame,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            xscrollcommand=scrollbar2.set,
            background='gray80')
        scrollbar.config(command=self.textedt.yview)
        scrollbar2.config(command=self.textedt.xview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar2.pack(side=tk.BOTTOM, fill=tk.X)
        self.textedt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        mainframe.add(frame)

    def insert_text_to_textedit(self, text, tag):
        """Adds text to tkinter Text. If 'text' contains unallowed signs,
        like emojis, replace them with replacement sign.

        """
        try:
            self.textedt.insert(tk.END, '\n' + text + '\n\n', tag)
        except tk.TclError:
            pieces = ['\n']
            copied = 0
            for i in range(len(text)):
                if ord(text[i]) >= 0x10000:
                    if i > copied:
                        pieces.append(text[copied:i])
                    pieces.append(chr(0xFFFD)) # replacement sign
                    copied = i + 1
            pieces.append(text[copied:])
            pieces.append('\n\n')
            self.textedt.insert(tk.END, "".join(pieces), tag)

    def show_hand_cursor(self, event):
        self.textedt.config(cursor="hand2")

    def hide_hand_cursor(self, event):
        self.textedt.config(cursor='xterm')

    def get_saveas_event(self, filename, data):
        def save_as(event):
            fname = filedialog.asksaveasfilename(initialfile=filename)
            if fname:
                with open(fname, mode='wb') as f:
                    f.write(base64.decodebytes(data))
                print("saved MMS content as '%s'" % fname)
        return save_as

    def select_contact(self, event):
        selection = self.listedt.curselection()[0]
        if selection == 0:
            contact = '__all__'
        else:
            contact = self.reader.get_contacts_list()[selection - 1]

        self.textedt.config(state=tk.NORMAL, background='gray90')
        self.textedt.delete(1.0, tk.END)
        self.textedt.tag_config(
            "received", background="light blue", rmargin=40,
            justify=tk.LEFT)
        self.textedt.tag_config(
            "sent", background="pale green", lmargin1=40, lmargin2=40,
            justify=tk.RIGHT)
        self.textedt.tag_config(
            "other", background="light pink", lmargin1=40, lmargin2=40,
            justify=tk.RIGHT)
        self.textedt.tag_config(
            "grayed",
            foreground='gray', offset=10)
        self.textedt.tag_config(
            "link", underline=1)
        self.textedt.tag_bind(
            "link", "<Enter>", self.show_hand_cursor)
        self.textedt.tag_bind(
            "link", "<Leave>", self.hide_hand_cursor)

        self.textedt.insert(tk.END, contact + '\n\n')

        #img = tk.PhotoImage(file="emoji.png").subsample(2)
        #img = ImageTk.PhotoImage(Image.open('emoji.png'))
        #self.textedt.image_create(tk.END, image=img)
        # store a reference to prevent it being garbage-collected:
        #self.textedt.img = img

        # clear previous images:
        self._current_images = []

        for i, message in enumerate(self.reader.get_message_list(contact)):
            if message.is_received():
                tag = "received"
            elif message.is_sent():
                tag = "sent"
            else:
                tag = "other"
            text = message.get_text()
            if text:
                self.insert_text_to_textedit(text, tag)
            if message.has_data():
                data = message.get_data()
                self.textedt.imgs = []
                for d in data:
                    if d['ctype'].startswith('image/') and ImageTk:

                        #iob = io.BytesIO(base64.decodebytes(d['data']))
                        #img = ImageTk.PhotoImage(Image.open(iob))
                        img = ImageTk.PhotoImage(data=base64.decodebytes(d['data']))

                        #print(img.width(), img.height(), d['name'], d['ctype'])
                        # TODO: if image is too big (bigger than what?),
                        # decrease image size?

                        self.textedt.insert(tk.END, '\n', tag)
                        self.textedt.image_create(tk.END, image=img)

                        # use unique tagname:
                        self.textedt.tag_bind(
                            "link%i" % i, "<Button-1>",
                            self.get_saveas_event(d['name'], d['data']))
                        self.textedt.tag_add("link", 'end-1l', 'end')
                        self.textedt.tag_add("link%i" % i, 'end-1l', 'end')

                        # store a reference to prevent it being garbage-collected:
                        self._current_images.append(img)
                        # this tag will be written over the image:
                        self.textedt.insert(tk.END, '\n\n', tag)
                    else:
                        #print(d['ctype'])
                        # use unique tagname:
                        self.textedt.tag_bind(
                            "link%i" % i, "<Button-1>",
                            self.get_saveas_event(d['name'], d['data']))
                        self.textedt.insert(tk.END, '\nAnhang: ', tag)
                        self.textedt.insert(
                            tk.END, d['name'] + '\n\n',
                            (tag, "link", "link%i" % i))


            #if message.has_multi_addresses():
            #    print('todo')

            self.textedt.insert(
                tk.END, message.get_type_text(), (tag, 'grayed'))

            self.textedt.insert(
                tk.END, ': ' + message.get_date() + ', ' + message.get_contact() + '\n', (tag, 'grayed'))
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
        fname = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text', '*.txt'), ('Alle Dateien', '*.*')])
        if fname:
            # folder name in case there are attachments to be saved:
            foldername = os.path.splitext(fname)[0] + "_MMS_attachments"
            if os.path.exists(foldername):
                i = 1
                while os.path.exists("%s_%02i" % (foldername, i)):
                    i += 1
                foldername = "%s_%02i" % (foldername, i)
            folder_created = False
            with open(fname, mode='w', encoding="utf-16") as f:
                # I am using utf-16 because Windows just won't get utf-8 and
                # I don't want to write a BOM (with utf-8-sig)
                selection = self.listedt.curselection()[0]
                if selection == 0:
                    contact = '__all__'
                else:
                    contact = self.reader.get_contacts_list()[selection - 1]
                for message in self.reader.get_message_list(contact):
                    f.write(message.get_type_text())
                    f.write(' ' + message.get_date() + ', ')
                    f.write(message.get_contact() + ':\n')
                    f.write(message.get_text())
                    if message.has_data():
                        data = message.get_data()
                        for d in data:
                            f.write(
                                "\n+Anhang (%s): %s" % (d["ctype"], d["name"]))
                            if not folder_created:
                                os.mkdir(foldername)
                                folder_created = True
                            afname = os.path.join(foldername, d["name"])
                            with open(afname, mode='wb') as af:
                                af.write(base64.decodebytes(d["data"]))
                            print("saved MMS content as '%s'" % afname)
                    f.write('\n\n')
                print("saved all messages of selected contact to '%s'" % fname)


    def srcfile_edt_return(self, event):
        if not self.srcfile_edt.get():
            # no filename entered yet:
            self.open_file_dialog()
        else:
            self.open_file()


if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    # set window title
    root.wm_title("SMS Backup Reader")
    root.geometry("640x600")
    #app.srcfile_edt.insert(0, 'sms_example.xml') #TODO remove
    #app.srcfile_edt.insert(0, 'Beispielmms.xml') #TODO remove
    app.mainloop()
