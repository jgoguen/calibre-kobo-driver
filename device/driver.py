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

from ConfigParser import SafeConfigParser
from calibre.constants import config_dir
from calibre.devices.kobo.driver import KOBOTOUCH
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.logging import default_log
from calibre_plugins.kobotouch_extended.common import plugin_minimum_calibre_version
from calibre_plugins.kobotouch_extended.common import plugin_version
from calibre_plugins.kobotouch_extended.common import modify_epub
from calibre_plugins.kobotouch_extended.common import uuid_from_metadata
from calibre_plugins.kobotouch_extended.container import KEPubContainer
from contextlib import closing
from datetime import datetime


# Support load_translations() without forcing calibre 1.9+
try:
    load_translations()
except NameError:
    pass

EPUB_EXT = '.epub'
KEPUB_EXT = '.kepub'
XML_NAMESPACE = 'http://www.w3.org/XML/1998/namespace'


class InvalidEPub(ValueError):

    def __init__(self, name, author, message, fname=None, lineno=None):
        self.name = name
        self.author = author
        self.message = message
        self.fname = fname
        self.lineno = lineno
        ValueError.__init__(self, _("Failed to parse '{book}' by '{author}' with error: '{error}' (file: {filename}, line: {lineno})").format(book=name, author=author, error=message, filename=fname, lineno=lineno))


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
    description = _('Communicate with the Kobo Touch, Glo, and Mini firmwares and enable extended Kobo ePub features.')
    configdir = os.path.join(config_dir, 'plugins')
    reference_kepub = os.path.join(configdir, 'reference.kepub.epub')
    FORMATS = ['kepub', 'epub', 'cbr', 'cbz', 'pdf', 'txt']

    minimum_calibre_version = plugin_minimum_calibre_version
    version = plugin_version

    content_types = {
        "main": 6,
        "content": 9,
        "toc": 899
    }

    supported_dbversion = 89
    min_supported_dbversion = 65
    max_supported_fwversion = (2, 10, 0)
    min_fwversion_tiles = (2, 6, 1)
    min_dbversion_stats = 88

    kobo_epub_mime_type = "application/x-kobo-epub+zip"
    xhtml_mime_type = "application/xhtml+xml"
    opf_mime_type = 'application/oebps-package+xml'
    opf_ns = "http://www.idpf.org/2007/opf"
    container_ns = "urn:oasis:names:tc:opendocument:xmlns:container"
    ncx_mime_type = "application/x-dtbncx+xml"
    ncx_ns = "http://www.daisy.org/z3986/2005/ncx/"
    dc_ns = "http://purl.org/dc/elements/1.1/"

    EXTRA_CUSTOMIZATION_MESSAGE = KOBOTOUCH.EXTRA_CUSTOMIZATION_MESSAGE[:]
    EXTRA_CUSTOMIZATION_DEFAULT = KOBOTOUCH.EXTRA_CUSTOMIZATION_DEFAULT[:]

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Enable Extended Kobo Features') + ':::' + _('Choose whether to enable extra customizations'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(True)
    OPT_EXTRA_FEATURES = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Upload DRM-encumbered ePub files') + ':::' + _('Select this to upload ePub files encumbered by DRM. If this is not selected, it is a fatal error to upload an encumbered file'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_UPLOAD_ENCUMBERED = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Silently Ignore Failed Conversions') + ':::' + _('Select this to not upload any book that fails conversion to kepub. If this is not selected, the upload process will be stopped at the first book that fails. If this is selected, failed books will be silently removed from the upload queue.'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_SKIP_FAILED = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Hyphenate Files') + ':::' + _('Select this to add a CSS file which enables hyphenation. The language used will be the language defined for the book in calibre. Please see the README file for directions on adding/updating hyphenation dictionaries.'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_HYPHENATE = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Replace Content Language Code') + ':::' + _('Select this to replace the defined language in each content file inside the ePub.'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_REPLACE_LANG = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Smarten Punctuation') + ':::' + _('Select this to smarten punctuation in the ePub'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_SMARTEN_PUNCTUATION = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Clean up ePub Markup') + ':::' + _('Select this to clean up the internal ePub markup.'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_CLEAN_MARKUP = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Copy generated KePub files to a directory') + ':::' + _('Enter an absolute directory path to copy all generated KePub files into for debugging purposes.'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(u'')
    OPT_FILE_COPY_DIR = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Use full book page numbers') + ':::' + _('Select this to show page numbers for the whole book, instead of each chapter. This will also affect regular ePub page number display!'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_FULL_PAGE_NUMBERS = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    EXTRA_CUSTOMIZATION_MESSAGE.append(_('Display reading statistics') + ':::' + _('Display KePub reading statistics. This will cause the file name template to be ignored and all books sent to .kobo/kepub/ with a UUID-based name!'))
    EXTRA_CUSTOMIZATION_DEFAULT.append(False)
    OPT_READING_STATS = len(EXTRA_CUSTOMIZATION_MESSAGE) - 1

    skip_renaming_files = set([])
    kobo_js_re = re.compile(r'.*/?kobo.*\.js$', re.IGNORECASE)
    invalid_filename_chars_re = re.compile(r'[\/\\\?%\*:;\|\"\'><\$!]', re.IGNORECASE | re.UNICODE)

    def modifying_epub(self):
        opts = self.settings().extra_customization
        return self.modifying_css() or opts[self.OPT_CLEAN_MARKUP] or \
            opts[self.OPT_EXTRA_FEATURES] or opts[self.OPT_REPLACE_LANG] \
            or opts[self.OPT_HYPHENATE] or opts[self.OPT_SMARTEN_PUNCTUATION]

    @classmethod
    def settings(cls):
        opts = super(KOBOTOUCHEXTENDED, cls).settings()
        # Make sure that each option is actually the right type
        for idx in range(0, len(cls.EXTRA_CUSTOMIZATION_DEFAULT)):
            if not isinstance(opts.extra_customization[idx], type(cls.EXTRA_CUSTOMIZATION_DEFAULT[idx])):
                opts.extra_customization[idx] = cls.EXTRA_CUSTOMIZATION_DEFAULT[idx]
        return opts

    @classmethod
    def config_widget(cls):
        from PyQt4.Qt import QCoreApplication
        from PyQt4.Qt import QScrollArea

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
    def save_template(cls):
        opts = super(KOBOTOUCHEXTENDED, cls).settings()
        print("DBVersion: " + str(cls.dbversion))
        print("Min DBVersion: " + str(cls.min_dbversion_stats))
        if cls.dbversion >= cls.min_dbversion_stats and opts.extra_customization[cls.OPT_READING_STATS] and opts.extra_customization[cls.OPT_EXTRA_FEATURES]:
            return ".kobo/kepub/{title_sort}"
        else:
            return super(KOBOTOUCHEXTENDED, cls).save_template()

    @classmethod
    def save_settings(cls, config_widget):
        super(KOBOTOUCHEXTENDED, cls).save_settings(config_widget.widget())

    def create_upload_path(self, path, mdata, fname, create_dirs=True):
        upload_path = super(KOBOTOUCHEXTENDED, self).create_upload_path(path, mdata, fname, create_dirs)
        if self.enable_stats:
            upload_path = re.sub(r'_kobo', '.kobo', upload_path)
            debug_print("KoboTouchExtended:create_upload_path:New upload path - {0}".format(upload_path))
        return upload_path

    @property
    def enable_stats(self):
        opts = self.settings()
        return self.dbversion >= self.min_dbversion_stats and opts.extra_customization[self.OPT_READING_STATS] and opts.extra_customization[self.OPT_EXTRA_FEATURES]

    def _modify_epub(self, infile, metadata, container=None):
        if not infile.endswith(EPUB_EXT):
            if not infile.endswith(KEPUB_EXT):
                self.skip_renaming_files.add(metadata.uuid)
            else:
                debug_print("KoboTouchExtended:_modify_epub:Skipping all processing for calibre-converted KePub file {0}".format(infile))
            return super(KOBOTOUCHEXTENDED, self)._modify_epub(infile, metadata, container)

        debug_print("KoboTouchExtended:_modify_epub:Adding basic Kobo features to {0} by {1}".format(metadata.title, ' and '.join(metadata.authors)))

        opts = self.settings()
        skip_failed = opts.extra_customization[self.OPT_SKIP_FAILED]
        if skip_failed:
            debug_print("KoboTouchExtended:_modify_epub:Failed conversions will be skipped")
        else:
            debug_print("KoboTouchExtended:_modify_epub:Failed conversions will raise exceptions")

        if container is None:
            container = KEPubContainer(infile, default_log)

        try:
            if container.is_drm_encumbered:
                debug_print("KoboTouchExtended:_modify_epub:ERROR: ePub is DRM-encumbered, not modifying")
                self.skip_renaming_files.add(metadata.uuid)
                if opts.extra_customization[self.OPT_UPLOAD_ENCUMBERED]:
                    return super(KOBOTOUCHEXTENDED, self)._modify_epub(infile, metadata, container)
                else:
                    return False

            # Add the conversion info file
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
            kte_data_file = self.temporary_file('_KoboTouchExtendedDriverInfo')
            debug_print("KoboTouchExtended:_modify_epub:Driver data file :: {0}".format(kte_data_file.name))
            kte_data_file.write(json.dumps(o))
            kte_data_file.close()
            container.copy_file_to_container(kte_data_file.name, name='driverinfo.kte', mt='application/json')

            modify_epub(container, infile, metadata=metadata, opts={
                'clean_markup': opts.extra_customization[self.OPT_CLEAN_MARKUP],
                'hyphenate': opts.extra_customization[self.OPT_HYPHENATE],
                'replace_lang': opts.extra_customization[self.OPT_REPLACE_LANG],
                'smarten_punctuation': opts.extra_customization[self.OPT_SMARTEN_PUNCTUATION],
                'extended_kepub_features': opts.extra_customization[self.OPT_EXTRA_FEATURES]
            })
        except Exception as e:
            exc_tb = sys.exc_info()[2]
            while exc_tb.tb_next and 'kobotouch_extended' in exc_tb.tb_next.tb_frame.f_code.co_filename:
                exc_tb = exc_tb.tb_next
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            if not skip_failed:
                raise InvalidEPub(metadata.title, " and ".join(metadata.authors), e.message, fname=fname, lineno=exc_tb.tb_lineno)
            else:
                self.skip_renaming_files.add(metadata.uuid)
                debug_print("Failed to process {0} by {1} with error: {2} (file: {3}, lineno: {4})".format(metadata.title, " and ".join(metadata.authors), e.message, fname, exc_tb.tb_lineno))
                return super(KOBOTOUCHEXTENDED, self)._modify_epub(infile, metadata, container)

        if not opts.extra_customization[self.OPT_EXTRA_FEATURES]:
            self.skip_renaming_files.add(metadata.uuid)

        dpath = opts.extra_customization[self.OPT_FILE_COPY_DIR]
        dpath = os.path.expanduser(dpath).strip()
        if dpath != "":
            dpath = self.create_upload_path(dpath, metadata, metadata.kte_calibre_name)
            debug_print("KoboTouchExtended:_modify_epub:Generated KePub file copy path: {0}".format(dpath))
            shutil.copy(infile, dpath)

        retval = super(KOBOTOUCHEXTENDED, self)._modify_epub(infile, metadata, container)
        if retval:
            container.commit(outpath=infile)
        return retval

    def upload_books(self, files, names, on_card=None, end_session=True, metadata=None):
        opts = self.settings()
        if opts.extra_customization[self.OPT_MODIFY_CSS]:
            debug_print("KoboTouchExtended:upload_books:Searching for device-specific CSS file")
            device_css_file_name = self.KOBO_EXTRA_CSSFILE
            if self.isAuraHD():
                device_css_file_name = 'kobo_extra_AURAHD.css'
            elif self.isAura():
                device_css_file_name = 'kobo_extra_AURA.css'
            elif self.isGlo():
                device_css_file_name = 'kobo_extra_GLO.css'
            elif self.isMini():
                device_css_file_name = 'kobo_extra_MINI.css'
            elif self.isTouch():
                device_css_file_name = 'kobo_extra_TOUCH.css'
            device_css_file_name = os.path.join(self.configdir, device_css_file_name)
            if os.path.isfile(device_css_file_name):
                debug_print("KoboTouchExtended:upload_books:Found device-specific file {0}".format(device_css_file_name))
                shutil.copy(device_css_file_name, os.path.join(self._main_prefix, self.KOBO_EXTRA_CSSFILE))
            else:
                debug_print("KoboTouchExtended:upload_books:No device-specific CSS file found (expecting {0})".format(device_css_file_name))

        kobo_config_file = os.path.join(self._main_prefix, '.kobo', 'Kobo', 'Kobo eReader.conf')
        if os.path.isfile(kobo_config_file):
            cfg = SafeConfigParser(allow_no_value=True)
            cfg.optionxform = str
            cfg.read(kobo_config_file)
            if not cfg.has_section("FeatureSettings"):
                cfg.add_section("FeatureSettings")
            debug_print("KoboTouchExtended:upload_books:Setting FeatureSettings.FullBookPageNumbers to {0}".format("true" if opts.extra_customization[self.OPT_FULL_PAGE_NUMBERS] else "false"))
            cfg.set("FeatureSettings", "FullBookPageNumbers", "true" if opts.extra_customization[self.OPT_FULL_PAGE_NUMBERS] else "false")
            with open(kobo_config_file, 'wb') as cfgfile:
                cfg.write(cfgfile)

        if self.enable_stats:
            with closing(sqlite.connect(self.device_database_path())) as connection:
                connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

                with closing(connection.cursor()) as cursor:
                    userid = 'kepub_user'
                    cursor.execute("SELECT UserID FROM user WHERE ___DeviceID IS NULL")
                    row = cursor.fetchone()
                    do_series = opts.extra_customization[self.OPT_UPDATE_SERIES_DETAILS] and self.supports_series()
                    if row is not None and len(row) > 0:
                        userid = row[0]
                    debug_print("KoboTouchExtended:upload_books:KePub user - {0}".format(userid))

                    add_content_query = "INSERT INTO content(ContentID, ContentType, MimeType, BookID, BookTitle, ImageId, Title, Attribution, Description, DateCreated, ShortCoverKey, adobe_location, Publisher, IsEncrypted, DateLastRead, FirstTimeReading, ChapterIDBookmarked, ParagraphBookmarked, BookmarkWordOffset, NumShortcovers, VolumeIndex, ___NumPages, ReadStatus, ___SyncTime, ___UserID, PublicationId, ___FileOffset, ___FileSize, ___PercentRead, ___ExpirationStatus, FavouritesIndex, Accessibility, ContentURL, Language, BookshelfTags, IsDownloaded, FeedbackType, AverageRating, Depth, PageProgressDirection, InWishlist, ISBN, WishlistedDate, FeedbackTypeSynced, IsSocialEnabled, EpubType, Monetization, ExternalId, Series, SeriesNumber, Subtitle, WordCount, Fallback, RestOfBookEstimate, CurrentChapterEstimate, CurrentChapterProgress, PocketStatus, UnsyncedPocketChanges, ImageUrl, DateAdded, WorkId) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    add_shortcover_query = "INSERT INTO volume_shortcovers (volumeId, shortcoverId, VolumeIndex) VALUES (?, ?, ?)"
                    add_activity_query = "INSERT INTO Activity (Id, Enabled, Type, Action, Date, Data) VALUES (?, 'true', ?, 2, ?, ?)"

                    try:
                        for fpath, name, mi in zip(files, names, metadata):
                            contentid = uuid_from_metadata(mi)
                            debug_print("KoboTouchExtended:upload_books:Content ID for {title} - {contentid}".format(title=mi.title, contentid=contentid))
                            container = KEPubContainer(fpath, default_log)
                            current_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

                            lang = container.opf_xpath('./opf:metadata/dc:language/text()')
                            if len(lang) > 0:
                                lang = lang[0]
                            else:
                                lang = ''

                            opf_path_prefix = ''
                            idx = container.opf_name.rfind('/')
                            if idx > -1:
                                opf_path_prefix = container.opf_name[:idx + 1]

                            content_id_to_href_map = {}
                            ncx_path = None
                            for node in container.opf_xpath('./opf:manifest/opf:item[@id and @href]'):
                                content_id_to_href_map[node.attrib["id"]] = "{0}{1}".format(opf_path_prefix, node.attrib["href"])
                                if node.attrib["media-type"] == self.ncx_mime_type:
                                    ncx_path = "{0}{1}".format(opf_path_prefix, node.attrib["href"])

                            num_rows = 0
                            for id in container.opf_xpath('./opf:spine[@toc="ncx"]/opf:itemref[@idref]/@idref'):
                                # Add general content entries
                                t = ("{contentid}!{prefix}!{name}".format(contentid=contentid, prefix=opf_path_prefix[:-1], name=content_id_to_href_map[id]), self.content_types["content"], self.xhtml_mime_type, contentid, mi.title, None, content_id_to_href_map[id],
                                     '', None, None, None, None, None, 'false',
                                     None, 'true', None, 0, 0, None, num_rows,
                                     42, 0, None, userid, None, 0, 0,
                                     0, None, -1, -1, None, None, None,
                                     1, 0, 0, 0, None, 'false', None,
                                     None, 0, 'true', -1, 2, None, None,
                                     None, None, -1, None, None, None, None,
                                     0, '7B20207D', None, None, '')
                                cursor.execute(add_content_query, t)
                                num_rows += 1

                            # Add TOC entries
                            if ncx_path is not None:
                                ncx = container.parsed(ncx_path)
                                hrefs = ncx.xpath('./ncx:navMap/ncx:navPoint/ncx:content[@src]/@src', namespaces={"ncx": self.ncx_ns})
                                titles = ncx.xpath('./ncx:navMap/ncx:navPoint/ncx:navLabel/ncx:text/text()', namespaces={"ncx": self.ncx_ns})
                                for idx in range(len(hrefs)):
                                    t = ("{contentid}!{prefix}!{name}-1".format(contentid=contentid, prefix=opf_path_prefix[:-1], name=hrefs[idx]), self.content_types["toc"], self.kobo_epub_mime_type, contentid, mi.title, None, titles[idx],
                                         '', None, None, None, None, None, 'false',
                                         None, 'true', "{contentid}!{prefix}!{name}".format(contentid=contentid, prefix=opf_path_prefix[:-1], name=hrefs[idx]), 0, 0, None, idx,
                                         42, 0, None, userid, None, 0, 0,
                                         0, None, -1, -1, None, None, None,
                                         1, 0, 0, 1, None, 'false', None,
                                         None, 0, 'true', -1, 2, None, None,
                                         None, None, -1, None, None, None, None,
                                         0, '7B20207D', None, None, '')
                                    cursor.execute(add_content_query, t)

                                # Create the volume shortcover entries
                                t = (contentid, "{contentid}!{prefix}!{name}".format(contentid=contentid, prefix=opf_path_prefix[:-1], name=content_id_to_href_map[id]), num_rows)
                                cursor.execute(add_shortcover_query, t)

                            # Add the main KePub entry
                            t = (contentid, self.content_types["main"], self.kobo_epub_mime_type, None, None, contentid, mi.title,
                                 authors_to_string(mi.authors).split(' & ')[0].strip(), mi.comments, current_date + ".000", None, contentid, mi.publisher, 'true',
                                 current_date + "Z", 'true', None, 1, 0, num_rows, 0,
                                 0, 0, current_date + "Z", userid, None, None, os.path.getsize(fpath),
                                 0, 0, -1, 1, '', lang, '',
                                 'true', 0, 0, 0, None, 'false', mi.isbn,
                                 None, 0, 'true', 1, 0, '', mi.series if do_series else None,
                                 mi.format_series_index() if do_series else None, None, -1, None, 0, 0, 0.0,
                                 0, '7B20207D', None, current_date + ".000Z", '')
                            cursor.execute(add_content_query, t)

                            # Create the Activity entry
                            t = (contentid, 'RecentBook', current_date, b'00000000')
                            cursor.execute(add_activity_query, t)

                        cursor.close()
                        connection.commit()
                    except Exception as e:
                        debug_print("KoboTouchExtended:upload_books:Exception while adding database entries - {0}".format(str(e)))
                        try:
                            connection.rollback()
                        except:
                            pass
                        raise

        return super(KOBOTOUCHEXTENDED, self).upload_books(files, names, on_card, end_session, metadata)

    def filename_callback(self, path, mi):
        opts = self.settings()
        if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
            debug_print("KoboTouchExtended:filename_callback:Path - {0}".format(path))

            idx = path.rfind('.')
            ext = path[idx:]
            if ext == KEPUB_EXT or (ext == EPUB_EXT and mi.uuid not in self.skip_renaming_files):
                path = "{0}.kepub{1}".format(path[:idx], EPUB_EXT)
                debug_print("KoboTouchExtended:filename_callback:New path - {0}".format(path))

        return path

    def sanitize_path_components(self, components):
        return [self.invalid_filename_chars_re.sub('_', x) for x in components]

    def create_upload_path(self, path, mdata, fname, create_dirs=True):
        debug_print("KoboTouchExtended:create_upload_path:(path={0})(fname={1})".format(path, fname))
        opts = self.settings()
        if self.dbversion > self.min_dbversion_stats and opts.extra_customization[self.OPT_READING_STATS] and opts.extra_customization[self.OPT_EXTRA_FEATURES]:
            upload_path = os.path.abspath(os.path.join(self._main_prefix, '.kobo', 'kepub'))
            if not os.path.isdir(upload_path):
                os.makedirs(upload_path)
            upload_path = os.path.join(upload_path, uuid_from_metadata(mdata))
            debug_print("KoboTouchExtended:create_upload_path:Generated KePub upload path {0}".format(upload_path))
            return upload_path
        else:
            return super(KOBOTOUCHEXTENDED, self).create_upload_path(path, mdata, fname, create_dirs)

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
