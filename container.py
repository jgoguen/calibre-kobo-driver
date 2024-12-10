# vim:fileencoding=UTF-8:filetype=python:ts=4:sw=4:sta:et:sts=4:ai

"""Extend calibre's EPUBContainer to work for a KePub."""

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
import traceback
from collections import defaultdict
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Callable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
from urllib.parse import unquote

from calibre import guess_type
from calibre.ebooks.conversion.plugins.epub_input import ADOBE_OBFUSCATION
from calibre.ebooks.conversion.plugins.epub_input import IDPF_OBFUSCATION
from calibre.ebooks.conversion.utils import HeuristicProcessor
from calibre.ebooks.oeb.polish.container import EpubContainer
from calibre.utils.smartypants import smartyPants

# lxml isn't the best, but I don't have access to defusedxml
from lxml import etree  # skipcq: BAN-B410


load_translations()

HTML_MIMETYPES = frozenset(["application/xhtml+xml", "text/html"])
# Technically an unneeded cast, but pyright things guess_type returns str | None
CSS_MIMETYPE: str = str(guess_type("a.css")[0])
# Technically an unneeded cast, but pyright things guess_type returns str | None
JS_MIMETYPE: str = str(guess_type("a.js")[0])
EXCLUDE_FROM_ZIP = frozenset([".DS_Store", ".directory", "mimetype", "thumbs.db"])
NO_SPACE_BEFORE_CHARS = frozenset(list(string.punctuation) + ["\xbb"])
ENCRYPTION_NAMESPACES = {
    "enc": "http://www.w3.org/2001/04/xmlenc#",
    "deenc": "http://ns.adobe.com/digitaleditions/enc",
}
XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"
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
SPECIAL_TAGS = frozenset(["img"])
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
    r'(.*?(?:[\.\!\?\:][\'"\u201c\u201d\u2018\u2019\u2026]*(?=\s)|(?=\s*$)))',
    re.UNICODE | re.MULTILINE,
)


# TODO: Refactor InvalidEpub from here and device/driver.py to be a common class
class InvalidEpub(ValueError):
    """Designates an invalid ePub file."""


class ParseError(ValueError):
    """Designates an error parsing an ePub inner file."""

    def __init__(self, name: str, desc: str) -> None:
        """Initialize a ParseError."""
        self.name = name
        self.desc = desc
        ValueError.__init__(self, f"Failed to parse: {name} with error: {desc}")


class KEPubContainer(EpubContainer):
    """Extends an EpubContainer to work for a KePub."""

    def __init__(
        self, epub_path: str, log, *args, do_cleanup: bool = False, **kwargs
    ) -> None:
        self.paragraph_counter = defaultdict(lambda: 1)  # type: Dict[str, int]
        super(KEPubContainer, self).__init__(epub_path, log, *args, **kwargs)
        self.my_thread = threading.current_thread()
        self.log = log
        self.log.debug(f"Creating KePub Container for ePub at {epub_path}")

        self.__run_async_over_content(self.forced_cleanup)
        if do_cleanup:
            self.__run_async_over_content(self.clean_markup)

    def html_names(self) -> Iterator[str]:
        """Get all HTML files in the OPF file.

        A generator function that yields only HTML file names from the ePub.
        """
        for node in self.opf_xpath("//opf:manifest/opf:item[@href and @media-type]"):
            if node.get("media-type") in HTML_MIMETYPES:
                href = os.path.join(os.path.dirname(self.opf_name), node.get("href"))
                href = os.path.normpath(href).replace(os.sep, "/")
                href = unquote(href)
                yield href

    @property
    def is_drm_encumbered(self) -> bool:
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
                self.log.error(f"Could not parse encryption.xml: {e}")
                raise

        return is_encumbered

    def copy_file_to_container(
        self, path: str, name: Optional[str] = None, mt: Optional[str] = None
    ) -> str:
        """Copy a file into this Container instance.

        @param path: The path to the file to copy into this Container.
        @param name: The name to give to the copied file, relative to the
        Container root. Set to None to use the basename of path.
        @param mt: The MIME type of the file to set in the manifest. Set to
        None to auto-detect.

        @return: The name of the file relative to the Container root
        """
        if not os.path.isfile(path):
            raise ValueError(_("A source path must be given"))
        if name is None:
            basename: str = os.path.basename(path)
        else:
            basename: str = name
        item = self.generate_item(basename, media_type=mt)
        # Unnecessary casse but pyright things href_to_name could return many things
        basename = str(self.href_to_name(item.get("href"), self.opf_name))

        self.log.info(f"Copying file '{path}' to '{self.root}' as '{basename}'")

        try:
            # Throws an error we can ignore if the directory already exists
            os.makedirs(os.path.dirname(os.path.join(self.root, basename)))
        except Exception:
            pass

        shutil.copy(path, os.path.join(self.root, basename))

        return basename

    def add_content_file_reference(self, name: str) -> None:
        """Add a reference to the named file to all content files.

        Adds a reference to the named file (see self.name_path_map) to all
        content files (self.html_names()). Currently only CSS files with a
        MIME type of text/css and JavaScript files with a MIME type of
        application/x-javascript are supported.
        """
        if name not in self.name_path_map or name not in self.mime_map:
            raise ValueError(_(f"A valid file name must be given (got {name})"))

        self.__run_async_over_content(self.__add_content_file_reference_impl, (name,))

    def __add_content_file_reference_impl(self, infile: str, name: str) -> None:
        self.log.debug(f"Adding reference to {name} to file {infile}")
        root = self.parsed(infile)
        if root is None:
            raise Exception(_(f"Could not retrieve content file {infile}"))
        head = root.xpath("./xhtml:head", namespaces={"xhtml": XHTML_NAMESPACE})
        if head is None:
            head = root.makeelement(f"{{{XHTML_NAMESPACE}}}head")
            root.insert(0, head)
        else:
            head = head[0]
        if head is None:
            raise Exception(
                _(
                    "A <head> section was found but was undefined in content "
                    + f"file {infile}"
                )
            )

        if self.mime_map[name] == CSS_MIMETYPE:
            elem = head.makeelement(
                f"{{{XHTML_NAMESPACE}}}link",
                rel="stylesheet",
                href=os.path.relpath(name, os.path.dirname(infile)).replace(
                    os.sep, "/"
                ),
            )
        elif self.mime_map[name] == JS_MIMETYPE:
            elem = head.makeelement(
                f"{{{XHTML_NAMESPACE}}}script",
                type="text/javascript",
                src=os.path.relpath(name, os.path.dirname(infile)).replace(os.sep, "/"),
            )
        else:
            elem = None

        if elem is not None:
            head.append(elem)
            if self.mime_map[name] == CSS_MIMETYPE:
                self.fix_tail(elem)
            self.commit_item(infile, keep_parsed=True)

    @staticmethod
    def fix_tail(item: etree._Element) -> None:
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

    def forced_cleanup(self, name: str) -> None:
        """Perform cleanup considered essential for standards compliance."""
        self.log.debug(f"Forcing cleanup for file {name}")
        html = self.raw_data(name, decode=True, normalize_to_nfc=True)
        if html is None:
            self.log.warning(f"No HTML content in {name}")
            return

        encoding_match = ENCODING_RE.search(str(html[:75]))
        if encoding_match and encoding_match.group(1).upper() != "UTF-8":
            html = re.sub(encoding_match.group(1), "UTF-8", html, 1, re.MULTILINE)

        # Force meta and link tags to be self-closing
        html = SELF_CLOSING_RE.sub(r"<\1 \2 />", html)

        # Force open script tags
        html = FORCE_OPEN_TAG_RE.sub(r"<\1 \2></\1>", html)

        # Remove Unicode replacement characters
        html = html.replace("\ufffd", "")

        self.replace(name, self.parse_xhtml(html))
        self.commit_item(name, keep_parsed=True)

    def clean_markup(self, name: str) -> None:
        """Clean HTML markup.

        This cleans the HTML markup for things which are not strictly
        non-compliant but can cause problems.
        """
        self.log.debug(f"Cleaning markup for file {name}")
        html = self.raw_data(name, decode=True, normalize_to_nfc=True)
        if html is None:
            self.log.warning(f"No HTML content in {name}")

        # Get rid of Microsoft cruft
        html = MS_CRUFT_RE_1.sub(" ", html)
        html = MS_CRUFT_RE_2.sub("", html)

        # Remove empty headings
        html = EMPTY_HEADINGS_RE.sub("", html)

        self.replace(name, self.parse_xhtml(html))
        self.commit_item(name, keep_parsed=True)

    def smarten_punctuation(self) -> None:
        self.__run_async_over_content(self.__smarten_punctuation_impl)

    def __smarten_punctuation_impl(self, name: str) -> None:
        """Convert standard punctuation to "smart" punctuation."""
        preprocessor = HeuristicProcessor(log=self.log)

        self.log.debug(f"Smartening punctuation for file {name}")
        html = self.raw_data(name, decode=True, normalize_to_nfc=True)
        if html is None:
            self.log.warning(f"No HTML content in file {name}")

        # Fix non-breaking space indents
        html = preprocessor.fix_nbsp_indents(html)

        # Smarten punctuation
        # q : quotes
        # B : backtick quotes (``double'' and `single')
        # d : dashes
        # e : ellipses
        html = smartyPants(html, attr="qBde")
        self.replace(name, self.parse_xhtml(html))

        self.commit_item(name, keep_parsed=True)

    def __run_async(self, func: Callable, args: List[Tuple[str, ...]]) -> None:
        # Verify that we aren't making subthreads of a subthread
        if threading.current_thread() != self.my_thread:
            self.log.debug("__run_async called by a subthread")
            traceback.print_stack()
            raise Exception("__run_async called by a subthread")

        futures: List[Future] = []
        with ThreadPoolExecutor() as pool:
            try:
                for arg in args:
                    self.log.debug(
                        f"Starting thread: func={func.__name__}, name={arg[0]}"
                    )
                    futures.append(pool.submit(func, *arg))

                for future in futures:
                    name = future.result(timeout=60)
                    self.log.debug(f"thread processing {name} finished")
            except Exception as e:
                self.log.error(f"Unhandled exception in thread processing. {str(e)}")
                raise e

        # Be sure dirtied trees are committed. These should be trees dirtied in
        # our superclass because trees dirtied here have already been committed
        for n in list(self.dirtied):
            self.log.debug(f"Committing dirtied: {n}")
            self.commit_item(n)

    def __run_async_over_content(
        self, func: Callable, args: Optional[Tuple[str, ...]] = None
    ) -> None:
        args = args or ()
        names = [(name,) + args for name in self.html_names()]
        self.__run_async(func, names)

    def convert(self) -> None:
        """The entry point for converting to KePub"""
        self.__run_async_over_content(self.add_kobo_spans)
        self.__run_async_over_content(self.add_kobo_divs)

    def add_kobo_divs(self, name) -> None:
        """Add KePub divs to the HTML file."""
        self.log.debug(f"Adding Kobo divs to {name}")
        root = self.parsed(name)
        kobo_div_count = int(
            root.xpath(
                'count(//xhtml:div[@id="book-inner"])',
                namespaces={"xhtml": XHTML_NAMESPACE},
            )
        )
        if kobo_div_count > 0:
            self.log.warning(
                _(f"Skipping file {name}")
                + ", "
                + ngettext(
                    "Kobo <div> tag present", "Kobo <div> tags present", kobo_div_count
                )
            )
            return name

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
            self.log.warning(
                _(f"Skipping file {name}")
                + " ("
                + ngettext(
                    f"{div_count} <div> tag", f"{div_count} <div> tags", div_count
                )
                + ", "
                + ngettext(f"{p_count} <p> tag", f"{p_count} <p> tags", p_count)
                + ")"
            )
            return name

        self.__add_kobo_divs_to_body(root)

        self.replace(name, root)
        self.commit_item(name, keep_parsed=True)
        return name

    @staticmethod
    def __add_kobo_divs_to_body(root: etree._Element) -> None:
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
        for key, value in body_attrs.items():
            body.set(key, value)

        # Wrap the full body in a div
        inner_div = etree.Element(
            f"{{{XHTML_NAMESPACE}}}div", attrib={"id": "book-inner"}
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
            f"{{{XHTML_NAMESPACE}}}div", attrib={"id": "book-columns"}
        )
        outer_div.append(inner_div)

        # And re-chuck the full div pyramid in the now empty body
        body.append(outer_div)

    def add_kobo_spans(self, name: str) -> None:
        """Add KePub spans (used for in-book location) the HTML file."""
        self.log.debug(f"Adding Kobo spans to {name}")
        root = self.parsed(name)
        kobo_span_count = int(
            root.xpath(
                'count(.//xhtml:span[@class="koboSpan" '
                + 'or starts-with(@id, "kobo.")])',
                namespaces={"xhtml": XHTML_NAMESPACE},
            )
        )
        if kobo_span_count > 0:
            self.log.warning(
                _(f"Skipping file {name}")
                + ", "
                + ngettext(
                    "Kobo <span> tag present",
                    "Kobo <span> tags present",
                    kobo_span_count,
                )
            )
            return

        body = root.xpath("./xhtml:body", namespaces={"xhtml": XHTML_NAMESPACE})[0]
        self._add_kobo_spans_to_node(body, name)

        self.replace(name, root)
        self.commit_item(name, keep_parsed=True)

    def _add_kobo_spans_to_node(
        self, node: etree._Element, name: str
    ) -> etree._Element:
        # process node only if it is not a comment or a processing instruction
        if node is None or isinstance(
            node, (etree._Comment, etree._ProcessingInstruction)
        ):
            if node is not None:
                node.tail = None
            self.log.debug(f"[{name}] Skipping comment/ProcessingInstruction node")
            return node

        # Special case some tags
        special_tag_match = re.search(r"^(?:\{[^\}]+\})?(\w+)$", node.tag)
        if special_tag_match:
            # Skipped tags are just flat out skipped
            if special_tag_match.group(1) in SKIPPED_TAGS:
                self.log.debug(f"[{name}] Skipping '{special_tag_match.group(1)}' tag")
                return node

            # Special tags get wrapped in a span and their children are ignored
            if special_tag_match.group(1) in SPECIAL_TAGS:
                self.log.debug(
                    f"[{name}] Wrapping '{special_tag_match.group(1)}' tag and "
                    + "ignoring children"
                )
                span = etree.Element(
                    f"{{{XHTML_NAMESPACE}}}span",
                    attrib={
                        "id": f"kobo.{self.paragraph_counter[name]}.1",
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
        for key, value in node_attrs.items():
            node.set(key, value)

        # the node text is converted to spans
        if node_text is not None:
            if self._append_kobo_spans_from_text(node, node_text, name):
                self.paragraph_counter[name] += 1

        # re-add the node children
        for child in node_children:
            # save child tail for later
            child_tail = child.tail
            child.tail = None
            node.append(self._add_kobo_spans_to_node(child, name))
            # the child tail is converted to spans
            if child_tail is not None:
                if self._append_kobo_spans_from_text(node, child_tail, name):
                    self.paragraph_counter[name] += 1

        return node

    def _append_kobo_spans_from_text(
        self, node: etree._Element, text: str, name: str
    ) -> etree._Element:
        if not text or text == "":
            self.log.error(f"[{name}] No text passed, can't add spans")
            return False

        # split text in sentences
        groups = TEXT_SPLIT_RE.split(text)

        # append first group (whitespace) as text
        if len(node) == 0:
            node.text = groups[0]
        else:
            node[-1].tail = groups[0]

        # append each sentence in its own span
        segment_counter = 1
        for g, ws in zip(groups[1::2], groups[2::2]):
            if g.strip() == "":
                continue
            span = etree.Element(
                f"{{{XHTML_NAMESPACE}}}span",
                attrib={
                    "class": "koboSpan",
                    "id": f"kobo.{self.paragraph_counter[name]}.{segment_counter}",
                },
            )
            span.text = g
            span.tail = ws
            node.append(span)
            segment_counter += 1

        return len(groups) > 1  # Return true if any spans were added.
