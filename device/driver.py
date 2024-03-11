# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=indent:ai

"""The main driver for the KoboTouchExtended driver. Everything starts here."""

__license__ = "GPL v3"
__copyright__ = "2013, Joel Goguen <jgoguen@jgoguen.ca>"
__docformat__ = "markdown en"

import os
import re
import shutil
import sys

from calibre.constants import config_dir
from calibre.devices.kobo.driver import KOBOTOUCH
from calibre_plugins.kobotouch_extended import common
from calibre_plugins.kobotouch_extended.container import KEPubContainer
from configparser import NoOptionError, ConfigParser
from typing import List
from typing import Optional
from typing import Set
from typing import Union

load_translations()

EPUB_EXT = ".epub"
KEPUB_EXT = ".kepub"


class KOBOTOUCHEXTENDED(KOBOTOUCH):
    """Extended driver for Kobo Touch, Kobo Glo, and Kobo Mini devices.

    This driver automatically modifies ePub files to include extra information
    used by Kobo devices to enable annotations and display of chapter names and
    page numbers on a per-chapter basis. Files are also transferred using the
    'kepub' designation ({name}.kepub.{ext}) automatically to trigger the Kobo
    device to enable these features. This also enabled more detailed reading
    statistics accessible within each book.
    """

    name = "KoboTouchExtended"
    gui_name = "Kobo Touch Extended"
    author = "Joel Goguen"
    description = _(  # noqa: F821
        "Communicate with Kobo Touch and later firmwares to enable extended Kobo "
        + "ePub features."
    )
    configdir = os.path.join(config_dir, "plugins")
    reference_kepub = os.path.join(configdir, "reference.kepub.epub")
    FORMATS = ["kepub", "epub", "cbr", "cbz", "pdf", "txt"]

    minimum_calibre_version = common.PLUGIN_MINIMUM_CALIBRE_VERSION
    version = common.PLUGIN_VERSION

    content_types = {"main": 6, "content": 9, "toc": 899}

    EXTRA_CUSTOMIZATION_MESSAGE: List[str] = KOBOTOUCH.EXTRA_CUSTOMIZATION_MESSAGE[:]
    EXTRA_CUSTOMIZATION_DEFAULT: List[Union[str, bool]] = (
        KOBOTOUCH.EXTRA_CUSTOMIZATION_DEFAULT[:]
    )

    skip_renaming_files: Set[str] = set()
    kobo_js_re = re.compile(r".*/?kobo.*\.js$", re.IGNORECASE)
    invalid_filename_chars_re = re.compile(
        r"[\/\\\?%\*:;\|\"\'><\$!]", re.IGNORECASE | re.UNICODE
    )

    def modifying_epub(self) -> bool:
        """Determine if this epub will be modified."""
        return (
            self.modifying_css()
            or self.clean_markup
            or self.extra_features
            or self.skip_failed
            or self.smarten_punctuation
            or self.disable_hyphenation
            or self.hyphenate_chars > 0
        )

    @classmethod
    def settings(cls):
        """Initialize settings for the driver."""
        opts = super(KOBOTOUCHEXTENDED, cls).settings()
        common.log.debug("KoboTouchExtended:settings: settings=", opts)
        # Make sure that each option is actually the right type
        for idx in range(0, len(cls.EXTRA_CUSTOMIZATION_DEFAULT)):
            if not isinstance(
                opts.extra_customization[idx],
                type(cls.EXTRA_CUSTOMIZATION_DEFAULT[idx]),
            ):
                opts.extra_customization[idx] = cls.EXTRA_CUSTOMIZATION_DEFAULT[idx]
        return opts

    @classmethod
    def config_widget(cls):
        """Create and populate the driver settings config widget."""
        from calibre.gui2.device_drivers.configwidget import ConfigWidget

        cw = super(KOBOTOUCHEXTENDED, cls).config_widget()
        if isinstance(cw, ConfigWidget):
            common.log.warning(
                "KoboTouchExtended:config_widget: Have old style config."
            )
            from PyQt5.QtCore import QCoreApplication
            from PyQt5.QtWidgets import QScrollArea

            qsa = QScrollArea()
            qsa.setWidgetResizable(True)
            qsa.setWidget(cw)
            qsa.validate = cw.validate
            desktop_geom = QCoreApplication.instance().desktop().availableGeometry()
            if desktop_geom.height() < 800:
                qsa.setBaseSize(qsa.size().width(), desktop_geom.height() - 100)
            cw = qsa
        else:
            common.log.info("KoboTouchExtended:config_widget: Have new style config.")
            cls.current_friendly_name = cls.gui_name

            from calibre_plugins.kobotouch_extended.device.koboextended_config import (
                KOBOTOUCHEXTENDEDConfig,
            )

            cw = KOBOTOUCHEXTENDEDConfig(
                cls.settings(),
                cls.FORMATS,
                cls.SUPPORTS_SUB_DIRS,
                cls.MUST_READ_METADATA,
                cls.SUPPORTS_USE_AUTHOR_SORT,
                cls.EXTRA_CUSTOMIZATION_MESSAGE,
                cls,
                extra_customization_choices=cls.EXTRA_CUSTOMIZATION_CHOICES,
            )
        return cw

    @classmethod
    def save_settings(cls, config_widget):
        """Ensure settings are properly saved between old and new config styles."""
        try:
            config_widget = config_widget.widget()
            common.log.warning(
                "KoboTouchExtended:save_settings: Have old style config."
            )
        except Exception:
            common.log.info("KoboTouchExtended:save_settings: Have new style config.")

        super(KOBOTOUCHEXTENDED, cls).save_settings(config_widget)

    def _modify_epub(
        self, infile: str, metadata, container: Optional[KEPubContainer] = None
    ):
        if container is None:
            container = KEPubContainer(infile, common.log, do_cleanup=self.clean_markup)
        if not infile.endswith(EPUB_EXT) or not self.kepubify_book(metadata):
            if infile.endswith(KEPUB_EXT):
                common.log.info(
                    "KoboTouchExtended:_modify_epub:Skipping all processing for "
                    + f"KePub file {infile}"
                )
            return super(KOBOTOUCHEXTENDED, self)._modify_epub(
                infile, metadata, container
            )

        common.log.info(
            "KoboTouchExtended:_modify_epub:Adding basic Kobo features to "
            + f"{metadata.title} by {' and '.join(metadata.authors)}"
        )

        if self.skip_failed:
            common.log.info(
                "KoboTouchExtended:_modify_epub:Failed conversions will be skipped"
            )
        else:
            common.log.info(
                "KoboTouchExtended:_modify_epub:Failed conversions will raise "
                + "exceptions"
            )

        if container.is_drm_encumbered:
            self.skip_renaming_files.add(metadata.uuid)
            if self.upload_encumbered:
                return super(KOBOTOUCHEXTENDED, self)._modify_epub(
                    infile, metadata, container
                )
            return False

        try:
            common.modify_epub(
                container,
                infile,
                metadata=metadata,
                opts={
                    "hyphenate": self.hyphenate and not self.disable_hyphenation,
                    "hyphen_min_chars": self.hyphenate_chars,
                    "hyphen_min_chars_before": self.hyphenate_chars_before,
                    "hyphen_min_chars_after": self.hyphenate_chars_after,
                    "hyphen_limit_lines": self.hyphenate_limit_lines,
                    "no-hyphens": self.disable_hyphenation,
                    "smarten_punctuation": self.smarten_punctuation,
                    "extended_kepub_features": self.extra_features,
                },
            )
        except Exception as e:
            msg = (
                f"Failed to process {metadata.title} by "
                + f"{' and '.join(metadata.authors)}: {e}"
            )
            common.log.exception(msg)

            if not self.skip_failed:
                tb = sys.exc_info()[2]
                raise e.__class__(msg).with_traceback(tb)

            self.skip_renaming_files.add(metadata.uuid)
            return super(KOBOTOUCHEXTENDED, self)._modify_epub(
                infile, metadata, container
            )

        dpath = self.file_copy_dir or ""
        if dpath != "":
            dpath = os.path.expanduser(dpath).strip()
            dpath = self.create_upload_path(dpath, metadata, metadata.kte_calibre_name)
            common.log.info(
                "KoboTouchExtended:_modify_epub:Generated KePub file copy "
                + f"path: {dpath}"
            )
            shutil.copy(infile, dpath)

        retval = super(KOBOTOUCHEXTENDED, self)._modify_epub(
            infile, metadata, container
        )
        if retval:
            container.commit(outpath=infile)
        return retval

    def upload_books(self, files, names, on_card=None, end_session=True, metadata=None):
        """Process sending the book to the Kobo device."""
        if self.modifying_css():
            common.log.info(
                "KoboTouchExtended:upload_books:Searching for device-specific "
                + "CSS file"
            )
            device_css_file_name = self.KOBO_EXTRA_CSSFILE
            try:
                if self.isAuraH2O():
                    device_css_file_name = "kobo_extra_AURAH2O.css"
                elif self.isAuraH2OEdition2():
                    device_css_file_name = "kobo_extra_AURAH2O_2.css"
                elif self.isAuraHD():
                    device_css_file_name = "kobo_extra_AURAHD.css"
                elif self.isAura():
                    device_css_file_name = "kobo_extra_AURA.css"
                elif self.isAuraEdition2():
                    device_css_file_name = "kobo_extra_AURA_2.css"
                elif self.isAuraOne():
                    device_css_file_name = "kobo_extra_AURAONE.css"
                elif self.isClaraHD():
                    device_css_file_name = "kobo_extra_CLARA.css"
                elif self.isForma():
                    device_css_file_name = "kobo_extra_FORMA.css"
                elif self.isElipsa():
                    device_css_file_name = "kobo_extra_ELIPSA.css"
                elif self.isGlo():
                    device_css_file_name = "kobo_extra_GLO.css"
                elif self.isGloHD():
                    device_css_file_name = "kobo_extra_GLOHD.css"
                elif self.isLibraH2O():
                    device_css_file_name = "kobo_extra_LIBRA.css"
                elif self.isLibra2():
                    device_css_file_name = "kobo_extra_LIBRA_2.css"
                elif self.isNia():
                    device_css_file_name = "kobo_extra_NIA.css"
                elif self.isSage():
                    device_css_file_name = "kobo_extra_SAGE.css"
                elif self.isMini():
                    device_css_file_name = "kobo_extra_MINI.css"
                elif self.isTouch():
                    device_css_file_name = "kobo_extra_TOUCH.css"
                elif self.isTouch2():
                    device_css_file_name = "kobo_extra_TOUCH_2.css"
            except AttributeError:
                common.log.warning(
                    "KoboTouchExtended:upload_books:Calibre version too old "
                    + "to handle some specific devices, falling back to "
                    + f"generic file {device_css_file_name}"
                )
            device_css_file_name = os.path.join(self.configdir, device_css_file_name)
            if os.path.isfile(device_css_file_name):
                common.log.info(
                    "KoboTouchExtended:upload_books:Found device-specific "
                    + f"file {device_css_file_name}"
                )
                shutil.copy(
                    device_css_file_name,
                    os.path.join(self._main_prefix, self.KOBO_EXTRA_CSSFILE),
                )
            else:
                common.log.info(
                    "KoboTouchExtended:upload_books:No device-specific CSS "
                    + f"file found (expecting {device_css_file_name})"
                )

        kobo_config_file = os.path.join(
            self._main_prefix, ".kobo", "Kobo", "Kobo eReader.conf"
        )
        if self.fwversion < (3, 11, 0):
            # The way the book progress was handled changed in 3.11.0 making this
            # option useless.
            if os.path.isfile(kobo_config_file):
                cfg = ConfigParser(allow_no_value=True)
                cfg.optionxform = lambda optionstr: optionstr
                cfg.read(kobo_config_file)

                try:
                    uses_FullBookPageNumbers = cfg.has_section(
                        "FeatureSettings"
                    ) and cfg.getboolean("FeatureSettings", "FullBookPageNumbers")
                except ValueError:
                    uses_FullBookPageNumbers = False
                except NoOptionError:
                    uses_FullBookPageNumbers = False

                if uses_FullBookPageNumbers == self.full_page_numbers:
                    pass
                else:
                    if not cfg.has_section("FeatureSettings"):
                        cfg.add_section("FeatureSettings")
                    common.log.info(
                        "KoboTouchExtended:upload_books:Setting FeatureSettings."
                        + "FullBookPageNumbers to "
                        + "true"
                        if self.full_page_numbers
                        else "false"
                    )
                    cfg.set(
                        "FeatureSettings",
                        "FullBookPageNumbers",
                        "true" if self.full_page_numbers else "false",
                    )
                    with open(kobo_config_file, "w") as cfgfile:
                        cfg.write(cfgfile)

        return super(KOBOTOUCHEXTENDED, self).upload_books(
            files, names, on_card, end_session, metadata
        )

    def filename_callback(self, path, mi):
        """Ensure the filename on the device is correct."""
        if (
            self.kepubify_book(mi)
            and path.endswith(EPUB_EXT)
            and mi.uuid not in self.skip_renaming_files
        ):
            common.log.debug(f"KoboTouchExtended:filename_callback:Path - {path}")
            path = path[: -len(EPUB_EXT)] + KEPUB_EXT + EPUB_EXT

            common.log.debug(f"KoboTouchExtended:filename_callback:New path - {path}")
        else:
            path = super(KOBOTOUCHEXTENDED, self).filename_callback(path, mi)

        return path

    def sanitize_path_components(self, components):
        """Perform any sanitization of path components."""
        return [self.invalid_filename_chars_re.sub("_", x) for x in components]

    def sync_booklists(self, booklists, end_session=True):
        """Synchronize book lists between calibre and the Kobo device."""
        if self.upload_covers:
            common.log.info("KoboTouchExtended:sync_booklists:Setting ImageId fields")

            select_query = (
                # DeepSource picks this up as possible SQL injection from string
                # concatenation, but the concatenation here is only static SQL. All
                # parameters are parameterized and passed to the SQL engine for
                # safe replacement.
                "SELECT ContentId FROM content WHERE "  # skipcq: BAN-B608
                + "ContentType = ? AND "  # skipcq: BAN-B608
                + "(ImageId IS NULL OR ImageId = '')"
            )
            update_query = "UPDATE content SET ImageId = ? WHERE ContentId = ?"
            try:
                db = self.device_database_connection()
            except AttributeError:
                import apsw

                db = apsw.Connection(self.device_database_path())

            def __rows_needing_imageid():
                """Map row ContentID entries needing an ImageID.

                Returns a dict object with keys being the ContentID of a row
                without an ImageID.
                """
                c = db.cursor()
                d = {}
                common.log.debug(
                    "KoboTouchExtended:sync_booklists:About to call query: "
                    + select_query
                )
                c.execute(select_query, (self.content_types["main"],))
                for row in c:
                    d[row[0]] = 1
                return d

            all_nulls = __rows_needing_imageid()
            common.log.debug(
                f"KoboTouchExtended:sync_booklists:Got {len(list(all_nulls.keys()))} "
                + "rows to update"
            )
            nulls = []
            for booklist in booklists:
                for b in booklist:
                    if b.application_id is not None and b.contentID in all_nulls:
                        nulls.append(
                            (self.imageid_from_contentid(b.contentID), b.contentID)
                        )

            cursor = db.cursor()
            while nulls[:100]:
                common.log.debug(
                    f"KoboTouchExtended:sync_booklists:Updating {len(nulls[:100])} "
                    + "ImageIDs..."
                )
                cursor.executemany(update_query, nulls[:100])
                del nulls[:100]
            cursor.close()
            db.close()
            common.log.debug(
                "KoboTouchExtended:sync_booklists:done setting ImageId fields"
            )

        super(KOBOTOUCHEXTENDED, self).sync_booklists(booklists, end_session)

    @classmethod
    def _config(cls):
        c = super(KOBOTOUCHEXTENDED, cls)._config()

        c.add_opt("extra_features", default=True)
        c.add_opt("use_template", default=False)
        c.add_opt("kepubify_template", default="")
        c.add_opt("upload_encumbered", default=False)
        c.add_opt("skip_failed", default=False)
        c.add_opt("hyphenate", default=False)
        c.add_opt("smarten_punctuation", default=False)
        c.add_opt("clean_markup", default=False)
        c.add_opt("full_page_numbers", default=False)
        c.add_opt("disable_hyphenation", default=False)
        c.add_opt("file_copy_dir", default="")
        c.add_opt("hyphenate_chars", default=6)
        c.add_opt("hyphenate_chars_before", default=3)
        c.add_opt("hyphenate_chars_after", default=3)
        c.add_opt("hyphenate_limit_lines", default=2)

        # remove_opt verifies the preference is present first
        c.remove_opt("replace_lang")

        return c

    @classmethod
    def migrate_old_settings(cls, settings):
        """Migrate old settings to the new format."""
        common.log.debug("KoboTouchExtended::migrate_old_settings - start")
        settings = super(KOBOTOUCHEXTENDED, cls).migrate_old_settings(settings)
        common.log.debug(
            "KoboTouchExtended::migrate_old_settings - end",
            settings.extra_customization,
        )

        count_options = 0
        opt_extra_features = count_options
        count_options += 1
        opt_upload_encumbered = count_options
        count_options += 1
        opt_skip_failed = count_options
        count_options += 1
        opt_hypnenate = count_options
        count_options += 1
        opt_smarten_punctuation = count_options
        count_options += 1
        opt_clean_markup = count_options
        count_options += 1
        opt_full_page_numbers = count_options
        count_options += 1
        opt_file_copy_dir = count_options
        count_options += 1
        opt_disable_hyphenation = count_options
        count_options += 1
        opt_hyphenate_chars = count_options
        count_options += 1
        opt_hyphenate_chars_before = count_options
        count_options += 1
        opt_hyphenate_chars_after = count_options
        count_options += 1
        opt_hyphenate_limit_lines = count_options

        if len(settings.extra_customization) >= count_options:
            common.log.warning(
                "KoboTouchExtended::migrate_old_settings - settings need to "
                + "be migrated"
            )
            try:
                settings.extra_features = settings.extra_customization[
                    opt_extra_features
                ]
            except IndexError:
                pass
            try:
                settings.upload_encumbered = settings.extra_customization[
                    opt_upload_encumbered
                ]
            except IndexError:
                pass
            try:
                settings.skip_failed = settings.extra_customization[opt_skip_failed]
            except IndexError:
                pass
            try:
                settings.hyphenate = settings.extra_customization[opt_hypnenate]
            except IndexError:
                pass
            try:
                settings.smarten_punctuation = settings.extra_customization[
                    opt_smarten_punctuation
                ]
            except IndexError:
                pass
            try:
                settings.clean_markup = settings.extra_customization[opt_clean_markup]
            except IndexError:
                pass
            try:
                settings.file_copy_dir = settings.extra_customization[opt_file_copy_dir]
                if not isinstance(settings.file_copy_dir, str):
                    settings.file_copy_dir = None
            except IndexError:
                pass
            try:
                settings.full_page_numbers = settings.extra_customization[
                    opt_full_page_numbers
                ]
            except IndexError:
                pass
            try:
                settings.disable_hyphenation = settings.extra_customization[
                    opt_disable_hyphenation
                ]
            except IndexError:
                pass
            try:
                settings.hyphenate_chars = settings.extra_customization[
                    opt_hyphenate_chars
                ]
            except IndexError:
                pass
            try:
                settings.hyphenate_chars_before = settings.extra_customization[
                    opt_hyphenate_chars_before
                ]
            except IndexError:
                pass
            try:
                settings.hyphenate_chars_after = settings.extra_customization[
                    opt_hyphenate_chars_after
                ]
            except IndexError:
                pass
            try:
                settings.hyphenate_limit_lines = settings.extra_customization[
                    opt_hyphenate_limit_lines
                ]
            except IndexError:
                pass

            settings.extra_customization = settings.extra_customization[
                count_options + 1 :  # noqa:E203 - thanks Black formatting!
            ]
            common.log.info(
                "KoboTouchExtended::migrate_old_settings - end",
                settings.extra_customization,
            )

        return settings

    def kepubify_book(self, metadata):
        """Return if the book is to be kepubified."""
        kepubify_book = self.extra_features
        common.log.warning(
            f"kepubify_book - self.kepubify_template='{self.kepubify_template}'"
        )
        if kepubify_book and self.use_template:
            from calibre.ebooks.metadata.book.formatter import SafeFormat

            common.log.warning(f"kepubify_book - metadata='{metadata}'")
            common.log.warning(
                f"kepubify_book - self.kepubify_template='{self.kepubify_template}'"
            )
            kepubify = SafeFormat().safe_format(
                self.kepubify_template, metadata, "Open With template error", metadata
            )
            common.log.warning(
                f"kepubify_book - after SafeFormat kepubify='{kepubify}'"
            )
            if kepubify is not None and kepubify.startswith("PLUGBOARD TEMPLATE ERROR"):
                common.log.warning(
                    f"kepubify_book - self.kepubify_template='{self.kepubify_template}'"
                )
                common.log.warning(f"kepubify_book - kepubify='{kepubify}'")
                kepubify_book = True
            else:
                kepubify_book = not kepubify == ""
        common.log.warning(f"kepubify_book - returning kepubify_book='{kepubify_book}'")
        return kepubify_book

    @property
    def extra_features(self):
        """Determine if extra Kobo features are being applied."""
        return self.get_pref("extra_features")

    @property
    def use_template(self):
        """Determine if the option to use the template for kepubification ."""
        return self.get_pref("use_template")

    @property
    def kepubify_template(self):
        """Determine the kepubify template."""
        return self.get_pref("kepubify_template")

    @property
    def upload_encumbered(self):
        """Determine if DRM-encumbered files will be uploaded."""
        return self.get_pref("upload_encumbered")

    @property
    def skip_failed(self):
        """Determine if failed conversions will be skipped."""
        return self.get_pref("skip_failed")

    @property
    def hyphenate(self):
        """Determine if hyphenation will be enabled."""
        return self.get_pref("hyphenate")

    @property
    def smarten_punctuation(self):
        """Determine if punctuation will be made into smart punctuation."""
        return self.get_pref("smarten_punctuation")

    @property
    def clean_markup(self):
        """Determine if additional cleanup will be done on the book contents."""
        return self.get_pref("clean_markup")

    @property
    def full_page_numbers(self):
        """Determine if the device should display book page numbers."""
        return self.get_pref("full_page_numbers")

    @property
    def disable_hyphenation(self):
        """Determine if hyphenation should be disabled."""
        return self.get_pref("disable_hyphenation")

    @property
    def file_copy_dir(self):
        """Determine where to copy converted books to."""
        return self.get_pref("file_copy_dir")

    @property
    def hyphenate_chars(self):
        return self.get_pref("hyphenate_chars")

    @property
    def hyphenate_chars_before(self):
        return self.get_pref("hyphenate_chars_before")

    @property
    def hyphenate_chars_after(self):
        return self.get_pref("hyphenate_chars_after")

    @property
    def hyphenate_limit_lines(self):
        lines = self.get_pref("hyphenate_limit_lines")

        if lines == 0:
            return "no-limit"

        return lines
