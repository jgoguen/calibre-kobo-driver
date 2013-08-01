# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2013, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

import json
import os
import re
import shutil
import sqlite3 as sqlite
import sys

from PyQt4.Qt import QCoreApplication
from PyQt4.Qt import QScrollArea
from calibre.constants import config_dir
from calibre.devices.kobo.driver import KOBOTOUCH
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.metadata.book.base import NULL_VALUES
from calibre.ebooks.oeb.polish.container import OPF_NAMESPACES
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.logging import default_log
from calibre_plugins.kobotouch_extended.container import KEPubContainer
from contextlib import closing
from datetime import datetime


EPUB_EXT = '.epub'
XML_NAMESPACE = 'http://www.w3.org/XML/1998/namespace'


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

    minimum_calibre_version = (0, 9, 42)
    version = (2, 1, 0)

    content_types = {
        "main": 6,
        "content": 9,
        "toc": 899
    }

    supported_dbversion = 80
    min_supported_dbversion = 65
    max_supported_fwversion = (2, 8, 1)
    min_fwversion_tiles = (2, 6, 1)

    EXTRA_CUSTOMIZATION_MESSAGE = KOBOTOUCH.EXTRA_CUSTOMIZATION_MESSAGE[:]
    EXTRA_CUSTOMIZATION_DEFAULT = KOBOTOUCH.EXTRA_CUSTOMIZATION_DEFAULT[:]

    EXTRA_CUSTOMIZATION_MESSAGE.append('Enable Extended Kobo Features:::Choose whether to enable extra customisations')
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

    EXTRA_CUSTOMIZATION_MESSAGE.append('Hyphenate Files:::Select this to add a CSS file which enables hyphenation. The language used will be the language defined for the book in calibre. '
                                                 ' Please see the README file for directions on adding/updating hyphenation dictionaries.')
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

    EXTRA_CUSTOMIZATION_MESSAGE.append('Block Kobo Analytics DB:::Kobo Analytics events are stored in the database. Select this option to delete any current events and block the '
                                       'addition of new events.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_BLOCK_ANALYTICS_DB_EVENTS = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append('Dismiss Award Tiles:::Firmware 2.6.1 introduced the Aura-style home screen. Select this option to dismiss the Award tiles normally shown '
                                       'on the home screen.')
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_HIDE_AWARDS_TILES = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    skip_renaming_files = set([])
    hyphenator = None
    kobo_js_re = re.compile(r'.*/?kobo.*\.js$', re.IGNORECASE)
    invalid_filename_chars_re = re.compile(r'[\/\\\?%\*:;\|\"\'><\$]', re.IGNORECASE | re.UNICODE)

    def modifying_epub(self):
        opts = self.settings().extra_customization
        return self.modifying_css() or opts[self.OPT_CLEAN_MARKUP] or \
            opts[self.OPT_EXTRA_FEATURES] or opts[self.OPT_DELETE_UNMANIFESTED] or \
            opts[self.OPT_REPLACE_LANG] or opts[self.OPT_HYPHENATE] or \
            opts[self.OPT_SMARTEN_PUNCTUATION]

    @classmethod
    def config_widget(cls):
        cw = super(KOBOTOUCHEXTENDED, cls).config_widget()
        qsa = QScrollArea()
        qsa.setWidgetResizable(True)
        qsa.setWidget(cw)
        qsa.validate = cw.validate
        desktop_geom = QCoreApplication.instance().desktop().availableGeometry()
        if desktop_geom.height() < 800:
            qsa.setBaseSize(qsa.size().width(), desktop_geom.height() - 100)
        return qsa

    @classmethod
    def save_settings(cls, config_widget):
        super(KOBOTOUCHEXTENDED, cls).save_settings(config_widget.widget())

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
                if isinstance(self.fwversion, tuple) and self.fwversion >= self.min_fwversion_tiles:
                    if opts.extra_customization[self.OPT_HIDE_NEW_BOOK_TILES]:
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

                    if opts.extra_customization[self.OPT_HIDE_AWARDS_TILES]:
                        sql = get_resources('sql/DismissAwardTiles.sql')
                        if sql:
                            debug_print("KoboTouchExtended - Adding DismissAwardTiles database trigger")
                            sql = unicode(sql)
                            conn.execute(sql)
                        else:
                            debug_print("KoboTouchExtended - Could not fetch DismissAwardTiles trigger SQL definition!")
                    else:
                        debug_print("KoboTouchExtended - Dropping DismissAwardTiles databsae trigger")
                        conn.execute("DROP TRIGGER IF EXISTS KTE_Activity_DismissAwardTiles")

                # Put this in a try-catch block. It's OK if this fails.
                try:
                    if opts.extra_customization[self.OPT_BLOCK_ANALYTICS_DB_EVENTS]:
                        sql = get_resources('sql/BlockAnalyticsEvents.sql')
                        if sql:
                            debug_print("KoboTouchExtended - Adding BlockAnalyticsEvents database trigger")
                            sql = unicode(sql)
                            conn.executescript(sql)
                        else:
                            debug_print("KoboTouchExtended - Could not fetch BlockAnalyticsEvents trigger SQL definition")
                    else:
                        debug_print("KoboTouchExtended - Dropping BlockAnalyticsEvents database trigger")
                        conn.execute("DROP TRIGGER IF EXISTS KTE_BlockAnalyticsEvents")
                except Exception as e:
                    debug_print("KoboTouchExtended - Exception raised while processing BlockAnalyticsEvents database trigger: {0}".format(str(e)))

        return bl

    def _modify_epub(self, file, metadata, container=None):
        if not file.endswith(EPUB_EXT):
            self.skip_renaming_files.add(metadata.uuid)
            return super(KOBOTOUCHEXTENDED, self)._modify_epub(file, metadata, container)

        debug_print("KoboTouchExtended:_modify_epub:Adding basic Kobo features to {0} by {1}".format(metadata.title, ' and '.join(metadata.authors)))
        opts = self.settings()

        skip_failed = opts.extra_customization[self.OPT_SKIP_FAILED]
        if skip_failed:
            debug_print("KoboTouchExtended:_modify_epub:Failed conversions will be skipped")
        else:
            debug_print("KoboTouchExtended:_modify_epub:Failed conversions will raise exceptions")

        if container is None:
            container = KEPubContainer(file, default_log)

        # This is the try-except block for the 'basic' additional features
        try:
            if container.is_drm_encumbered:
                debug_print("KoboTouchExtended:_modify_epub:ERROR: ePub is DRM-encumbered, not modifying")
                self.skip_renaming_files.add(metadata.uuid)
                if opts.extra_customization[self.OPT_UPLOAD_ENCUMBERED]:
                    return super(KOBOTOUCHEXTENDED, self)._modify_epub(file, metadata, container)
                else:
                    return False

            # Add the conversion info file
            book_details = {}
            calibre_details_file = self.normalize_path(os.path.join(self._main_prefix, 'driveinfo.calibre'))
            debug_print("KoboTouchExtended:_modify_epub:Calibre details file :: {0}".format(calibre_details_file))
            o = {}
            if os.path.isfile:
                f = open(calibre_details_file, 'rb')
                o = json.loads(f.read())
                f.close()
                for prop in ('device_store_uuid', 'prefix', 'last_library_uuid', 'location_code'):
                    del(o[prop])
            else:
                debug_print("KoboTouchExtended:_modify_file:Calibre details file does not exist!")
            o['kobotouchextended_version'] = ".".join([str(n) for n in self.version])
            o['kobotouchextended_options'] = str(opts.extra_customization)
            o['kobotouchextended_currenttime'] = datetime.utcnow().ctime()

            kte_data_file = PersistentTemporaryFile(suffix='_KoboTouchExtended', prefix='driverinfo_')
            debug_print("KoboTouchExtended:_modify_epub:Driver data file :: {0}".format(kte_data_file.name))
            kte_data_file.write(json.dumps(o))
            kte_data_file.close()
            container.copy_file_to_container(kte_data_file.name, name='driverinfo.kte', mt='application/json')

            # Search for the ePub cover
            found_cover = False
            opf = container.opf
            cover_meta_node = opf.xpath('./opf:metadata/opf:meta[@name="cover"]', namespaces=OPF_NAMESPACES)
            if len(cover_meta_node) > 0:
                cover_meta_node = cover_meta_node[0]
                cover_id = cover_meta_node.attrib["content"] if "content" in cover_meta_node.attrib else None
                if cover_id is not None:
                    debug_print("KoboTouchExtended:_modify_epub:Found cover image ID '{0}'".format(cover_id))
                    cover_node = opf.xpath('./opf:manifest/opf:item[@id="{0}"]'.format(cover_id), namespaces=OPF_NAMESPACES)
                    if len(cover_node) > 0:
                        cover_node = cover_node[0]
                        if "properties" not in cover_node.attrib or cover_node.attrib["properties"] != "cover-image":
                            debug_print("KoboTouchExtended:_modify_epub:Setting cover-image property")
                            cover_node.set("properties", "cover-image")
                            container.dirty(container.opf_name)
                            found_cover = True
            # It's possible that the cover image can't be detected this way. Try looking for the cover image ID in the OPF manifest.
            if not found_cover:
                debug_print("KoboTouchExtended:_modify_epub:Looking for cover image in OPF manifest")
                node_list = opf.xpath('./opf:manifest/opf:item[(@id="cover" or starts-with(@id, "cover")) and starts-with(@media-type, "image")]', namespaces=OPF_NAMESPACES)
                if len(node_list) > 0:
                    node = node_list[0]
                    if "properties" not in node.attrib or node.attrib["properties"] != 'cover-image':
                        debug_print("KoboTouchExtended:_modify_epub:Setting cover-image")
                        node.set("properties", "cover-image")
                        container.dirty(container.opf_name)
                        found_cover = True

            # Because of the changes made to the markup here, cleanup needs to be done before any other content file processing
            container.forced_cleanup()
            if opts.extra_customization[self.OPT_CLEAN_MARKUP]:
                container.clean_markup()

            # Hyphenate files?
            if opts.extra_customization[self.OPT_HYPHENATE]:
                hyphenation_css = os.path.join(self.configdir, 'hyphenation.css')
                f = open(hyphenation_css, 'w')
                f.write(get_resources('css/hyphenation.css'))
                f.close()
                css_path = os.path.basename(container.copy_file_to_container(hyphenation_css, name='kte-css/hyphenation.css'))
                container.add_content_file_reference("kte-css/{0}".format(css_path))

            # Override content file language
            if opts.extra_customization[self.OPT_REPLACE_LANG] and metadata.language != NULL_VALUES["language"]:
                # First override for the OPF file
                lang_node = container.opf_xpath('//opf:metadata/dc:language')
                if len(lang_node) > 0:
                    debug_print("KoboTouchExtended:_modify_epub:Overriding OPF language")
                    lang_node = lang_node[0]
                    lang_node.text = metadata.language
                else:
                    debug_print("KoboTouchExtended:_modify_epub:Setting OPF language")
                    metadata_node = container.opf_xpath('//opf:metadata')[0]
                    lang_node = metadata_node.makeelement("{%s}language" % OPF_NAMESPACES['dc'])
                    lang_node.text = metadata.language
                    container.insert_into_xml(metadata_node, lang_node)
                container.dirty(container.opf_name)

                # Now override for content files
                for name in container.get_html_names():
                    debug_print("KoboTouchExtended:_modify_epub:Overriding content file language :: {0}".format(name))
                    root = container.parsed(name)
                    root.attrib["{%s}lang" % XML_NAMESPACE] = metadata.language
                    root.attrib["lang"] = metadata.language

            # Now smarten punctuation
            if opts.extra_customization[self.OPT_SMARTEN_PUNCTUATION]:
                if not opts.extra_customization[self.OPT_REPLACE_LANG] or metadata.language == NULL_VALUES['language']:
                    debug_print("KoboTouchExtended:_modify_epub:WARNING - Hyphenation is enabled but not overriding content file language. Hyphenation may use the wrong dictionary.")
                container.smarten_punctuation()
        except Exception as e:
            (exc_type, exc_obj, exc_tb) = sys.exc_info()
            while exc_tb.tb_next and 'kobotouch_extended' in exc_tb.tb_next.tb_frame.f_code.co_filename:
                exc_tb = exc_tb.tb_next
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            if not skip_failed:
                raise InvalidEPub(metadata.title, " and ".join(metadata.authors), e.message, fname=fname, lineno=exc_tb.tb_lineno)
            else:
                self.skip_renaming_files.add(metadata.uuid)
                debug_print("Failed to process {0} by {1} with error: {2} (file: {3}, lineno: {4})".format(metadata.title, " and ".join(metadata.authors), e.message, fname, exc_tb.tb_lineno))
                return super(KOBOTOUCHEXTENDED, self)._modify_epub(file, metadata, container)

        # Everything below here is part of the 'extra features' bundle
        if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
            debug_print("KoboTouchExtended:_modify_epub:Adding extended Kobo features to {0} by {1}".format(metadata.title, ' and '.join(metadata.authors)))
            try:
                # Add the Kobo span tags
                container.add_kobo_spans()

                skip_js = False
                # Check to see if there's already a kobo*.js in the ePub
                for name in container.name_path_map:
                    if self.kobo_js_re.match(name):
                        skip_js = True
                        break
                if not skip_js:
                    if os.path.isfile(self.reference_kepub):
                        reference_container = KEPubContainer(self.reference_kepub, default_log)
                        for name in reference_container.name_path_map:
                            if self.kobo_js_re.match(name):
                                jsname = container.copy_file_to_container(os.path.join(reference_container.root, name), name='kobo.js')
                                container.add_content_file_reference(jsname)
                                break
            except Exception as e:
                (exc_type, exc_obj, exc_tb) = sys.exc_info()
                while exc_tb.tb_next and 'kobotouch_extended' in exc_tb.tb_next.tb_frame.f_code.co_filename:
                    exc_tb = exc_tb.tb_next
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                if not skip_failed:
                    raise InvalidEPub(metadata.title, " and ".join(metadata.authors), e.message, fname=fname, lineno=exc_tb.tb_lineno)
                else:
                    self.skip_renaming_files.add(metadata.uuid)
                    debug_print("Failed to process {0} by {1} with error: {2} (file: {3}, lineno: {4})".format(metadata.title, " and ".join(metadata.authors), e.message, fname, exc_tb.tb_lineno))
                    return super(KOBOTOUCHEXTENDED, self)._modify_epub(file, metadata, container)
        else:
            self.skip_renaming_files.add(metadata.uuid)
        os.unlink(file)
        container.commit(file)

        dpath = opts.extra_customization[self.OPT_FILE_COPY_DIR]
        dpath = os.path.expanduser(dpath).strip()
        if dpath != "":
            dpath = self.create_upload_path(dpath, metadata, metadata.kte_calibre_name)
            debug_print("KoboTouchExtended:_modify_epub:Generated KePub file copy path: {0}".format(dpath))
            shutil.copy(file, dpath)

        return super(KOBOTOUCHEXTENDED, self)._modify_epub(file, metadata, container)

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
