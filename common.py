# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

"""Common functions and variables needed by more than one plugin."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__license__ = "GPL v3"
__copyright__ = "2013, Joel Goguen <jgoguen@jgoguen.ca>"
__docformat__ = "markdown en"

# Be careful editing this! This file has to work in multiple packages at once,
# so don't import anything from calibre_plugins

import os
import re
import sys

from calibre.constants import config_dir
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.base import NULL_VALUES
from calibre.ebooks.oeb.polish.container import EpubContainer
from calibre.ebooks.oeb.polish.container import OPF_NAMESPACES
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.logging import DEBUG
from calibre.utils.logging import INFO
from calibre.utils.logging import ThreadSafeLog

from lxml.etree import _Element

try:
    # Python 3
    from typing import Dict
    from typing import List
    from typing import Optional
    from typing import Union
except ImportError:
    # Python 2
    pass

kobo_js_re = re.compile(r".*/?kobo.*\.js$", re.IGNORECASE)
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
configdir = os.path.join(config_dir, "plugins")  # type: str
reference_kepub = os.path.join(configdir, "reference.kepub.epub")  # type: str
plugin_version = (3, 2, 0)
plugin_minimum_calibre_version = (2, 60, 0)


class Logger(ThreadSafeLog):
    def __init__(self):
        log_level = INFO
        if (
            "CALIBRE_DEVELOP_FROM" in os.environ
            or "CALIBRE_DEBUG" in os.environ
            or "calibre-debug" in sys.argv[0]
        ):
            log_level = DEBUG

        super(ThreadSafeLog, self).__init__(log_level)


log = Logger()


# The logic here to detect a cover image is mostly duplicated from
# metadata/writer.py. Updates to the logic here probably need an accompanying
# update over there.
def modify_epub(
    container,  # type: EpubContainer
    filename,  # type: str
    metadata=None,  # type: Optional[Metadata]
    opts={},  # type: Dict[str, Union[str, bool]]
):  # type: (...) -> None
    """Modify the ePub file to make it KePub-compliant."""
    # Search for the ePub cover
    # TODO: Refactor out cover detection logic so it can be directly used in
    # metadata/writer.py
    found_cover = False  # type: bool
    opf = container.opf  # type: _Element
    cover_meta_node_list = opf.xpath(
        './opf:metadata/opf:meta[@name="cover"]', namespaces=OPF_NAMESPACES
    )  # List[_Element]

    if len(cover_meta_node_list) > 0:
        cover_meta_node = cover_meta_node_list[0]  # type: _Element
        cover_id = cover_meta_node.attrib.get("content", None)

        log.debug("Found meta node with name=cover: {0}".format(cover_meta_node))

        if cover_id:
            log.info("Found cover image ID '{0}'".format(cover_id))

            cover_node_list = opf.xpath(
                './opf:manifest/opf:item[@id="{0}"]'.format(cover_id),
                namespaces=OPF_NAMESPACES,
            )  # type: List[_Element]
            if len(cover_node_list) > 0:
                cover_node = cover_node_list[0]  # type: _Element

                log.debug("Found an item node with cover ID: {0}".format(cover_node))

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

        node_list = opf.xpath(
            "./opf:manifest/opf:item[(translate(@id, "
            + "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
            + '="cover" or starts-with(translate(@id, '
            + "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
            + ', "cover")) and starts-with(@media-type, "image")]',
            namespaces=OPF_NAMESPACES,
        )  # type: List[_Element]
        if len(node_list) > 0:
            log.info(
                "Found {0:d} nodes, assuming the first is the "
                "right node".format(len(node_list))
            )

            node = node_list[0]  # type: _Element
            if node.attrib.get("properties", "") != "cover-image":
                log.info("Setting cover-image property")
                node.set("properties", "cover-image")
                container.dirty(container.opf_name)
            else:
                log.warning("Item node is already set as cover-image")
            found_cover = True

    # Because of the changes made to the markup here, cleanup needs to be done
    # before any other content file processing
    container.forced_cleanup()
    if opts.get("clean_markup", False):
        container.clean_markup()

    # Hyphenate files?
    if opts.get("no-hyphens", False):
        nohyphen_css = PersistentTemporaryFile(
            suffix="_nohyphen", prefix="kepub_"
        )  # type: PersistentTemporaryFile
        nohyphen_css.write(get_resources("css/no-hyphens.css"))  # noqa: F821
        nohyphen_css.close()

        css_path = os.path.basename(
            container.copy_file_to_container(
                nohyphen_css.name, name="kte-css/no-hyphens.css"
            )
        )  # type: str
        container.add_content_file_reference("kte-css/{0}".format(css_path))
        os.unlink(nohyphen_css.name)
    elif opts.get("hyphenate", False):
        if metadata and metadata.language == NULL_VALUES["language"]:
            log.warning(
                "Hyphenation is enabled but not overriding content file "
                "language. Hyphenation may use the wrong dictionary."
            )
        hyphen_css = PersistentTemporaryFile(
            suffix="_hyphenate", prefix="kepub_"
        )  # type: PersistentTemporaryFile
        hyphen_css.write(get_resources("css/hyphenation.css"))  # noqa: F821
        hyphen_css.close()

        css_path = os.path.basename(
            container.copy_file_to_container(
                hyphen_css.name, name="kte-css/hyphenation.css"
            )
        )  # type: str
        container.add_content_file_reference("kte-css/{0}".format(css_path))
        os.unlink(hyphen_css.name)

    # Now smarten punctuation
    if opts.get("smarten_punctuation", False):
        container.smarten_punctuation()

    if opts.get("extended_kepub_features", True):
        if metadata is not None:
            log.info(
                "Adding extended Kobo features to {0} by {1}".format(
                    metadata.title, " and ".join(metadata.authors)
                )
            )

        # Add the Kobo span tags
        container.add_kobo_spans()

        # Add the Kobo style hacks div tags
        container.add_kobo_divs()

        # Check to see if there's already a kobo*.js in the ePub
        skip_js = False  # type: str
        for name in container.name_path_map:
            if kobo_js_re.match(name):
                skip_js = True
                break

        if not skip_js:
            if os.path.isfile(reference_kepub):
                reference_container = EpubContainer(reference_kepub, log)
                for name in reference_container.name_path_map:
                    if kobo_js_re.match(name):
                        jsname = container.copy_file_to_container(
                            os.path.join(reference_container.root, name), name="kobo.js"
                        )
                        container.add_content_file_reference(jsname)
                        break

        # Add the Kobo style hacks
        stylehacks_css = PersistentTemporaryFile(suffix="_stylehacks", prefix="kepub_")
        stylehacks_css.write(get_resources("css/style-hacks.css"))  # noqa: F821
        stylehacks_css.close()

        css_path = os.path.basename(
            container.copy_file_to_container(
                stylehacks_css.name, name="kte-css/stylehacks.css"
            )
        )
        container.add_content_file_reference("kte-css/{0}".format(css_path))
    os.unlink(filename)
    container.commit(filename)
