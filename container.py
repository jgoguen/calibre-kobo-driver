# vim:fileencoding=UTF-8:filetype=python:ts=4:sw=4:sta:et:sts=4:ai

"""Extend calibre's EPUBContainer to work for a KePub."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__license__ = "GPL v3"
__copyright__ = (
    "2010, Kovid Goyal <kovid@kovidgoyal.net>; "
    + "2013, Joel Goguen <jgoguen@jgoguen.ca>"
)
__docformat__ = "restructuredtext en"

# Be careful editing this! This file has to work in multiple plugins at once,
# so don't import anything from calibre_plugins.

import os
import re
import shutil
import string
import threading
from collections import defaultdict
from copy import deepcopy

from calibre import guess_type
from calibre.ebooks.conversion.plugins.epub_input import ADOBE_OBFUSCATION
from calibre.ebooks.conversion.plugins.epub_input import IDPF_OBFUSCATION
from calibre.ebooks.conversion.utils import HeuristicProcessor
from calibre.ebooks.oeb.polish.container import EpubContainer
from calibre.utils.smartypants import smartyPants
from polyglot.builtins import is_py3

from lxml import etree

if is_py3:
    from typing import Any
    from typing import Callable
    from typing import Dict
    from typing import List
    from typing import Optional
    from typing import Set
    from typing import Tuple

# Support load_translations() without forcing calibre 1.9+
try:
    load_translations()
except NameError:
    pass

HTML_MIMETYPES = frozenset(["application/xhtml+xml", "text/html"])  # type: Set[str]
CSS_MIMETYPE = guess_type("a.css")[0]  # type: str
JS_MIMETYPE = guess_type("a.js")[0]  # type: str
EXCLUDE_FROM_ZIP = frozenset(
    [".DS_Store", ".directory", "mimetype", "thumbs.db"]
)  # type: Set[str]
NO_SPACE_BEFORE_CHARS = frozenset(
    [c for c in string.punctuation] + ["\xbb"]
)  # noqa: E501, type: Set[str]
ENCRYPTION_NAMESPACES = {
    "enc": "http://www.w3.org/2001/04/xmlenc#",
    "deenc": "http://ns.adobe.com/digitaleditions/enc",
}  # type: Dict[str, str]
XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"  # type: str
SKIPPED_TAGS = frozenset(
    [
        "button",
        "circle",
        "defs",
        "figcaption",
        "figure",
        "g",
        "input",
        "math",
        "path",
        "polygon",
        "pre",
        "rect",
        "script",
        "style",
        "svg",
        "use",
        "video",
    ]
)
SPECIAL_TAGS = frozenset(["img"])  # type: Set[str]
ENCODING_RE = re.compile(r'^\<\?.+encoding="([^"]+)"', re.MULTILINE)
SELF_CLOSING_RE = re.compile(
    r"<(meta|link) ([^>]+)>.*?</\1>", re.UNICODE | re.MULTILINE
)
FORCE_OPEN_TAG_RE = re.compile(r"<(script|p) ([^<]+) ?/>", re.UNICODE | re.MULTILINE)
EMPTY_HEADINGS_RE = re.compile(r"(?i)<(h\d+)[^>]*?>\s*</\1>", re.UNICODE | re.MULTILINE)
ELLIPSIS_RE = re.compile(r"(?u)(?<=\w)\s?(\.\s+?){2}\.", re.UNICODE | re.MULTILINE)
MS_CRUFT_RE_1 = re.compile(r"<o:p>\s*</o:p>", re.UNICODE | re.MULTILINE)
MS_CRUFT_RE_2 = re.compile(r"(?i)</?st1:\w+>", re.UNICODE | re.MULTILINE)
TEXT_SPLIT_RE = re.compile(
    r'(\s*.*?[\.\!\?\:][\'"\u201c\u201d\u2018\u2019\u2026]?\s*)',
    re.UNICODE | re.MULTILINE,
)


# TODO: Refactor InvalidEpub from here and device/driver.py to be a common class
class InvalidEpub(ValueError):
    """Designates an invalid ePub file."""

    pass


class ParseError(ValueError):
    """Designates an error parsing an ePub inner file."""

    def __init__(self, name, desc):  # type: (str, str) -> None
        """Initialize a ParseError."""
        self.name = name
        self.desc = desc
        ValueError.__init__(
            self, "Failed to parse: {0} with error: {1}".format(name, desc)
        )


class KEPubContainer(EpubContainer):
    """Extends an EpubContainer to work for a KePub."""

    def __init__(
        self, epub_path, log, do_cleanup=False, *args, **kwargs
    ):  # type: (...) -> None
        self.paragraph_counter = defaultdict(lambda: 1)  # type: Dict[str, int]
        super(KEPubContainer, self).__init__(epub_path, log, *args, **kwargs)
        self.log = log
        self.log.debug("Creating KePub Container for ePub at {0}".format(epub_path))

        self.__run_async_over_content(self.forced_cleanup)
        if do_cleanup:
            self.__run_async_over_content(self.clean_markup)

    def html_names(self):
        """Get all HTML files in the OPF file.

        A generator function that yields only HTML file names from the ePub.
        """
        for node in self.opf_xpath("//opf:manifest/opf:item[@href and @media-type]"):
            if node.get("media-type") in HTML_MIMETYPES:
                href = os.path.join(os.path.dirname(self.opf_name), node.get("href"))
                href = os.path.normpath(href).replace(os.sep, "/")
                yield href

    @property
    def is_drm_encumbered(self):
        """Determine if the ePub container is DRM-encumbered.

        This method looks for the 'encryption.xml' file which denotes an
        ePub encumbered by Digital Restrictions Management. DRM-encumbered
        files cannot be edited.
        """
        is_encumbered = False
        if "META-INF/encryption.xml" in self.name_path_map:
            try:
                xml = self.parsed("META-INF/encryption.xml")
                if xml is None:
                    # If encryption.xml can't be parsed, assume its presence
                    # means an encumbered file. This may be wrong, but so far
                    # it's proven accurate.
                    return True
                for elem in xml.xpath(
                    "./enc:EncryptedData/enc:EncryptionMethod[@Algorithm]",
                    namespaces=ENCRYPTION_NAMESPACES,
                ):
                    alg = elem.get("Algorithm")

                    # Anything not an acceptable encryption algorithm is a
                    # sign of an encumbered file.
                    if alg not in {ADOBE_OBFUSCATION, IDPF_OBFUSCATION}:
                        is_encumbered = True
                        break
            except Exception as e:
                self.log.error("Could not parse encryption.xml: " + e.message)
                raise

        return is_encumbered

    def flush_cache(self):  # type: (...) -> None
        self.__run_async(self.__flush_cache_impl, [(name,) for name in self.dirtied])

    def __flush_cache_impl(self, name):  # type: (str) -> None
        """Flush the cache, writing all cached values to disk."""
        self.commit_item(name, keep_parsed=True)

    def copy_file_to_container(self, path, name=None, mt=None):
        """Copy a file into this Container instance.

        @param path: The path to the file to copy into this Container.
        @param name: The name to give to the copied file, relative to the
        Container root. Set to None to use the basename of path.
        @param mt: The MIME type of the file to set in the manifest. Set to
        None to auto-detect.

        @return: The name of the file relative to the Container root
        """
        if path is None or not os.path.isfile(path):
            raise ValueError(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "A source path must be given"
                )
            )
        if name is None:
            name = os.path.basename(path)
        item = self.generate_item(name, media_type=mt)
        name = self.href_to_name(item.get("href"), self.opf_name)

        self.log.info(
            "Copying file '{0}' to '{1}' as '{2}'".format(path, self.root, name)
        )

        try:
            # Throws an error we can ignore if the directory already exists
            os.makedirs(os.path.dirname(os.path.join(self.root, name)))
        except Exception:
            pass

        shutil.copy(path, os.path.join(self.root, name))

        return name

    def add_content_file_reference(self, name):
        """Add a reference to the named file to all content files.

        Adds a reference to the named file (see self.name_path_map) to all
        content files (self.html_names()). Currently only CSS files with a
        MIME type of text/css and JavaScript files with a MIME type of
        application/x-javascript are supported.
        """
        if name not in self.name_path_map or name not in self.mime_map:
            raise ValueError(
                _(  # noqa: F821 - _ is defined in calibre
                    "A valid file name must be given (got {filename})"
                ).format(filename=name)
            )

        self.__run_async_over_content(self.__add_content_file_reference_impl, (name,))

    def __add_content_file_reference_impl(self, infile, name):
        self.log.debug("Adding reference to {0} to file {1}".format(name, infile))
        root = self.parsed(infile)
        if root is None:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "Could not retrieve content file {0}"
                ).format(infile)
            )
        head = root.xpath("./xhtml:head", namespaces={"xhtml": XHTML_NAMESPACE})
        if head is None:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "Could not find a <head> element in {0}"
                ).format(infile)
            )
        head = head[0]
        if head is None:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "A <head> section was found but was undefined in content file {0}"
                ).format(infile)
            )

        if self.mime_map[name] == CSS_MIMETYPE:
            elem = head.makeelement(
                "{%s}link" % XHTML_NAMESPACE,
                rel="stylesheet",
                href=os.path.relpath(name, os.path.dirname(infile)).replace(
                    os.sep, "/"
                ),
            )
        elif self.mime_map[name] == JS_MIMETYPE:
            elem = head.makeelement(
                "{%s}script" % XHTML_NAMESPACE,
                type="text/javascript",
                src=os.path.relpath(name, os.path.dirname(infile)).replace(os.sep, "/"),
            )
        else:
            elem = None

        if elem is not None:
            head.append(elem)
            if self.mime_map[name] == CSS_MIMETYPE:
                self.fix_tail(elem)
            self.dirty(infile)

    def fix_tail(self, item):
        """Fix self-closing elements.

        Designed only to work with self closing elements after item has just
        been inserted/appended
        """
        parent = item.getparent()
        idx = parent.index(item)
        if idx == 0:
            # item is the first child element, move the text to after item
            item.tail = parent.text
        else:
            # There are other elements, possibly also text, before this child
            # element.
            # Move this element's tail to the previous element (note: .text is
            # only the text after the last child element, text before that and
            # surrounding elements are attributes of the elements)
            item.tail = parent[idx - 1].tail
            # If this is the last child element, it gets the remaining text.
            if idx == len(parent) - 1:
                parent[idx - 1].tail = parent.text

    def forced_cleanup(self, name):  # type: (str) -> None
        """Perform cleanup considered essential for standards compliance."""
        self.log.debug("Forcing cleanup for file {0}".format(name))
        html = self.raw_data(name, decode=True, normalize_to_nfc=True)
        if html is None:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "No HTML content in {0}"
                ).format(name)
            )

        encoding_match = ENCODING_RE.search(str(html[:75]))
        encoding = "UTF-8"
        if encoding_match and encoding_match.group(1):
            encoding = encoding_match.group(1).upper()
        if hasattr(html, "decode"):
            html = html.decode(encoding)
        if encoding_match and encoding_match.group(1).upper() != "UTF-8":
            html = re.sub(encoding_match.group(1), "UTF-8", html, 1, re.MULTILINE)

        # Force meta and link tags to be self-closing
        html = SELF_CLOSING_RE.sub(r"<\1 \2 />", html)

        # Force open script tags
        html = FORCE_OPEN_TAG_RE.sub(r"<\1 \2></\1>", html)

        # Remove Unicode replacement characters
        html = html.replace("\uFFFD", "")

        self.replace(name, self.parse_xhtml(html))
        self.flush_cache()

    def clean_markup(self, name):  # type: (str) -> None
        """Clean HTML markup.

        This cleans the HTML markup for things which are not strictly
        non-compliant but can cause problems.
        """
        self.log.debug("Cleaning markup for file {0}".format(name))
        html = self.raw_data(name, decode=True, normalize_to_nfc=True)
        if html is None:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "No HTML content in {0}"
                ).format(name)
            )

        # Get rid of Microsoft cruft
        html = MS_CRUFT_RE_1.sub(" ", html)
        html = MS_CRUFT_RE_2.sub("", html)

        # Remove empty headings
        html = EMPTY_HEADINGS_RE.sub("", html)

        self.replace(name, self.parse_xhtml(html))
        self.flush_cache()

    def smarten_punctuation(self):  # type: (...) -> None
        self.__run_async_over_content(self.__smarten_punctuation_impl)

    def __smarten_punctuation_impl(self, name):  # type: (str) -> None
        """Convert standard punctuation to "smart" punctuation."""
        preprocessor = HeuristicProcessor(log=self.log)

        self.log.debug("Smartening punctuation for file {0}".format(name))
        html = self.raw_data(name, decode=True, normalize_to_nfc=True)
        if html is None:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "No HTML content in file {0}"
                ).format(name)
            )

        # Fix non-breaking space indents
        html = preprocessor.fix_nbsp_indents(html)

        # Smarten punctuation
        html = smartyPants(html)

        # Ellipsis to HTML entity
        html = ELLIPSIS_RE.sub("&hellip;", html)

        # Double-dash and unicode char code to em-dash
        html = html.replace("---", " &#x2013; ")
        html = html.replace("\x97", " &#x2013; ")
        html = html.replace("\u2013", " &#x2013; ")
        html = html.replace("--", " &#x2014; ")
        html = html.replace("\u2014", " &#x2014; ")

        # Fix comment nodes that got mangled
        html = html.replace("<! &#x2014; ", "<!-- ")
        html = html.replace(" &#x2014; >", " -->")

        self.replace(name, self.parse_xhtml(html))
        self.flush_cache()

    def __run_async(self, func, args):  # type: (Callable, List[Tuple[Any]]) -> None
        threads = [threading.Thread(target=func, args=arg) for arg in args]
        [th.start() for th in threads]
        [th.join() for th in threads]

    def __run_async_over_content(
        self, func, args=None
    ):  # type: (Callable, Optional[List[Any]]) -> None
        args = args or ()
        names = [(name,) + args for name in self.html_names()]
        self.__run_async(func, names)

    def convert(self):  # type: (...) -> bool
        """The entry point for converting to KePub"""
        self.__run_async_over_content(self.add_kobo_spans)
        self.__run_async_over_content(self.add_kobo_divs)

    def add_kobo_divs(self, name):  # type: (str) -> bool
        """Add KePub divs to the HTML file."""
        self.log.debug("Adding Kobo divs to {0}".format(name))
        root = self.parsed(name)
        kobo_div_count = root.xpath(
            'count(//xhtml:div[@id="book-inner"])',
            namespaces={"xhtml": XHTML_NAMESPACE},
        )
        if kobo_div_count > 0:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "Skipping file {fname}"
                ).format(fname=name)
                + ", "
                + ngettext(  # noqa: F821 - ngettext is defined in globals by calibre
                    "Kobo <div> tag present", "Kobo <div> tags present", kobo_div_count
                )
            )

        # NOTE: Hackish heuristic: Forgo this if we have more div's than
        # p's, which would potentially indicate a book using div's instead
        # of p's...
        # Apparently, doing this on those books appears to blow up in a
        # spectacular way, so, err, don't ;).
        # FIXME: Try to figure out what's really happening instead of
        # sidestepping the issue?
        div_count = int(
            root.xpath("count(//xhtml:div)", namespaces={"xhtml": XHTML_NAMESPACE})
        )
        p_count = int(
            root.xpath("count(//xhtml:p)", namespaces={"xhtml": XHTML_NAMESPACE})
        )
        if div_count > p_count:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "Skipping file {fname}"
                ).format(fname=name)
                + " ("
                + ngettext(  # noqa: F821 - ngettext is defined in globals by calibre
                    "{div_count:d} <div> tag", "{div_count:d} <div> tags", div_count
                ).format(div_count=int(div_count))
                + ", "
                + ngettext(  # noqa: F821 - ngettext is defined in globals by calibre
                    "{p_count:d} <p> tag", "{p_count:d} <p> tags", p_count
                ).format(p_count=int(p_count))
                + ")"
            )

        self.__add_kobo_divs_to_body(root)

        self.replace(name, root)
        self.flush_cache()

    def __add_kobo_divs_to_body(self, root):
        body = root.xpath("./xhtml:body", namespaces={"xhtml": XHTML_NAMESPACE})[0]

        # save node content for later
        body_text = body.text
        body_children = deepcopy(body.getchildren())
        body_attrs = {}
        for key in list(body.keys()):
            body_attrs[key] = body.get(key)

        # reset current node, to start from scratch
        body.clear()

        # restore node attributes
        for key in body_attrs:
            body.set(key, body_attrs[key])

        # Wrap the full body in a div
        inner_div = etree.Element(
            "{%s}div" % (XHTML_NAMESPACE,), attrib={"id": "book-inner"}
        )

        # Handle the node text
        if body_text is not None:
            inner_div.text = body_text

        # re-add the node children, but as children of the div
        for child in body_children:
            # save child tail for later
            child_tail = child.tail
            child.tail = None
            inner_div.append(child)
            # Handle the child tail
            if child_tail is not None:
                inner_div[-1].tail = child_tail

        # Finally, wrap that div in another one...
        outer_div = etree.Element(
            "{%s}div" % (XHTML_NAMESPACE,), attrib={"id": "book-columns"}
        )
        outer_div.append(inner_div)

        # And re-chuck the full div pyramid in the now empty body
        body.append(outer_div)

    def add_kobo_spans(self, name):  # type: (str) -> None
        """Add KePub spans (used for in-book location) the HTML file."""
        self.log.debug("Adding Kobo spans to {0}".format(name))
        root = self.parsed(name)
        kobo_span_count = root.xpath(
            'count(.//xhtml:span[@class="koboSpan" ' + 'or starts-with(@id, "kobo.")])',
            namespaces={"xhtml": XHTML_NAMESPACE},
        )
        if kobo_span_count > 0:
            raise Exception(
                _(  # noqa: F821 - _ is defined in globals by calibre
                    "Skipping file {fname}"
                ).format(fname=name)
                + ", "
                + ngettext(  # noqa: F821 - ngettext is defined by calibre
                    "Kobo <span> tag present",
                    "Kobo <span> tags present",
                    kobo_span_count,
                )
            )

        body = root.xpath("./xhtml:body", namespaces={"xhtml": XHTML_NAMESPACE})[0]
        self._add_kobo_spans_to_node(body, name)

        self.replace(name, root)
        self.flush_cache()

    def _add_kobo_spans_to_node(self, node, name):
        # process node only if it is not a comment or a processing instruction
        if (
            node is None
            or isinstance(node, etree._Comment)
            or isinstance(node, etree._ProcessingInstruction)
        ):
            if node is not None:
                node.tail = None
            self.log.debug(
                "[{0}] Skipping comment/ProcessingInstruction node".format(name)
            )
            return node

        # Special case some tags
        special_tag_match = re.search(r"^(?:\{[^\}]+\})?(\w+)$", node.tag)
        if special_tag_match:
            # Skipped tags are just flat out skipped
            if special_tag_match.group(1) in SKIPPED_TAGS:
                self.log.debug(
                    "[{1}] Skipping '{0}' tag".format(special_tag_match.group(1), name)
                )
                return node

            # Special tags get wrapped in a span and their children are ignored
            if special_tag_match.group(1) in SPECIAL_TAGS:
                self.log.debug(
                    "[{1}] Wrapping '{0}' tag and ignoring children".format(
                        special_tag_match.group(1), name
                    )
                )
                span = etree.Element(
                    "{%s}span" % (XHTML_NAMESPACE,),
                    attrib={
                        "id": "kobo.{0}.1".format(self.paragraph_counter[name]),
                        "class": "koboSpan",
                    },
                )
                span.append(node)
                return span

        # save node content for later
        node_text = node.text
        node_children = deepcopy(node.getchildren())
        node_attrs = {}
        for key in list(node.keys()):
            node_attrs[key] = node.get(key)

        # reset current node, to start from scratch
        node.clear()

        # restore node attributes
        for key in node_attrs:
            node.set(key, node_attrs[key])

        # the node text is converted to spans
        if node_text is not None:
            if not self._append_kobo_spans_from_text(node, node_text, name):
                # didn't add spans, restore text
                node.text = node_text
            else:
                self.paragraph_counter[name] += 1

        # re-add the node children
        for child in node_children:
            # save child tail for later
            child_tail = child.tail
            child.tail = None
            node.append(self._add_kobo_spans_to_node(child, name))
            # the child tail is converted to spans
            if child_tail is not None:
                if not self._append_kobo_spans_from_text(node, child_tail, name):
                    # didn't add spans, restore tail on last child
                    node[-1].tail = child_tail
                else:
                    self.paragraph_counter[name] += 1

        return node

    def _append_kobo_spans_from_text(self, node, text, name):
        if not text:
            self.log.error("[{0}] No text passed, can't add spans".format(name))
            return False

        # if text is only whitespace, don't add spans
        if text.strip() == "":
            self.log.warning(
                "[{0}] Found only whitespace, not adding spans".format(name)
            )
            return False

        # split text in sentences
        groups = TEXT_SPLIT_RE.split(text)
        # remove empty strings resulting from split()
        groups = [g for g in groups if g != ""]
        for idx in range(len(groups)):
            if hasattr(groups[idx], "decode"):
                groups[idx] = groups[idx].decode("UTF-8")

        # TODO: To match Kobo KePubs, the trailing whitespace needs to
        # be prepended to the next group. Probably equivalent to make
        # sure the space stays in the span at the end.
        # add each sentence in its own span
        segment_counter = 1
        for g in groups:
            span = etree.Element(
                "{%s}span" % (XHTML_NAMESPACE,),
                attrib={
                    "class": "koboSpan",
                    "id": "kobo.{0}.{1}".format(
                        self.paragraph_counter[name], segment_counter
                    ),
                },
            )
            span.text = g
            node.append(span)
            segment_counter += 1

        return True
