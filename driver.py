# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from contextlib import closing

__license__ = 'GPL v3'
__copyright__ = '2013, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

import os
import re
import shutil
import sqlite3 as sqlite
import sys

from calibre.constants import config_dir
from calibre.devices.kobo.driver import KOBOTOUCH
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.metadata.book.base import NULL_VALUES
from calibre_plugins.kobotouch_extended.container import Container
from calibre_plugins.kobotouch_extended.hyphenator import Hyphenator

from copy import deepcopy
from lxml import etree

EPUB_EXT = '.epub'


class DRMEncumberedEPub(ValueError):
    def __init__(self, name, author):
        self.name = name
        self.author = author
        ValueError.__init__(self, _("ePub '{0}' by '{1}' is encumbered by DRM").format(name, author))


class InvalidEPub(ValueError):
    def __init__(self, name, author, message, fname=None, lineno=None):
        self.name = name
        self.author = author
        self.message = message
        self.fname = fname
        self.lineno = lineno
        ValueError.__init__(self, _("Failed to parse '{0}' by '{1}' with error: '{2}' (file: {3}, line: {4})".format(name, author, message, fname, lineno)))


class KOBOTOUCHEXTENDED(KOBOTOUCH):
    '''Extended driver for Kobo Touch, Kobo Glo, and Kobo Mini devices.

    This driver automatically modifies ePub files to include extra information
    used by Kobo devices to enable annotations and display of chapter names and
    page numbers on a per-chapter basis. Files are also transferred using the
    'kepub' designation ({name}.kepub.{ext}) automatically to trigger the Kobo
    device to enable these features. This also enabled more detailed reading
    statistics accessible within each book.
    '''

    name = 'KoboTouchExtended'
    gui_name = 'Kobo Touch/Glo/Mini'
    author = 'Joel Goguen'
    description = 'Communicate with the Kobo Touch, Glo, and Mini firmwares and enable extended Kobo ePub features.'
    configdir = os.path.join(config_dir, 'plugins', 'KoboTouchExtended')
    reference_kepub = os.path.join(configdir, 'reference.kepub.epub')

    minimum_calibre_version = (0, 9, 29)
    version = (1, 4, 4)

    content_types = {
        "main": 6,
        "content": 9,
        "toc": 899
    }

    supported_dbversion = 80
    min_supported_dbversion = 65
    max_supported_fwversion = (2, 6, 1)
    min_fwversion_tiles = (2, 6, 1)

    EXTRA_CUSTOMIZATION_MESSAGE = KOBOTOUCH.EXTRA_CUSTOMIZATION_MESSAGE[:]
    EXTRA_CUSTOMIZATION_DEFAULT = KOBOTOUCH.EXTRA_CUSTOMIZATION_DEFAULT[:]

    EXTRA_CUSTOMIZATION_MESSAGE.append('Enable Extended Features:::Choose whether to enable extra customisations')
    EXTRA_CUSTOMIZATION_DEFAULT.append(True)
    OPT_EXTRA_FEATURES = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Delete Files not in Manifest:::Select this to silently delete files that are not in the manifest if they are encountered during processing. '
                                                 'If this option is not selected, files not in the manifest will be silently added to the manifest and processed as if they always were in the manifest.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_DELETE_UNMANIFESTED = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Upload DRM-encumbered ePub files:::Select this to upload ePub files encumbered by DRM. If this is not selected, it is a fatal error to upload an encumbered file')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_UPLOAD_ENCUMBERED = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Silently Ignore Failed Conversions:::Select this to not upload any book that fails conversion to kepub. If this is not selected, the upload process '
                                                 'will be stopped at the first book that fails. If this is selected, failed books will be silently removed from the upload queue.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_SKIP_FAILED = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Hyphenate Files:::Select this to add soft hyphens to uploaded ePub files. The language used will be the language defined for the book in calibre. '
                                                 ' It is necessary to have a LibreOffice/OpenOffice hyphenation dictionary in ' + os.path.join(config_dir, 'plugins', 'KoboTouchExtended') +
                                                 ' named like hyph_{language}.dic, where {language} is the ISO 639 3-letter language code. For example, \'eng\' but not \'en_CA\'. The default dictionary to use '
                                                 ' if none is found may be named \'hyph.dic\' instead.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_HYPHENATE = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Replace Content Language Code:::Select this to replace the defined language in each content file inside the ePub.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_REPLACE_LANG = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Smarten Punctuation:::Select this to smarten punctuation in the ePub')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_SMARTEN_PUNCTUATION = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Clean up ePub Markup:::Select this to clean up the internal ePub markup.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_CLEAN_MARKUP = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Copy generated KePub files to a directory:::Enter an absolute directory path to copy all generated KePub files into for debugging purposes.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(u'')
    OPT_FILE_COPY_DIR = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Dismiss New Book Tiles:::Firmware 2.6.1 introduced the Aura-style home screen. Select this option to dismiss the New Book tiles normally added '
                                       'when new books are loaded. Unplug and plug back in the device for this to take effect. Only applies to books added after doing this.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_HIDE_NEW_BOOK_TILES = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    skip_renaming_files = []
    hyphenator = None
    kobo_js_re = re.compile(r'.*/?kobo.*\.js$', re.IGNORECASE)
    invalid_filename_chars_re = re.compile(r'[\/\\\?%\*:;\|\"\'><\$]', re.IGNORECASE | re.UNICODE)

    def initialize(self):
        if not os.path.isdir(self.configdir):
            os.makedirs(self.configdir)
        super(KOBOTOUCHEXTENDED, self).initialize()

    def books(self, oncard=None, end_session=True):
        bl = super(KOBOTOUCHEXTENDED, self).books(oncard=oncard, end_session=end_session)

        # Only process database triggers on the main device run
        opts = self.settings()
        if oncard is None:
            with closing(sqlite.connect(self.device_database_path())) as conn:
                if isinstance(self.fwversion, tuple) and self.fwversion >= self.min_fwversion_tiles and opts.extra_customization[self.OPT_HIDE_NEW_BOOK_TILES]:
                    sql = get_resources('sql/DismissNewBookTiles.sql')
                    if sql:
                        debug_print("KoboTouchExtended - Adding DismissNewBookTiles database trigger")
                        sql = unicode(sql)
                        conn.execute(sql)
                    else:
                        debug_print("KoboTouchExtended - Could not fetch DismissNewBookTiles trigger SQL definition!")
                else:
                    debug_print("KoboTouchExtended - Dropping DismissNewBookTiles database trigger")
                    conn.execute("DROP TRIGGER IF EXISTS KTE_Activity_DismissNewBookTiles")

        return bl

    def _modify_epub(self, file, metadata):
        opts = self.settings()
        debug_print("KoboTouchExtended:_modify_epub:Processing {0}".format(metadata.title))

        skip_failed = opts.extra_customization[self.OPT_SKIP_FAILED]
        if skip_failed:
            debug_print("KoboTouchExtended:_modify_epub:Failed conversions will be skipped")
        else:
            debug_print("KoboTouchExtended:_modify_epub:Failed conversions will raise exceptions")

        container = Container(file)
        if container.is_drm_encumbered:
            debug_print("KoboTouchExtended:_modify_epub:ERROR: ePub is DRM-encumbered, not modifying")
            self.skip_renaming_files.append(metadata.uuid)
            if opts.extra_customization[self.OPT_UPLOAD_ENCUMBERED]:
                raise DRMEncumberedEPub(metadata.title, ", ".join(metadata.authors))
            else:
                return False

        # Because of the changes made to the markup here, cleanup needs to be done before anything else
        container.forced_cleanup();
        if opts.extra_customization[self.OPT_CLEAN_MARKUP]:
            container.clean_markup()
        # Now add the Kobo span tags
        container.add_kobo_spans()
        # Now smarten punctuation -- must happen before hyphenation
        if opts.extra_customization[self.OPT_SMARTEN_PUNCTUATION]:
            container.smarten_punctuation()
        # Hyphenate files -- must happen after smartening punctuation
        if opts.extra_customization[self.OPT_HYPHENATE]:
            hyphenator = None
            dictfile = None
            for lang in metadata.languages:
                if lang == 'und':
                    continue
                dictfile = os.path.join(self.configdir, "hyph_{0}.dic".format(lang))
                if os.path.isfile(dictfile):
                    break
            if dictfile is None or not os.path.isfile(dictfile):
                dictfile = os.path.join(self.configdir, "hyph.dic")
            if dictfile is not None and os.path.isfile(dictfile):
                debug_print("KoboTouchExtended:_modify_epub:Using hyphenation dictionary {0}".format(dictfile))
                hyphenator = Hyphenator(dictfile)
            if hyphenator is not None:
                container.hyphenate(hyphenator)

        skip_js = False
        # Check to see if there's already a kobo*.js in the ePub
        for name in container.name_map:
            if self.kobo_js_re.match(name):
                skip_js = True
                break
        if not skip_js:
            if os.path.isfile(self.reference_kepub):
                reference_container = Container(self.reference_kepub)
                for name in reference_container.name_map:
                    if self.kobo_js_re.match(name):
                        jsname = container.copy_file_to_container(os.path.join(reference_container.root, name), name='kobo.js')
                        container.add_content_file_reference(jsname)
                        break

        found_cover = False
        opf = container.opf
        cover_meta_node = opf.xpath('./opf:metadata/opf:meta[@name="cover"]', namespaces=container.namespaces)
        if len(cover_meta_node) > 0:
            cover_meta_node = cover_meta_node[0]
            cover_id = cover_meta_node.attrib["content"] if "content" in cover_meta_node.attrib else None
            if cover_id is not None:
                debug_print("KoboTouchExtended:_modify_epub:Found cover image id {0}".format(cover_id))
                cover_node = opf.xpath('./opf:manifest/opf:item[@id="{0}"]'.format(cover_id), namespaces=container.namespaces)
                if len(cover_node) > 0:
                    cover_node = cover_node[0]
                    if "properties" not in cover_node.attrib or cover_node.attrib["properties"] != "cover-image":
                        debug_print("KoboTouchExtended:_modify_epub:Setting cover-image")
                        cover_node.set("properties", "cover-image")
                        container.set(container.opf_name, opf)
                        found_cover = True

        # It's possible that the cover image can't be detected this way. Try looking for the cover image ID in the OPF manifest.
        if not found_cover:
            debug_print("KoboTouchExtended:_modify_epub:Looking for cover image in OPF manifest")
            node_list = opf.xpath('./opf:manifest/opf:item[(@id="cover" or starts-with(@id, "cover")) and starts-with(@media-type, "image")]', namespaces=container.namespaces)
            if len(node_list) > 0:
                node = node_list[0]
                if "properties" not in node.attrib or node.attrib["properties"] != 'cover-image':
                    debug_print("KoboTouchExtended:_modify_epub:Setting cover-image")
                    node.set("properties", "cover-image")
                    container.set(container.opf_name, opf)
                    found_cover = True

        for name in container.get_html_names():
            debug_print("KoboTouchExtended:_modify_epub:Processing HTML {0}".format(name))
            root = container.get(name)
            if not hasattr(root, 'xpath'):
                if opts.extra_customization[self.OPT_DELETE_UNMANIFESTED]:
                    debug_print("KoboTouchExtended:_modify_epub:Removing unmanifested file {0}".format(name))
                    os.unlink(os.path.join(container.root, name))
                    continue
                else:
                    item = container.manifest_item_for_name(name)
                    if item is None:
                        debug_print("KoboTouchExtended:_modify_epub:Adding unmanifested item {0} to the manifest".format(name))
                        container.add_name_to_manifest(name)
                        root = container.get(name)
                    if item is not None or not hasattr(root, "xpath"):
                        debug_print("KoboTouchExtended:_modify_epub:{0} is not a XML-based format".format(name))
                        continue

            if opts.extra_customization[self.OPT_REPLACE_LANG] and metadata.language != NULL_VALUES["language"]:
                root.attrib["{%s}lang" % container.namespaces["xml"]] = metadata.language
                root.attrib["lang"] = metadata.language

        os.unlink(file)
        container.write(file)

        return True

    def upload_books(self, files, names, on_card=None, end_session=True, metadata=None):
        opts = self.settings()
        skip_failed = opts.extra_customization[self.OPT_SKIP_FAILED]
        new_files = []
        new_names = []
        new_metadata = []
        errors = []
        if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
            debug_print("KoboTouchExtended:upload_books:Enabling extra ePub features for Kobo devices")
            i = 0
            for file, n, mi in zip(files, names, metadata):
                self.report_progress(i / float(len(files)), "Processing book: {0} by {1}".format(mi.title, " and ".join(mi.authors)))
                ext = file[file.rfind('.'):]
                if ext == EPUB_EXT:
                    try:
                        self._modify_epub(file, mi)
                    except Exception as e:
                        (exc_type, exc_obj, exc_tb) = sys.exc_info()
                        while exc_tb.tb_next and 'kobotouch_extended' in exc_tb.tb_next.tb_frame.f_code.co_filename:
                            exc_tb = exc_tb.tb_next
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        if not skip_failed:
                            raise InvalidEPub(mi.title, " and ".join(mi.authors), e.message, fname=fname, lineno=exc_tb.tb_lineno)
                        else:
                            errors.append("Failed to upload {0} with error: {1}".format("'{0}' by '{1}'".format(mi.title, " and ".join(mi.authors)), e.message))
                            if mi.uuid not in self.skip_renaming_files:
                                self.skip_renaming_files.append(mi.uuid)
                            debug_print("Failed to process {0} by {1} with error: {2} (file: {3}, lineno: {4})".format(mi.title, " and ".join(mi.authors), e.message, fname, exc_tb.tb_lineno))
                    else:
                        new_files.append(file)
                        new_names.append(n)
                        new_metadata.append(mi)

                        dpath = opts.extra_customization[self.OPT_FILE_COPY_DIR]
                        dpath = os.path.expanduser(dpath)
                        if dpath.strip() != '' and os.path.isabs(dpath) and os.path.isdir(dpath):
                            dstpath = os.path.join(dpath, "{0} - {1}.kepub.epub".format(self.invalid_filename_chars_re.sub('_', mi.title_sort), mi.authors[0]))
                            debug_print("KoboTouchExtended:upload_books:Copying generated KePub file to {0}".format(dstpath))
                            shutil.copy(file, dstpath)
                else:
                    new_files.append(file)
                    new_names.append(n)
                    new_metadata.append(mi)
                i += 1
        else:
            new_files = files
            new_names = names
            new_metadata = metadata

        if metadata and new_metadata and len(metadata) != len(new_metadata) and len(new_metadata) > 0:
            print("The following books could not be processed and will not be uploaded to your device:")
            print("\n".join(errors))

        self.report_progress(0, 'Working...')
        result = super(KOBOTOUCHEXTENDED, self).upload_books(new_files, new_names, on_card, end_session, new_metadata)

        return result

    def filename_callback(self, path, mi):
        opts = self.settings()
        if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
            debug_print("KoboTouchExtended:filename_callback:Path - {0}".format(path))

            idx = path.rfind('.')
            ext = path[idx:]
            if ext == EPUB_EXT and mi.uuid not in self.skip_renaming_files:
                path = "{0}.kepub{1}".format(path[:idx], EPUB_EXT)
                debug_print("KoboTouchExtended:filename_callback:New path - {0}".format(path))

        return path

    def sanitize_path_components(self, components):
        return [self.invalid_filename_chars_re.sub('_', x) for x in components]

    def sync_booklists(self, booklists, end_session=True):
        opts = self.settings()
        if opts.extra_customization[self.OPT_UPLOAD_COVERS]:
            debug_print("KoboTouchExtended:sync_booklists:Setting ImageId fields")

            select_query = "SELECT ContentId FROM content WHERE ContentType = ? AND (ImageId IS NULL OR ImageId = '')"
            update_query = "UPDATE content SET ImageId = ? WHERE ContentId = ?"
            db = sqlite.connect(os.path.join(self._main_prefix, ".kobo", "KoboReader.sqlite"), isolation_level=None)
            db.text_factory = lambda x: unicode(x, "utf-8", "ignore")

            def __rows_needing_imageid():
                """Returns a dict object with keys being the ContentID of a row without an ImageID.
                """
                c = db.cursor()
                d = {}
                c.execute(select_query, (self.content_types['main'],))
                for row in c:
                    d[row[0]] = 1
                return d

            all_nulls = __rows_needing_imageid()
            debug_print("KoboTouchExtended:sync_booklists:Got {0} rows to update".format(str(len(all_nulls.keys()))))
            nulls = []
            for booklist in booklists:
                for b in booklist:
                    if b.application_id is not None and b.contentID in all_nulls:
                        nulls.append((self.imageid_from_contentid(b.contentID), b.contentID))
            del(all_nulls)

            cursor = db.cursor()
            while nulls[:100]:
                debug_print("KoboTouchExtended:sync_booklists:Updating {0} ImageIDs...".format(str(len(nulls[:100]))))
                cursor.executemany(update_query, nulls[:100])
                db.commit()
                del(nulls[:100])
            cursor.close()
            db.close()
            debug_print("KoboTouchExtended:sync_booklists:done setting ImageId fields")

        super(KOBOTOUCHEXTENDED, self).sync_booklists(booklists, end_session)
