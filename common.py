# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

"""Common functions and variables needed by more than one plugin."""

__license__ = "GPL v3"
__copyright__ = "2013, Joel Goguen <jgoguen@jgoguen.ca>"
__docformat__ = "markdown en"

# Be careful editing this! This file has to work in multiple packages at once,
# so don't import anything from calibre_plugins

import os
import re
import sys
import time
import traceback
from functools import partial

from calibre import prints
from calibre.constants import config_dir
from calibre.constants import preferred_encoding
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.base import NULL_VALUES
from calibre.ebooks.oeb.polish.container import EpubContainer
from calibre.ebooks.oeb.polish.container import OPF_NAMESPACES
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.logging import ANSIStream
from polyglot.builtins import is_py3
from polyglot.io import PolyglotStringIO

# lxml isn't great, but I don't have access to defusedxml
from lxml.etree import _Element  # skipcq: BAN-B410

if is_py3:
    from typing import Dict
    from typing import List
    from typing import Optional
    from typing import Union

KOBO_JS_RE = re.compile(r".*/?kobo.*?\.js$", re.IGNORECASE)
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
CONFIGDIR = os.path.join(config_dir, "plugins")
REFERENCE_KEPUB = os.path.join(CONFIGDIR, "reference.kepub.epub")
PLUGIN_VERSION = (3, 7, 1)
PLUGIN_MINIMUM_CALIBRE_VERSION = (5, 0, 0)


class Logger:
    LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}

    def __init__(self) -> None:
        self.log_level = "INFO"
        if (
            "CALIBRE_DEVELOP_FROM" in os.environ
            or "CALIBRE_DEBUG" in os.environ
            or "calibre-debug" in sys.argv[0]
        ):
            self.log_level = "DEBUG"

        # According to Kovid, calibre always uses UTF-8 for the Python 3 version
        self.preferred_encoding = "UTF-8" if is_py3 else preferred_encoding
        self.outputs = [ANSIStream()]

        self.debug = partial(self.print_formatted_log, "DEBUG")
        self.info = partial(self.print_formatted_log, "INFO")
        self.warn = self.warning = partial(self.print_formatted_log, "WARN")
        self.error = partial(self.print_formatted_log, "ERROR")

    def __call__(self, logmsg) -> None:
        self.info(logmsg)

    @staticmethod
    def _tag_args(level: str, *args: str) -> List[str]:
        now = time.localtime()
        buf = PolyglotStringIO()
        tagged_args: List[str] = []
        for arg in args:
            prints(time.strftime("%Y-%m-%d %H:%M:%S", now), file=buf, end=" ")
            buf.write("[")
            prints(level, file=buf, end="")
            buf.write("] ")
            prints(arg, file=buf, end="")

            tagged_args.append(buf.getvalue())
            buf.truncate(0)

        return tagged_args

    def _prints(self, level: str, *args, **kwargs) -> None:
        for o in self.outputs:
            o.prints(self.LEVELS[level], *args, **kwargs)
            if hasattr(o, "flush"):
                o.flush()

    def print_formatted_log(self, level: str, *args, **kwargs) -> None:
        tagged_args = self._tag_args(level, *args)
        self._prints(level, *tagged_args, **kwargs)

    def exception(self, *args, **kwargs) -> None:
        limit = kwargs.pop("limit", None)
        tagged_args = self._tag_args("ERROR", *args)
        self._prints("ERROR", *tagged_args, **kwargs)
        self._prints("ERROR", traceback.format_exc(limit))


log = Logger()


# The logic here to detect a cover image is mostly duplicated from
# metadata/writer.py. Updates to the logic here probably need an accompanying
# update over there.
def modify_epub(
    container: EpubContainer,
    filename: str,
    metadata: Optional[Metadata] = None,
    opts: Optional[Dict[str, Union[str, bool]]] = None,
) -> None:
    """Modify the ePub file to make it KePub-compliant."""
    _modify_start = time.time()
    opts = opts or {}

    # Search for the ePub cover
    # TODO: Refactor out cover detection logic so it can be directly used in
    # metadata/writer.py
    found_cover = False
    opf: _Element = container.opf
    cover_meta_node_list: List[_Element] = opf.xpath(
        './opf:metadata/opf:meta[@name="cover"]', namespaces=OPF_NAMESPACES
    )

    if len(cover_meta_node_list) > 0:
        cover_meta_node: _Element = cover_meta_node_list[0]
        cover_id = cover_meta_node.attrib.get("content", None)

        log.debug("Found meta node with name=cover")

        if cover_id:
            log.info(f"Found cover image ID '{cover_id}'")

            cover_node_list: _Element = opf.xpath(
                f'./opf:manifest/opf:item[@id="{cover_id}"]',
                namespaces=OPF_NAMESPACES,
            )
            if len(cover_node_list) > 0:
                cover_node: _Element = cover_node_list[0]

                log.debug("Found an item node with cover ID")

                if cover_node.attrib.get("properties", "") != "cover-image":
                    log.info("Setting cover-image property")
                    cover_node.set("properties", "cover-image")
                    container.dirty(container.opf_name)
                else:
                    log.warning("Item node is already set as cover-image")
                found_cover = True

    # It's possible that the cover image can't be detected this way. Try
    # looking for the cover image ID in the OPF manifest.
    if not found_cover:
        log.debug("Looking for cover image in OPF manifest")

        node_list: List[_Element] = opf.xpath(
            "./opf:manifest/opf:item[(translate(@id, "
            + "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
            + '="cover" or starts-with(translate(@id, '
            + "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
            + ', "cover")) and starts-with(@media-type, "image")]',
            namespaces=OPF_NAMESPACES,
        )
        if len(node_list) > 0:
            log.info(
                f"Found {len(node_list)} nodes, assuming the first is the right node"
            )

            node: _Element = node_list[0]
            if node.attrib.get("properties", "") != "cover-image":
                log.info("Setting cover-image property")
                node.set("properties", "cover-image")
                container.dirty(container.opf_name)
            else:
                log.warning("Item node is already set as cover-image")
            found_cover = True

    # Hyphenate files?
    if opts.get("no-hyphens", False):
        nohyphen_css = PersistentTemporaryFile(suffix="_nohyphen", prefix="kepub_")
        nohyphen_css.write(get_resources("css/no-hyphens.css"))
        nohyphen_css.close()

        css_path = os.path.basename(
            container.copy_file_to_container(
                nohyphen_css.name, name="kte-css/no-hyphens.css"
            )
        )
        container.add_content_file_reference(f"kte-css/{css_path}")
        os.unlink(nohyphen_css.name)
    elif opts.get("hyphenate", False) and int(opts.get("hyphen_min_chars", 6)) > 0:
        if metadata and metadata.language == NULL_VALUES["language"]:
            log.warning(
                "Hyphenation is enabled but not overriding content file "
                + "language. Hyphenation may use the wrong dictionary."
            )
        hyphen_css = PersistentTemporaryFile(suffix="_hyphenate", prefix="kepub_")
        css_template = get_resources("css/hyphenation.css.tmpl").decode()
        hyphen_limit_lines = opts.get("hyphen_limit_lines", 2)
        if hyphen_limit_lines == 0:
            hyphen_limit_lines = "no-limit"
        hyphen_css.write(
            css_template.format(
                hyphen_min_chars=opts.get("hyphen_min_chars"),
                hyphen_min_chars_before=opts.get("hyphen_min_chars_before", 3),
                hyphen_min_chars_after=opts.get("hyphen_min_chars_after", 3),
                hyphen_limit_lines=hyphen_limit_lines,
            ).encode()
        )
        hyphen_css.close()

        css_path = os.path.basename(
            container.copy_file_to_container(
                hyphen_css.name, name="kte-css/hyphenation.css"
            )
        )
        container.add_content_file_reference(f"kte-css/{css_path}")
        os.unlink(hyphen_css.name)

    # Now smarten punctuation
    if opts.get("smarten_punctuation", False):
        container.smarten_punctuation()

    if opts.get("extended_kepub_features", True):
        if metadata is not None:
            log.info(
                f"Adding extended Kobo features to {metadata.title} by "
                + " and ".join(metadata.authors)
            )

        # Add the Kobo span and div tags
        container.convert()

        # Check to see if there's already a kobo*.js in the ePub
        skip_js = False
        for name in container.name_path_map:
            if KOBO_JS_RE.match(name):
                skip_js = True
                break

        if os.path.isfile(REFERENCE_KEPUB) and not skip_js:
            reference_container = EpubContainer(REFERENCE_KEPUB, log)
            for name in reference_container.name_path_map:
                if KOBO_JS_RE.match(name):
                    jsname = container.copy_file_to_container(
                        os.path.join(reference_container.root, name), name="kobo.js"
                    )
                    container.add_content_file_reference(jsname)
                    break

        # Add the Kobo style hacks
        stylehacks_css = PersistentTemporaryFile(suffix="_stylehacks", prefix="kepub_")
        stylehacks_css.write(get_resources("css/style-hacks.css"))
        stylehacks_css.close()

        css_path = os.path.basename(
            container.copy_file_to_container(
                stylehacks_css.name, name="kte-css/stylehacks.css"
            )
        )
        container.add_content_file_reference(f"kte-css/{css_path}")
    os.unlink(filename)
    container.commit(filename)

    _modify_time = time.time() - _modify_start
    log.info(f"modify_epub took {_modify_time:0.2f} seconds")


def intValueChanged(widget, singular, plural, *args, **kwargs):
    from PyQt5 import QtWidgets

    if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
        widget.setSuffix(" " + ngettext(singular, plural, widget.value()))
