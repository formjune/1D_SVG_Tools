"""
1D SVG TOOLS
Plugin is devoted for working with svg files. Splitting, Slicing into icons, merging them

;;; Copyright (C) 2019 Paul Kotelevets aka 1D_Inc, Andrey Menshikov 
;;; forum: https://forum.freecadweb.org/viewtopic.php?f=34&t=34687
;;;
;;; License = GPL v2
;;; This program is free software: you can redistribute it and/or modify
;;; it under the terms of the GNU General Public License as published by
;;; the Free Software Foundation, either version 3 of the License, or
;;; (at your option) any later version.
;;;
;;; This program is distributed in the hope that it will be useful,
;;; but WITHOUT ANY WARRANTY; without even the implied warranty of
;;; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
;;; GNU General Public License for more details. 
;;;
;;; You should have received a copy of the GNU General Public License
;;; along with this program.  If not, see http://www.gnu.org/licenses/


1D_ SVG_Tools is an addon for Blender 2.79, a toolkit that provides tools for working with SVG files.
SUPPORTED BLENDER VERSION = 2.79

- INSTALLATION



- TOOLS

SVG input split - splits svg file into pieces not exceeding selected size.
Input - SVG file of directory with SVG files to proceed.
Output - directory or empty for input directory.
Max Size - size for output files

SVG output merge - merge files into one. Output file will be named MERGE.SVG
Input - directory with SVG files to proceed.
Output - directory or empty for input directory.

SVG parse images
Scans SVG file for external image links and creates/rewrites Blneder interlnal text file called "svg parse images.txt" with found paths.
Input - SVG file to scan.
Crop Absolute Names - Convert absolute paths into "input directory + file name". Result for absolute names will be written into separated data block. Used for finding files near SVG (integrity check for archiving).

SVG copy images - Copy all files from external links found by SVG parse images into one directory.
Input - svg file to scan
Output - directory or empty for input directory. 

SVG icon slicer (+ Slice Transformed checkbox) - analysis tool. Creates temporal copy of SVG file, with all objects that have transformations moved to "TranMatrix" layer, as they cause problems with SVG icon slicing. Used for detecting objects with transformations and then fixing them in the original file.
Input - file to analyze
Output - directory or empty for input directory. In case of leaving empty name will be "input file + _out.svg"

SVG icon slicer (- Slice Transformed checkbox) - slices single SVG file with icons into multiple SVG icon files.
Icon filenames are taken from link of image objects from right side to the icon block.
Grids, Metadata and License data are copied from original SVG.
Objects with transformation matrices aren't supported properly, use Slice Transformed checkbox to detect them.
Text blocks are ignored.

Input - file to slice
Output - directory or empty for input directory. In case of leaving empty files will be written in new directory named "input file + out"
"""



import os
import collections
import string
import _markupbase
from html import unescape
import re
import warnings
from html.parser import interesting_normal, incomplete, entityref, charref, starttagopen, piclose, commentclose, \
    tagfind_tolerant, attrfind_tolerant, locatestarttagend_tolerant, endendtag, endtagfind
from xml.sax.saxutils import escape
import copy
import xml
import bpy


bl_info = {
    "name": "1D SVG Tools",
    "author": "Andrey Menshikov",
    "version": (1, 0, 0),
    "blender": (2, 7, 9),
    "location": "View3D > Tool Shelf > 1D > 1D SVG Tools",
    "description": "SVG file processing tools",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Mesh"}


class TagUnit(object):
    """container for svg tag"""

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.data = ""
        self.children = []

    def string(self, offset=0):
        """convert back to html"""

        result = "%s<%s" % (" " * offset, self.tag)
        attrs = []
        for key, value in self.attrs.items():
            attrs.append("%s%s=\"%s\"" % (" " * (offset + 3), key, value))

        if attrs:
            result += "\n%s>" % "\n".join(attrs)
        else:
            result += ">"

        children = []
        for child in self.children:
            children.append("%s" % child.string(offset + 3))
        if children:
            result += "\n%s</%s>" % ("\n".join(children), self.tag)
        elif self.data:
            result += "%s</%s>" % (self.data, self.tag)
        else:
            result += "</%s>" % self.tag

        return result


class HTMLParser(_markupbase.ParserBase):
    """Find tags and other markup and call handler functions.

    Usage:
        p = HTMLParser()
        p.feed(data)
        ...
        p.close()

    Start tags are handled by calling self.handle_starttag() or
    self.handle_startendtag(); end tags by self.handle_endtag().  The
    data between tags is passed from the parser to the derived class
    by calling self.handle_data() with the data as argument (the data
    may be split up in arbitrary chunks).  If convert_charrefs is
    True the character references are converted automatically to the
    corresponding Unicode character (and self.handle_data() is no
    longer split in chunks), otherwise they are passed by calling
    self.handle_entityref() or self.handle_charref() with the string
    containing respectively the named or numeric reference as the
    argument.
    """

    CDATA_CONTENT_ELEMENTS = ("script", "style")

    def __init__(self, *, convert_charrefs=True):
        """Initialize and reset this instance.

        If convert_charrefs is True (the default), all character references
        are automatically converted to the corresponding Unicode characters.
        """
        self.convert_charrefs = convert_charrefs
        self.reset()

    def reset(self):
        """Reset this instance.  Loses all unprocessed data."""
        self.rawdata = ''
        self.lasttag = '???'
        self.interesting = interesting_normal
        self.cdata_elem = None
        _markupbase.ParserBase.reset(self)

    def feed(self, data):
        r"""Feed data to the parser.

        Call this as often as you want, with as little or as much text
        as you want (may include '\n').
        """
        self.rawdata = self.rawdata + data
        self.goahead(0)

    def close(self):
        """Handle any buffered data."""
        self.goahead(1)

    __starttag_text = None

    def get_starttag_text(self):
        """Return full source of start tag: '<...>'."""
        return self.__starttag_text

    def set_cdata_mode(self, elem):
        self.cdata_elem = elem
        self.interesting = re.compile(r'</\s*%s\s*>' % self.cdata_elem, re.I)

    def clear_cdata_mode(self):
        self.interesting = interesting_normal
        self.cdata_elem = None

    # Internal -- handle data as far as reasonable.  May leave state
    # and data to be processed by a subsequent call.  If 'end' is
    # true, force handling all data as if followed by EOF marker.
    def goahead(self, end):
        rawdata = self.rawdata
        i = 0
        n = len(rawdata)
        while i < n:
            if self.convert_charrefs and not self.cdata_elem:
                j = rawdata.find('<', i)
                if j < 0:
                    # if we can't find the next <, either we are at the end
                    # or there's more text incoming.  If the latter is True,
                    # we can't pass the text to handle_data in case we have
                    # a charref cut in half at end.  Try to determine if
                    # this is the case before proceeding by looking for an
                    # & near the end and see if it's followed by a space or ;.
                    amppos = rawdata.rfind('&', max(i, n-34))
                    if (amppos >= 0 and
                        not re.compile(r'[\s;]').search(rawdata, amppos)):
                        break  # wait till we get all the text
                    j = n
            else:
                match = self.interesting.search(rawdata, i)  # < or &
                if match:
                    j = match.start()
                else:
                    if self.cdata_elem:
                        break
                    j = n
            if i < j:
                if self.convert_charrefs and not self.cdata_elem:
                    self.handle_data(unescape(rawdata[i:j]))
                else:
                    self.handle_data(rawdata[i:j])
            i = self.updatepos(i, j)
            if i == n: break
            startswith = rawdata.startswith
            if startswith('<', i):
                if starttagopen.match(rawdata, i): # < + letter
                    k = self.parse_starttag(i)
                elif startswith("</", i):
                    k = self.parse_endtag(i)
                elif startswith("<!--", i):
                    k = self.parse_comment(i)
                elif startswith("<?", i):
                    k = self.parse_pi(i)
                elif startswith("<!", i):
                    k = self.parse_html_declaration(i)
                elif (i + 1) < n:
                    self.handle_data("<")
                    k = i + 1
                else:
                    break
                if k < 0:
                    if not end:
                        break
                    k = rawdata.find('>', i + 1)
                    if k < 0:
                        k = rawdata.find('<', i + 1)
                        if k < 0:
                            k = i + 1
                    else:
                        k += 1
                    if self.convert_charrefs and not self.cdata_elem:
                        self.handle_data(unescape(rawdata[i:k]))
                    else:
                        self.handle_data(rawdata[i:k])
                i = self.updatepos(i, k)
            elif startswith("&#", i):
                match = charref.match(rawdata, i)
                if match:
                    name = match.group()[2:-1]
                    self.handle_charref(name)
                    k = match.end()
                    if not startswith(';', k-1):
                        k = k - 1
                    i = self.updatepos(i, k)
                    continue
                else:
                    if ";" in rawdata[i:]:  # bail by consuming &#
                        self.handle_data(rawdata[i:i+2])
                        i = self.updatepos(i, i+2)
                    break
            elif startswith('&', i):
                match = entityref.match(rawdata, i)
                if match:
                    name = match.group(1)
                    self.handle_entityref(name)
                    k = match.end()
                    if not startswith(';', k-1):
                        k = k - 1
                    i = self.updatepos(i, k)
                    continue
                match = incomplete.match(rawdata, i)
                if match:
                    # match.group() will contain at least 2 chars
                    if end and match.group() == rawdata[i:]:
                        k = match.end()
                        if k <= i:
                            k = n
                        i = self.updatepos(i, i + 1)
                    # incomplete
                    break
                elif (i + 1) < n:
                    # not the end of the buffer, and can't be confused
                    # with some other construct
                    self.handle_data("&")
                    i = self.updatepos(i, i + 1)
                else:
                    break
            else:
                assert 0, "interesting.search() lied"
        # end while
        if end and i < n and not self.cdata_elem:
            if self.convert_charrefs and not self.cdata_elem:
                self.handle_data(unescape(rawdata[i:n]))
            else:
                self.handle_data(rawdata[i:n])
            i = self.updatepos(i, n)
        self.rawdata = rawdata[i:]

    # Internal -- parse html declarations, return length or -1 if not terminated
    # See w3.org/TR/html5/tokenization.html#markup-declaration-open-state
    # See also parse_declaration in _markupbase
    def parse_html_declaration(self, i):
        rawdata = self.rawdata
        assert rawdata[i:i+2] == '<!', ('unexpected call to '
                                        'parse_html_declaration()')
        if rawdata[i:i+4] == '<!--':
            # this case is actually already handled in goahead()
            return self.parse_comment(i)
        elif rawdata[i:i+3] == '<![':
            return self.parse_marked_section(i)
        elif rawdata[i:i+9] == '<!doctype':
            # find the closing >
            gtpos = rawdata.find('>', i+9)
            if gtpos == -1:
                return -1
            self.handle_decl(rawdata[i+2:gtpos])
            return gtpos+1
        else:
            return self.parse_bogus_comment(i)

    # Internal -- parse bogus comment, return length or -1 if not terminated
    # see http://www.w3.org/TR/html5/tokenization.html#bogus-comment-state
    def parse_bogus_comment(self, i, report=1):
        rawdata = self.rawdata
        assert rawdata[i:i+2] in ('<!', '</'), ('unexpected call to '
                                                'parse_comment()')
        pos = rawdata.find('>', i+2)
        if pos == -1:
            return -1
        if report:
            self.handle_comment(rawdata[i+2:pos])
        return pos + 1

    # Internal -- parse processing instr, return end or -1 if not terminated
    def parse_pi(self, i):
        rawdata = self.rawdata
        assert rawdata[i:i+2] == '<?', 'unexpected call to parse_pi()'
        match = piclose.search(rawdata, i+2) # >
        if not match:
            return -1
        j = match.start()
        self.handle_pi(rawdata[i+2: j])
        j = match.end()
        return j

    # Internal -- handle starttag, return end or -1 if not terminated
    def parse_starttag(self, i):
        self.__starttag_text = None
        endpos = self.check_for_whole_start_tag(i)
        if endpos < 0:
            return endpos
        rawdata = self.rawdata
        self.__starttag_text = rawdata[i:endpos]

        # Now parse the data between i+1 and j into a tag and attrs
        attrs = []
        match = tagfind_tolerant.match(rawdata, i+1)
        assert match, 'unexpected call to parse_starttag()'
        k = match.end()
        self.lasttag = tag = match.group(1)
        while k < endpos:
            m = attrfind_tolerant.match(rawdata, k)
            if not m:
                break
            attrname, rest, attrvalue = m.group(1, 2, 3)
            if not rest:
                attrvalue = None
            elif attrvalue[:1] == '\'' == attrvalue[-1:] or \
                 attrvalue[:1] == '"' == attrvalue[-1:]:
                attrvalue = attrvalue[1:-1]
            if attrvalue:
                attrvalue = unescape(attrvalue)
            attrs.append((attrname, attrvalue))
            k = m.end()

        end = rawdata[k:endpos].strip()
        if end not in (">", "/>"):
            lineno, offset = self.getpos()
            if "\n" in self.__starttag_text:
                lineno = lineno + self.__starttag_text.count("\n")
                offset = len(self.__starttag_text) \
                         - self.__starttag_text.rfind("\n")
            else:
                offset = offset + len(self.__starttag_text)
            self.handle_data(rawdata[i:endpos])
            return endpos
        if end.endswith('/>'):
            # XHTML-style empty tag: <span attr="value" />
            self.handle_startendtag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
            if tag in self.CDATA_CONTENT_ELEMENTS:
                self.set_cdata_mode(tag)
        return endpos

    # Internal -- check to see if we have a complete starttag; return end
    # or -1 if incomplete.
    def check_for_whole_start_tag(self, i):
        rawdata = self.rawdata
        m = locatestarttagend_tolerant.match(rawdata, i)
        if m:
            j = m.end()
            next = rawdata[j:j+1]
            if next == ">":
                return j + 1
            if next == "/":
                if rawdata.startswith("/>", j):
                    return j + 2
                if rawdata.startswith("/", j):
                    # buffer boundary
                    return -1
                # else bogus input
                if j > i:
                    return j
                else:
                    return i + 1
            if next == "":
                # end of input
                return -1
            if next in ("abcdefghijklmnopqrstuvwxyz=/"
                        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
                # end of input in or before attribute value, or we have the
                # '/' from a '/>' ending
                return -1
            if j > i:
                return j
            else:
                return i + 1
        raise AssertionError("we should not get here!")

    # Internal -- parse endtag, return end or -1 if incomplete
    def parse_endtag(self, i):
        rawdata = self.rawdata
        assert rawdata[i:i+2] == "</", "unexpected call to parse_endtag"
        match = endendtag.search(rawdata, i+1) # >
        if not match:
            return -1
        gtpos = match.end()
        match = endtagfind.match(rawdata, i) # </ + tag + >
        if not match:
            if self.cdata_elem is not None:
                self.handle_data(rawdata[i:gtpos])
                return gtpos
            # find the name: w3.org/TR/html5/tokenization.html#tag-name-state
            namematch = tagfind_tolerant.match(rawdata, i+2)
            if not namematch:
                # w3.org/TR/html5/tokenization.html#end-tag-open-state
                if rawdata[i:i+3] == '</>':
                    return i+3
                else:
                    return self.parse_bogus_comment(i)
            tagname = namematch.group(1)
            # consume and ignore other stuff between the name and the >
            # Note: this is not 100% correct, since we might have things like
            # </tag attr=">">, but looking for > after tha name should cover
            # most of the cases and is much simpler
            gtpos = rawdata.find('>', namematch.end())
            self.handle_endtag(tagname)
            return gtpos+1

        elem = match.group(1) # script or style
        if self.cdata_elem is not None:
            if elem != self.cdata_elem:
                self.handle_data(rawdata[i:gtpos])
                return gtpos

        self.handle_endtag(elem)
        self.clear_cdata_mode()
        return gtpos

    # Overridable -- finish processing of start+end tag: <tag.../>
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    # Overridable -- handle start tag
    def handle_starttag(self, tag, attrs):
        pass

    # Overridable -- handle end tag
    def handle_endtag(self, tag):
        pass

    # Overridable -- handle character reference
    def handle_charref(self, name):
        pass

    # Overridable -- handle entity reference
    def handle_entityref(self, name):
        pass

    # Overridable -- handle data
    def handle_data(self, data):
        pass

    # Overridable -- handle comment
    def handle_comment(self, data):
        pass

    # Overridable -- handle declaration
    def handle_decl(self, decl):
        pass

    # Overridable -- handle processing instruction
    def handle_pi(self, data):
        pass

    def unknown_decl(self, data):
        pass

    # Internal -- helper to remove special character quoting
    def unescape(self, s):
        warnings.warn('The unescape method is deprecated and will be removed '
                      'in 3.5, use html.unescape() instead.',
                      DeprecationWarning, stacklevel=2)
        return unescape(s)


class StructureBuilder(HTMLParser):
    """creates tag based structure"""

    def __init__(self, file_name):
        HTMLParser.__init__(self)
        self._queue = []  # structure that helps return
        self.root = []
        self.current_tag = None
        self.feed(open(file_name, encoding="utf-8").read())

    def handle_starttag(self, tag, attrs):
        tag_unit = TagUnit(tag, attrs)
        if self.current_tag:
            self.current_tag.children.append(tag_unit)
        self.current_tag = tag_unit
        self._queue.append(tag_unit)

    def handle_endtag(self, tag):
        self._queue.pop(-1)
        if self._queue:
            self.current_tag = self._queue[-1]
        else:
            self.root.append(self.current_tag)
            self.current_tag = None

    def handle_data(self, data):
        if "&t" in data:
            data = data.replace("&t", "&amp;")
        if self.current_tag:
            self.current_tag.data += data


class SVGSplit(bpy.types.Operator):
    """splitter for xml. ported from someone code. literally I dunno how it works"""

    bl_idname = "mesh.am1dsvg_svg_split"
    bl_label = "SVG inout split"
    bl_options = {'REGISTER', 'UNDO'}

    # How much data we process at a time
    CHUNK_SIZE = 1024 * 1024

    # The sequence of element leading us to the current one
    path = []

    # How far we are in the current file
    cur_size = 0
    # From how much should we start another file
    MAX_SIZE = 1024 * 1024  # 1Mb

    # The current index
    cur_idx = 0
    # The current file handle we are writing to
    cur_file = None

    # The format string used to introduce the index in the file to be written
    FMT = ".%d"

    # The filename we are playing with
    out_dir = None
    root = None
    ext = None

    # The xml declaration of the file.
    xml_declaration = None

    # What was the signature of the last start element
    start = None

    # if we are currently in the process of changing file
    ending = False

    @staticmethod
    def attrs_s(attrs):
        """ This generate the XML attributes from an element attribute list """
        data = ['']
        for i in range(0, len(attrs), 2):
            data.append('%s="%s"' % (attrs[i], escape(attrs[i + 1])))
        return ' '.join(data)

    @classmethod
    def next_file(cls):
        """ This makes the decision to cut the current file and starta new one """

        if (not cls.ending) and (cls.cur_size > cls.MAX_SIZE):
            # size above threshold, and not already cls.ending

            cls.ending = True
            # Close the current elements
            for elem in reversed(cls.path):
                cls.end_element(elem[0])
            # Close the file
            cls.cur_file.close()
            # reset the size
            cls.cur_size = 0
            # Open another file
            cls.cur_idx += 1
            cls.cur_file = open(os.path.join(cls.out_dir, cls.root + cls.FMT % cls.cur_idx + cls.ext), 'wt', encoding="utf-8")
            if cls.xml_declaration is not None:
                cls.cur_file.write('<?xml%s?>\n' % cls.attrs_s(cls.xml_declaration))
            # Start again where we stopped
            for elem in cls.path:
                cls.start_element(*elem)
            # We are done 'cls.ending'
            cls.ending = False

    @classmethod
    def xml_decl(cls, version, encoding, standalone):
        data = ['version', version, 'encoding', encoding]
        if standalone != -1:
            data.extend(['standalone', 'yes' if standalone else 'no'])
        cls.xml_declaration = data
        cls.cur_file.write('<?xml%s?>\n' % cls.attrs_s(cls.xml_declaration))

    @classmethod
    def start_element(cls, name, attrs):
        """ Called by the parser when he meet a start element """
        if cls.start is not None:
            # Chaining starts after each others
            cls.cur_file.write('<%s%s>' % (cls.start[0], cls.attrs_s(cls.start[1])))
        cls.start = (name, attrs)
        if cls.ending:
            return
        cls.cur_size += len(name) + sum(len(k) for k in attrs)
        cls.path.append((name, attrs))

    @classmethod
    def end_element(cls, name):
        """ Caled by the parser when he meet an end element """

        if cls.start is not None:
            # Empty element, good, we did not wrote the start part
            cls.cur_file.write('<%s%s/>' % (cls.start[0], cls.attrs_s(cls.start[1])))
        else:
            # There was some data, close it normaly
            cls.cur_file.write('</%s>' % name)
        cls.start = None
        if cls.ending:
            return
        elem = cls.path.pop()
        assert elem[0] == name
        cls.cur_size += len(name)
        cls.next_file()

    @classmethod
    def char_data(cls, data):
        """ Called by the parser when he meet data """

        wroteStart = False
        if cls.start is not None:
            # The data belong to an element, we should write the start part first
            cls.cur_file.write('<%s%s>' % (cls.start[0], cls.attrs_s(cls.start[1])))
            cls.start = None
            wroteStart = True
        # ``escape`` is too much for us, only & and < ned to be escaped there ...
        data = data.replace('&', '&amp;')
        data = data.replace('<', '&lt;')
        if data == '>':
            data = '&gt;'
        cls.cur_file.write(data)
        cls.cur_size += len(data)
        if not wroteStart:
            # The data was outside of an element, it could be the right moment to
            # make the split
            cls.next_file()

    @classmethod
    def main(cls, filename_source, max_size, output_dir=None):
        # Create a parser

        p = xml.parsers.expat.ParserCreate()
        # We want to reproduce the input, so we are interested in the order of the
        # attributess
        p.ordered_attributes = 1

        # Set our callbacks (we are stripping comments out by not defining
        # callbacks for them)
        p.XmlDeclHandler = cls.xml_decl
        p.StartElementHandler = cls.start_element
        p.EndElementHandler = cls.end_element
        p.CharacterDataHandler = cls.char_data

        cls.cur_idx = 0
        cls.MAX_SIZE = max_size
        cls.FMT = "_split_%.3i"

        cls.out_dir, filename = os.path.split(filename_source)
        if output_dir is not None:
            cls.out_dir = output_dir

        cls.root, cls.ext = os.path.splitext(filename)

        cls.cur_file = open(os.path.join(cls.out_dir, cls.root + cls.FMT % cls.cur_idx + cls.ext), 'wt',
                            encoding="utf-8")

        with open(filename_source, "rt", encoding="utf-8") as xml_file:
            while True:
                # Read a chunk
                chunk = xml_file.read(cls.CHUNK_SIZE)
                if len(chunk) < cls.CHUNK_SIZE:
                    # End of file
                    # tell the parser we're done
                    p.Parse(chunk, 1)
                    # exit the loop
                    break
                # process the chunk
                p.Parse(chunk)

        # Don't forget to close our handle
        cls.cur_file.close()

    def execute(self, context):

        max_size = context.scene.amsvg_settings.svg_size * 2 ** 20  # convert mb to bytes
        directory = context.scene.amsvg_settings.svg_input

        # load all files from directory
        if os.path.isdir(directory):
            files = [os.path.join(directory, f).replace("\\", "/") for f in os.listdir(directory)
                     if f.endswith('.svg') and os.path.getsize(os.path.join(directory, f)) >= max_size]

        elif os.path.isfile(directory) and directory.endswith('.svg') and os.path.getsize(directory) >= max_size:
            files = [directory.replace("\\", "/")]
        else:
            return {"FINISHED"}

        if not os.path.isdir(context.scene.amsvg_settings.svg_output):
            try:
                os.makedirs(context.scene.amsvg_settings.svg_output, exist_ok=True)
            except (TypeError, FileNotFoundError):
                return {"FINISHED"}

        for filename in files:
            filename = filename.replace("\\", "/")
            out_dir = context.scene.amsvg_settings.svg_output.replace("\\", "/")
            if os.path.isabs(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            else:
                dir_list = [p for p in filename.split("/")[:-1] if p]
                out_list = [p for p in out_dir.split("/") if p]
                while out_list[0] == "..":
                    dir_list.pop(-1)
                    out_list.pop(0)
                out_dir = os.path.join(*dir_list, *out_list)
                out_dir = out_dir[:2] + "/" + out_dir[2:]
            self.main(filename, max_size, out_dir)

        return {"FINISHED"}


class SVGMerge(bpy.types.Operator):
    """splitter for xml. ported from someone code. literally I dunno how it works"""

    bl_idname = "mesh.am1dsvg_svg_merge"
    bl_label = "SVG output merge"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefix = ""
        all_data = ""

        for file in os.listdir(context.scene.amsvg_settings.svg_output):
            if os.path.splitext(file)[1].lower() != ".svg":
                continue
            file = os.path.join(context.scene.amsvg_settings.svg_output, file)
            with open(file, encoding="utf-8") as svg_file:
                data = svg_file.read()
            i = data.find("<svg")
            j = data.find(">", i)
            m = data.find("</svg>")
            if -1 in (i, j, m):
                continue
            if not prefix:
                prefix = data[:j + 1]
            all_data += data[j:m + 1]

        if prefix:
            with open(os.path.join(context.scene.amsvg_settings.svg_output, "MERGE.SVG"), "w", encoding="utf-8") as svg_file:
                svg_file.write(prefix)
                svg_file.write(all_data)
                svg_file.write("</svg>")

        return {"FINISHED"}


class SVGParseImages(bpy.types.Operator):
    bl_idname = "mesh.am1dsvg_svg_parse_images"
    bl_label = "SVG parse images"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def parse(context):
        """get list of found and lost files"""

        def checkTag(current_tag):
            if current_tag.tag == "image":

                svg_path = copy.copy(file_path)

                path = current_tag.attrs["xlink:href"].replace("\\", "/")
                if os.path.isabs(path):     # absolute path
                    if context.scene.amsvg_settings.svg_crop_abs:  # search local
                        svg_path.append(path.split("/")[-1])
                        path = "/".join(svg_path)

                    if os.path.isfile(path):
                        abs_found_files.append(path)
                    else:
                        abs_lost_files.append(path)

                else:
                    path = path.split("/")
                    while svg_path and path and path[0] == "..":
                        path.pop(0)
                        svg_path.pop(-1)
                    svg_path.extend(path)
                    path = "/".join(svg_path)

                    if os.path.exists(path):
                        found_files.append(path)
                    else:
                        lost_files.append(path)

            for child in current_tag.children:
                checkTag(child)

        found_files = []
        lost_files = []
        abs_found_files = []
        abs_lost_files = []
        file_path = os.path.dirname(context.scene.amsvg_settings.svg_input.replace("\\", "/")).split("/")
        checkTag(StructureBuilder(context.scene.amsvg_settings.svg_input).root[0])
        return found_files, lost_files, abs_found_files, abs_lost_files

    def execute(self, context):

        if not os.path.exists(context.scene.amsvg_settings.svg_input):
            return {"FINISHED"}

        found_files, lost_files, abs_found_files, abs_lost_files = self.parse(context)

        if "svg parse images" in bpy.data.texts:
            text_block = bpy.data.texts["svg parse images"]
        else:
            text_block = bpy.data.texts.new(name="svg parse images")
        text_block.clear()
        found_files = list(set(found_files))
        lost_files = list(set(lost_files))
        for i, line in enumerate(found_files):
            found_files[i] = "%.2i) %s" % (i + 1, line)
        for i, line in enumerate(lost_files):
            lost_files[i] = "%.2i) %s" % (i + 1, line)

        text_block.write("ABSOLUTE PATHS:\n")
        if abs_found_files:
            text_block.write("FOUND FILES:\n" + "\n".join(abs_found_files) + "\n\n")
        else:
            text_block.write("NO FOUND FILES\n\n")
        if abs_lost_files:
            text_block.write("LOST FILES:\n" + "\n".join(abs_lost_files) + "\n\n")
        else:
            text_block.write("NO LOST FILES\n\n")
        text_block.write("------\n")

        text_block.write("RELATIVE PATHS:\n")
        if found_files:
            text_block.write("FOUND FILES:\n" + "\n".join(found_files) + "\n\n")
        else:
            text_block.write("NO FOUND FILES\n\n")
        if lost_files:
            text_block.write("LOST FILES:\n" + "\n".join(lost_files))
        else:
            text_block.write("NO LOST FILES")
        return {"FINISHED"}


class SVGCopyImages(bpy.types.Operator):

    bl_idname = "mesh.am1dsvg_svg_copy_images"
    bl_label = "SVG copy images"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        if not os.path.exists(context.scene.amsvg_settings.svg_input):
            return {"FINISHED"}

        found_files = SVGParseImages.parse(context)[0]
        os.makedirs(context.scene.amsvg_settings.svg_output, exist_ok=True)
        for abs_file in found_files:
            with open(abs_file, "rb") as file:
                data = file.read()
            with open(os.path.join(context.scene.amsvg_settings.svg_output, os.path.split(abs_file)[1]), "wb") as file:
                file.write(data)

        return {"FINISHED"}


class SVGIconSlicer(bpy.types.Operator):

    bl_idname = "mesh.am1dsvg_svg_icon_slicer"
    bl_label = "SVG icon slicer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.scene.amsvg_settings.svg_label:
            SVGTransformChecker.execute(context.scene.amsvg_settings.svg_input, context.scene.amsvg_settings.svg_output)
        else:
            SVGIconSplitter.execute(context.scene.amsvg_settings.svg_input, context.scene.amsvg_settings.svg_output)
        return {"FINISHED"}


class SVGTransformChecker(object):

    @classmethod
    def execute(cls, input_name, output_name):
        name = os.path.split(os.path.splitext(input_name)[0])[1]
        if output_name:
            output_name = os.path.join(output_name, name + "_out.svg")
        else:
            output_name = os.path.splitext(input_name)[0] + "_out.svg"

        structure_builder = StructureBuilder(input_name)
        tree = structure_builder.root
        if len(tree) != 1:
            return {"CANCELED"}
        matrix_tag = TagUnit("g", {"id": "TranMatrix", "inkscape:label": "TranMatrix", "inkscape:groupmode": "layer"})
        tree[0].children.append(matrix_tag)
        cls.sort(tree[0], matrix_tag)
        open(output_name, "w", encoding="utf-8").write(tree[0].string())
        return {"FINISHED"}

    @classmethod
    def sort(cls, current_tag, matrix_tag):
        list_pass = []  # will be checked
        list_dont = []  # won't be checked and go to matrix
        for tag in current_tag.children:
            if "transform" in tag.attrs:
                list_dont.append(tag)
            else:
                list_pass.append(tag)

        current_tag.children = list_pass
        matrix_tag.children.extend(list_dont)
        for next_tag in current_tag.children:
            cls.sort(next_tag, matrix_tag)


class SVGIconSplitter(object):
    """it doesn't support transformation matrices"""

    @classmethod
    def execute(cls, input_name, output_name):
        if not output_name:
            output_name = os.path.splitext(input_name)[0] + "_out"
        os.makedirs(output_name, exist_ok=True)
        tag_dict = collections.defaultdict(list)
        image_dict = {}
        structure_builder = StructureBuilder(input_name)
        tree = structure_builder.root
        if len(tree) != 1:
            return {"CANCELED"}
        size = int(tree[0].attrs["width"])
        cls.createSortedList(size, tree[0], tag_dict, image_dict)
        tree[0].children = [tag for tag in tree[0].children if tag.tag != "g"]  # remove all groups tag
        icon_tag = TagUnit("g", {"id": "icon", "inkscape:label": "icon", "inkscape:groupmode": "layer"})
        tree[0].children.append(icon_tag)
        for key, name in image_dict.items():
            if key not in tag_dict:
                continue
            icon_tag.children = tag_dict[key]
            open(os.path.join(output_name, name), "w", encoding="utf-8").write(tree[0].string())

    @classmethod
    def createSortedList(cls, size, current_tag, tag_dict, image_dict):
        """create list of html objects excluding text"""
        for tag in current_tag.children:
            if tag.tag[:4] == "flow":  # remove text
                continue

            if tag.tag == "image":
                path = tag.attrs["sodipodi:absref"].replace("\\", "/").split("/")[-1]
                file_name = os.path.splitext(path)[0]
                div_x, mod_x = divmod(eval(tag.attrs["x"]) + 1, size)
                div_y, mod_y = divmod(eval(tag.attrs["y"]) + 1, size)
                image_dict[(div_x - 1.0, div_y)] = file_name + ".svg"
                continue

            elif tag.tag == "circle" or tag.tag == "ellipse":
                div_x, mod_x = divmod(eval(tag.attrs["cx"]), size)
                div_y, mod_y = divmod(eval(tag.attrs["cy"]), size)
                tag.attrs["cx"] = str(mod_x)
                tag.attrs["cy"] = str(mod_y)
                div_x = int(div_x)
                div_y = int(div_y)
                tag_dict[(div_x, div_y)].append(tag)

            elif tag.tag == "rect":
                div_x, mod_x = divmod(eval(tag.attrs["x"]), size)
                div_y, mod_y = divmod(eval(tag.attrs["y"]), size)
                div_x = int(div_x)
                div_y = int(div_y)
                tag.attrs["x"] = str(mod_x)
                tag.attrs["y"] = str(mod_y)
                tag_dict[(div_x, div_y)].append(tag)

            elif tag.tag == "path":
                absolute = True
                last_digit = "M"
                first_point = True
                div_x = div_y = 0
                result = ""

                for chunk in tag.attrs["d"].split():
                    if chunk in string.ascii_letters:  # letter
                        absolute = chunk.isupper()
                        last_digit = chunk
                        result += " %s" % chunk

                    elif "," not in chunk:  # single value chunk
                        z = eval(chunk)
                        if absolute:
                            div, mod = divmod(z, size)
                            if last_digit.lower() == "v":  # vertical
                                div_y = div
                            else:
                                div_x = div
                            result += " %s" % mod
                        else:
                            result += " %s" % z

                    else:  # double chunk
                        x, y = eval(chunk)
                        if absolute or first_point:
                            div_x, mod_x = divmod(x, size)
                            div_y, mod_y = divmod(y, size)
                            result += " %s,%s" % (mod_x, mod_y)
                        else:  # relatively add point
                            result += " %s,%s" % (x, y)
                        first_point = False
                div_x = int(div_x)
                div_y = int(div_y)
                tag.attrs["d"] = result
                tag_dict[(div_x, div_y)].append(tag)

            cls.createSortedList(size, tag, tag_dict, image_dict)


class Settings(bpy.types.PropertyGroup):

    svg_input = bpy.props.StringProperty(subtype="FILE_PATH")
    svg_output = bpy.props.StringProperty(subtype="FILE_PATH")
    svg_size = bpy.props.FloatProperty(name="svg_size", default=2, min=0.1, step=10, precision=1)
    svg_crop_abs = bpy.props.BoolProperty(name="", default=False)
    svg_label = bpy.props.BoolProperty(name="", default=False)


class Layout(bpy.types.Panel):

    bl_label = "1D SVG Tools"
    bl_idname = "Andrey_1DSVG_Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = '1D'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        """col - main column layout. do not rewrite
        col_in - main column inside every section
        col_in_n - sub layout"""
        layout = self.layout
        column = layout.column(align=True)
        column.prop(context.scene.amsvg_settings, "svg_input", text="input file or directory")
        column.prop(context.scene.amsvg_settings, "svg_output", text="output directory")
        column.prop(context.scene.amsvg_settings, "svg_size", text="max size (MB)")
        column.prop(context.scene.amsvg_settings, "svg_crop_abs", text="crop absolute names")
        column.prop(context.scene.amsvg_settings, "svg_label", text="slice transformed")
        column.operator("mesh.am1dsvg_svg_split", text="SVG input split")
        column.operator("mesh.am1dsvg_svg_merge", text="SVG output merge")
        column.operator("mesh.am1dsvg_svg_parse_images", text="SVG parse images")
        column.operator("mesh.am1dsvg_svg_copy_images", text="SVG copy images")
        column.operator("mesh.am1dsvg_svg_icon_slicer", text="SVG Icon Slicer")


def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.am_tool = bpy.props.PointerProperty(type=bpy.types.PropertyGroup)
    bpy.types.Scene.amsvg_settings = bpy.props.PointerProperty(type=Settings)


def unregister():
    bpy.utils.unregister_module(__name__)
    del bpy.types.Scene.my_tool


if __name__ == "__main__":
    register()
