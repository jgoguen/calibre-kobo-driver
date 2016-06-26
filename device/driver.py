# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=indent:ai

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
from calibre.utils.logging import default_log
from calibre_plugins.kobotouch_extended.common import plugin_minimum_calibre_version
from calibre_plugins.kobotouch_extended.common import plugin_version
from calibre_plugins.kobotouch_extended.common import modify_epub
from calibre_plugins.kobotouch_extended.container import KEPubContainer
from datetime import datetime

# Support load_translations() without forcing calibre 1.9+
try:
    load_translations()
except NameError:
    pass

EPUB_EXT = '.epub'
KEPUB_EXT = '.kepub'


class InvalidEPub(ValueError):
    def __init__(self, name, author, message, fname=None, lineno=None):
        self.name = name
        self.author = author
        self.message = message
        self.fname = fname
        self.lineno = lineno
        ValueError.__init__(
            self,
            _("Failed to parse '{book}' by '{author}' with error: '{error}' "
              "(file: {filename}, line: {lineno})").format(book=name,
                                                           author=author,
                                                           error=message,
                                                           filename=fname,
                                                           lineno=lineno))


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
    gui_name = 'Kobo Touch/Glo/Mini/Aura HD/Aura'
    author = 'Joel Goguen'
    description = _('Communicate with the Kobo Touch, Glo, Mini, Aura HD, and '
                    'Aura firmwares and enable extended Kobo ePub features.')
    configdir = os.path.join(config_dir, 'plugins')
    reference_kepub = os.path.join(configdir, 'reference.kepub.epub')
    FORMATS = ['kepub', 'epub', 'cbr', 'cbz', 'pdf', 'txt']

    minimum_calibre_version = plugin_minimum_calibre_version
    version = plugin_version

    content_types = {"main": 6, "content": 9, "toc": 899}

    EXTRA_CUSTOMIZATION_MESSAGE = KOBOTOUCH.EXTRA_CUSTOMIZATION_MESSAGE[:]
    EXTRA_CUSTOMIZATION_DEFAULT = KOBOTOUCH.EXTRA_CUSTOMIZATION_DEFAULT[:]

    skip_renaming_files = set([])
    kobo_js_re = re.compile(r'.*/?kobo.*\.js$', re.IGNORECASE)
    invalid_filename_chars_re = re.compile(r'[\/\\\?%\*:;\|\"\'><\$!]',
                                           re.IGNORECASE | re.UNICODE)

    def modifying_epub(self):
        return self.modifying_css() or self.clean_markup or \
               self.extra_features or self.replace_lang or self.skip_failed or \
               self.smarten_punctuation or self.disable_hyphenation

    @classmethod
    def settings(cls):
        opts = super(KOBOTOUCHEXTENDED, cls).settings()
        debug_print("KoboTouchExtended:settings: settings=", opts)
        # Make sure that each option is actually the right type
        for idx in range(0, len(cls.EXTRA_CUSTOMIZATION_DEFAULT)):
            if not isinstance(opts.extra_customization[idx],
                              type(cls.EXTRA_CUSTOMIZATION_DEFAULT[idx])):
                opts.extra_customization[
                    idx] = cls.EXTRA_CUSTOMIZATION_DEFAULT[idx]
        return opts

    @classmethod
    def config_widget(cls):
        from calibre.gui2.device_drivers.configwidget import ConfigWidget

        cw = super(KOBOTOUCHEXTENDED, cls).config_widget()
        if isinstance(cw, ConfigWidget):
            debug_print(
                "KoboTouchExtended:config_widget: Have old style configuration.")
            try:
                from PyQt5.QtCore import QCoreApplication
                from PyQt5.QtWidgets import QScrollArea
            except ImportError:
                from PyQt4.Qt import QCoreApplication
                from PyQt4.Qt import QScrollArea
            qsa = QScrollArea()
            qsa.setWidgetResizable(True)
            qsa.setWidget(cw)
            qsa.validate = cw.validate
            desktop_geom = QCoreApplication.instance().desktop(
            ).availableGeometry()
            if desktop_geom.height() < 800:
                qsa.setBaseSize(qsa.size().width(),
                                desktop_geom.height() - 100)
            cw = qsa
        else:
            debug_print(
                "KoboTouchExtended:config_widget: Have new style configuration.")
            cls.current_friendly_name = cls.gui_name

            from calibre_plugins.kobotouch_extended.device.koboextended_config import KOBOTOUCHEXTENDEDConfig
            cw = KOBOTOUCHEXTENDEDConfig(
                cls.settings(),
                cls.FORMATS,
                cls.SUPPORTS_SUB_DIRS,
                cls.MUST_READ_METADATA,
                cls.SUPPORTS_USE_AUTHOR_SORT,
                cls.EXTRA_CUSTOMIZATION_MESSAGE,
                cls,
                extra_customization_choices=cls.EXTRA_CUSTOMIZATION_CHOICES)
        return cw

    @classmethod
    def save_settings(cls, config_widget):
        try:
            config_widget = config_widget.widget()
            debug_print(
                "KoboTouchExtended:save_settings: Have old style configuration.")
        except:
            debug_print(
                "KoboTouchExtended:save_settings: Have new style configuration.")

        super(KOBOTOUCHEXTENDED, cls).save_settings(config_widget)

    def _modify_epub(self, infile, metadata, container=None):
        if not infile.endswith(EPUB_EXT):
            if not infile.endswith(KEPUB_EXT):
                self.skip_renaming_files.add(metadata.uuid)
            else:
                debug_print("KoboTouchExtended:_modify_epub:Skipping all "
                            "processing for calibre-converted KePub file "
                            "{0}".format(infile))
            return super(KOBOTOUCHEXTENDED, self)._modify_epub(
                infile, metadata, container)

        debug_print("KoboTouchExtended:_modify_epub:Adding basic Kobo "
                    "features to {0} by {1}".format(
                        metadata.title, ' and '.join(metadata.authors)))

        opts = self.settings()
        skip_failed = self.skip_failed
        if skip_failed:
            debug_print("KoboTouchExtended:_modify_epub:Failed conversions "
                        "will be skipped")
        else:
            debug_print("KoboTouchExtended:_modify_epub:Failed conversions "
                        "will raise exceptions")

        if container is None:
            container = KEPubContainer(infile, default_log)

        try:
            if container.is_drm_encumbered:
                debug_print(
                    "KoboTouchExtended:_modify_epub:ERROR: ePub is DRM-encumbered, not modifying")
                self.skip_renaming_files.add(metadata.uuid)
                if self.upload_encumbered:
                    return super(KOBOTOUCHEXTENDED, self)._modify_epub(
                        infile, metadata, container)
                else:
                    return False

            # Add the conversion info file
            calibre_details_file = self.normalize_path(os.path.join(
                self._main_prefix, 'driveinfo.calibre'))
            debug_print(
                "KoboTouchExtended:_modify_epub:Calibre details file :: {0}".format(
                    calibre_details_file))
            o = {}
            if os.path.isfile:
                f = open(calibre_details_file, 'rb')
                o = json.loads(f.read())
                f.close()
                for prop in ('device_store_uuid', 'prefix',
                             'last_library_uuid', 'location_code'):
                    del (o[prop])
            else:
                debug_print(
                    "KoboTouchExtended:_modify_file:Calibre details file does not exist!")
            o['kobotouchextended_version'] = ".".join([str(n)
                                                       for n in self.version])
            o['kobotouchextended_options'] = str(opts.extra_customization)
            o['kobotouchextended_currenttime'] = datetime.utcnow().ctime()
            kte_data_file = self.temporary_file('_KoboTouchExtendedDriverInfo')
            debug_print(
                "KoboTouchExtended:_modify_epub:Driver data file :: {0}".format(
                    kte_data_file.name))
            kte_data_file.write(json.dumps(o))
            kte_data_file.close()
            container.copy_file_to_container(kte_data_file.name,
                                             name='driverinfo.kte',
                                             mt='application/json')

            modify_epub(container,
                        infile,
                        metadata=metadata,
                        opts={
                            'clean_markup': self.clean_markup,
                            'hyphenate': self.skip_failed and
                            not self.disable_hyphenation,
                            'no-hyphens': self.disable_hyphenation,
                            'replace_lang': self.replace_lang,
                            'smarten_punctuation': self.smarten_punctuation,
                            'extended_kepub_features': self.extra_features
                        })
        except Exception as e:
            exc_tb = sys.exc_info()[2]
            while exc_tb.tb_next and 'kobotouch_extended' in exc_tb.tb_next.tb_frame.f_code.co_filename:
                exc_tb = exc_tb.tb_next
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            if not skip_failed:
                raise InvalidEPub(metadata.title,
                                  " and ".join(metadata.authors),
                                  e.message,
                                  fname=fname,
                                  lineno=exc_tb.tb_lineno)
            else:
                self.skip_renaming_files.add(metadata.uuid)
                debug_print(
                    "Failed to process {0} by {1} with error: {2} (file: {3}, lineno: {4})".format(
                        metadata.title, " and ".join(metadata.authors),
                        e.message, fname, exc_tb.tb_lineno))
                return super(KOBOTOUCHEXTENDED, self)._modify_epub(
                    infile, metadata, container)

        if not self.extra_features:
            self.skip_renaming_files.add(metadata.uuid)

        dpath = self.file_copy_dir
        dpath = os.path.expanduser(dpath).strip()
        if dpath != "":
            dpath = self.create_upload_path(dpath, metadata,
                                            metadata.kte_calibre_name)
            debug_print(
                "KoboTouchExtended:_modify_epub:Generated KePub file copy path: {0}".format(
                    dpath))
            shutil.copy(infile, dpath)

        retval = super(KOBOTOUCHEXTENDED, self)._modify_epub(infile, metadata,
                                                             container)
        if retval:
            container.commit(outpath=infile)
        return retval

    def upload_books(self,
                     files,
                     names,
                     on_card=None,
                     end_session=True,
                     metadata=None):
        if self.modifying_css():
            debug_print(
                "KoboTouchExtended:upload_books:Searching for device-specific CSS file")
            device_css_file_name = self.KOBO_EXTRA_CSSFILE
            try:
                if self.isAuraH2O():
                    device_css_file_name = 'kobo_extra_AURAH2O.css'
                elif self.isAuraHD():
                    device_css_file_name = 'kobo_extra_AURAHD.css'
                elif self.isAura():
                    device_css_file_name = 'kobo_extra_AURA.css'
                elif self.isGlo():
                    device_css_file_name = 'kobo_extra_GLO.css'
                elif self.isGloHD():
                    device_css_file_name = 'kobo_extra_GLOHD.css'
                elif self.isMini():
                    device_css_file_name = 'kobo_extra_MINI.css'
                elif self.isTouch():
                    device_css_file_name = 'kobo_extra_TOUCH.css'
            except AttributeError:
                debug_print(
                    "KoboTouchExtended:upload_books:Calibre version too old to handle some specific devices, falling back to generic file {0}".format(
                        device_css_file_name))
            device_css_file_name = os.path.join(self.configdir,
                                                device_css_file_name)
            if os.path.isfile(device_css_file_name):
                debug_print(
                    "KoboTouchExtended:upload_books:Found device-specific file {0}".format(
                        device_css_file_name))
                shutil.copy(device_css_file_name,
                            os.path.join(self._main_prefix,
                                         self.KOBO_EXTRA_CSSFILE))
            else:
                debug_print(
                    "KoboTouchExtended:upload_books:No device-specific CSS file found (expecting {0})".format(
                        device_css_file_name))

        kobo_config_file = os.path.join(self._main_prefix, '.kobo', 'Kobo',
                                        'Kobo eReader.conf')
        if os.path.isfile(kobo_config_file):
            cfg = SafeConfigParser(allow_no_value=True)
            cfg.optionxform = str
            cfg.read(kobo_config_file)

            if not cfg.has_section("FeatureSettings"):
                cfg.add_section("FeatureSettings")
            debug_print(
                "KoboTouchExtended:upload_books:Setting FeatureSettings.FullBookPageNumbers to {0}".format(
                    "true" if self.full_page_numbers else "false"))
            cfg.set("FeatureSettings", "FullBookPageNumbers", "true" if
                    self.full_page_numbers else "false")
            with open(kobo_config_file, 'wb') as cfgfile:
                cfg.write(cfgfile)

        return super(KOBOTOUCHEXTENDED, self).upload_books(
            files, names, on_card, end_session, metadata)

    def filename_callback(self, path, mi):
        if self.extra_features:
            debug_print(
                "KoboTouchExtended:filename_callback:Path - {0}".format(path))
            if path.endswith(KEPUB_EXT):
                path += EPUB_EXT
            elif path.endswith(
                    EPUB_EXT) and mi.uuid not in self.skip_renaming_files:
                path = path[:-len(EPUB_EXT)] + KEPUB_EXT + EPUB_EXT

            debug_print(
                "KoboTouchExtended:filename_callback:New path - {0}".format(
                    path))
        return path

    def sanitize_path_components(self, components):
        return [self.invalid_filename_chars_re.sub('_', x) for x in components]

    def sync_booklists(self, booklists, end_session=True):
        if self.upload_covers:
            debug_print(
                "KoboTouchExtended:sync_booklists:Setting ImageId fields")

            select_query = "SELECT ContentId FROM content WHERE ContentType = ? AND (ImageId IS NULL OR ImageId = '')"
            update_query = "UPDATE content SET ImageId = ? WHERE ContentId = ?"
            db = sqlite.connect(
                os.path.join(self._main_prefix, ".kobo", "KoboReader.sqlite"),
                isolation_level=None)
            db.text_factory = lambda x: unicode(x, "utf-8", "ignore")

            def __rows_needing_imageid():
                """Returns a dict object with keys being the ContentID of a row without an ImageID.
                """
                c = db.cursor()
                d = {}
                c.execute(select_query, (self.content_types['main'], ))
                for row in c:
                    d[row[0]] = 1
                return d

            all_nulls = __rows_needing_imageid()
            debug_print(
                "KoboTouchExtended:sync_booklists:Got {0} rows to update".format(
                    str(len(all_nulls.keys()))))
            nulls = []
            for booklist in booklists:
                for b in booklist:
                    if b.application_id is not None and b.contentID in all_nulls:
                        nulls.append((self.imageid_from_contentid(b.contentID),
                                      b.contentID))
            del (all_nulls)

            cursor = db.cursor()
            while nulls[:100]:
                debug_print(
                    "KoboTouchExtended:sync_booklists:Updating {0} ImageIDs...".format(
                        str(len(nulls[:100]))))
                cursor.executemany(update_query, nulls[:100])
                db.commit()
                del (nulls[:100])
            cursor.close()
            db.close()
            debug_print(
                "KoboTouchExtended:sync_booklists:done setting ImageId fields")

        super(KOBOTOUCHEXTENDED, self).sync_booklists(booklists, end_session)

    @classmethod
    def _config(cls):
        c = super(KOBOTOUCHEXTENDED, cls)._config()

        c.add_opt('extra_features', default=True)
        c.add_opt('upload_encumbered', default=False)
        c.add_opt('skip_failed', default=False)
        c.add_opt('hyphenate', default=False)
        c.add_opt('replace_lang', default=False)
        c.add_opt('smarten_punctuation', default=False)
        c.add_opt('clean_markup', default=False)
        c.add_opt('full_page_numbers', default=False)
        c.add_opt('disable_hyphenation', default=False)
        c.add_opt('file_copy_dir', default='')

        return c

    @classmethod
    def migrate_old_settings(cls, settings):
        debug_print("KoboTouchExtended::migrate_old_settings - start")
        settings = super(KOBOTOUCHEXTENDED, cls).migrate_old_settings(settings)

        count_options = 0
        OPT_EXTRA_FEATURES = count_options
        count_options += 1
        OPT_UPLOAD_ENCUMBERED = count_options
        count_options += 1
        OPT_SKIP_FAILED = count_options
        count_options += 1
        OPT_HYPHENATE = count_options
        count_options += 1
        OPT_REPLACE_LANG = count_options
        count_options += 1
        OPT_SMARTEN_PUNCTUATION = count_options
        count_options += 1
        OPT_CLEAN_MARKUP = count_options
        count_options += 1
        OPT_FILE_COPY_DIR = count_options
        count_options += 1
        OPT_FULL_PAGE_NUMBERS = count_options
        count_options += 1
        OPT_DISABLE_HYPHENATION = count_options

        if len(settings.extra_customization) >= count_options:
            debug_print(
                "KoboTouchExtended::migrate_old_settings - settings need to be migrated")
            try:
                settings.extra_features = settings.extra_customization[
                    OPT_EXTRA_FEATURES]
            except IndexError:
                pass
            try:
                settings.upload_encumbered = settings.extra_customization[
                    OPT_UPLOAD_ENCUMBERED]
            except IndexError:
                pass
            try:
                settings.skip_failed = settings.extra_customization[
                    OPT_SKIP_FAILED]
            except IndexError:
                pass
            try:
                settings.hyphenate = settings.extra_customization[
                    OPT_HYPHENATE]
            except IndexError:
                pass
            try:
                settings.replace_lang = settings.extra_customization[
                    OPT_REPLACE_LANG]
            except IndexError:
                pass
            try:
                settings.smarten_punctuation = settings.extra_customization[
                    OPT_SMARTEN_PUNCTUATION]
            except IndexError:
                pass
            try:
                settings.clean_markup = settings.extra_customization[
                    OPT_CLEAN_MARKUP]
            except IndexError:
                pass
            try:
                settings.file_copy_dir = settings.extra_customization[
                    OPT_FILE_COPY_DIR]
            except IndexError:
                pass
            try:
                settings.full_page_numbers = settings.extra_customization[
                    OPT_FULL_PAGE_NUMBERS]
            except IndexError:
                pass
            try:
                settings.disable_hyphenation = settings.extra_customization[
                    OPT_DISABLE_HYPHENATION]
            except IndexError:
                pass

        return settings

    @property
    def extra_features(self):
        return self.get_pref('extra_features')

    @property
    def upload_encumbered(self):
        return self.get_pref('upload_encumbered')

    @property
    def skip_failed(self):
        return self.get_pref('skip_failed')

    @property
    def hyphenate(self):
        return self.get_pref('hyphenate')

    @property
    def replace_lang(self):
        return self.get_pref('replace_lang')

    @property
    def smarten_punctuation(self):
        return self.get_pref('smarten_punctuation')

    @property
    def clean_markup(self):
        return self.get_pref('clean_markup')

    @property
    def full_page_numbers(self):
        return self.get_pref('full_page_numbers')

    @property
    def disable_hyphenation(self):
        return self.get_pref('disable_hyphenation')

    @property
    def file_copy_dir(self):
        return self.get_pref('file_copy_dir')
