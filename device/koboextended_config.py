#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=indent:ai

"""Driver configuration for KoboTouchExtended."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__license__ = "GPL v3"
__copyright__ = "2016, David Forrester, Joel Goguen <contact@jgoguen.ca>"
__docformat__ = "markdown en"

from PyQt5.Qt import QGridLayout
from PyQt5.Qt import QLabel
from PyQt5.Qt import QLineEdit
from PyQt5.Qt import QVBoxLayout

from calibre.devices.kobo.kobotouch_config import KOBOTOUCHConfig
from calibre.gui2.device_drivers.tabbed_device_config import DeviceConfigTab
from calibre.gui2.device_drivers.tabbed_device_config import DeviceOptionsGroupBox
from calibre.gui2.device_drivers.tabbed_device_config import create_checkbox
from calibre.utils.logging import default_log

# Support load_translations() without forcing calibre 1.9+
try:
    load_translations()
except NameError:
    pass


class KOBOTOUCHEXTENDEDConfig(KOBOTOUCHConfig):
    """Configuration for KoboTouchExtended."""

    def __init__(
        self,
        device_settings,
        all_formats,
        supports_subdirs,
        must_read_metadata,
        supports_use_author_sort,
        extra_customization_message,
        device,
        extra_customization_choices=None,
        parent=None,
    ):
        """Initialize configuration."""
        super(KOBOTOUCHEXTENDEDConfig, self).__init__(
            device_settings,
            all_formats,
            supports_subdirs,
            must_read_metadata,
            supports_use_author_sort,
            extra_customization_message,
            device,
            extra_customization_choices,
            parent,
        )

        self.tabExtended = TabExtendedConfig(self, self.device)
        self.addDeviceTab(self.tabExtended, _("Extended"))  # noqa: F821

    def commit(self):
        """Process driver options for saving."""
        default_log("KOBOTOUCHEXTENDEDConfig::commit: start")
        p = super(KOBOTOUCHEXTENDEDConfig, self).commit()

        p["extra_features"] = self.extra_features
        p["upload_encumbered"] = self.upload_encumbered
        p["skip_failed"] = self.skip_failed
        p["hyphenate"] = self.hyphenate
        p["smarten_punctuation"] = self.smarten_punctuation
        p["clean_markup"] = self.clean_markup
        p["full_page_numbers"] = self.full_page_numbers
        p["disable_hyphenation"] = self.disable_hyphenation
        p["file_copy_dir"] = self.file_copy_dir

        return p


class TabExtendedConfig(DeviceConfigTab):
    """The config widget tab for KoboTouchExtended options."""

    def __init__(self, parent, device):
        """Initialize KoboTouchExtended config tab."""
        super(TabExtendedConfig, self).__init__(parent)

        self.l = QVBoxLayout(self)  # noqa: E741
        self.setLayout(self.l)

        self.extended_options = ExtendedGroupBox(self, device)
        self.l.addWidget(self.extended_options)
        self.addDeviceWidget(self.extended_options)


class ExtendedGroupBox(DeviceOptionsGroupBox):
    """The options group for KoboTouchExtended."""

    def __init__(self, parent, device):
        """Set up driver config options group."""
        super(ExtendedGroupBox, self).__init__(
            parent, device, _("Extended driver")  # noqa: F821
        )

        self.options_layout = QGridLayout()
        self.options_layout.setObjectName("options_layout")
        self.setLayout(self.options_layout)

        self.extra_features_checkbox = create_checkbox(
            _("Enable Extended Kobo Features"),  # noqa: F821
            _("Choose whether to enable extra customizations"),  # noqa: F821
            device.get_pref("extra_features"),
        )

        self.upload_encumbered_checkbox = create_checkbox(
            _("Upload DRM-encumbered ePub files"),  # noqa: F821
            _(  # noqa: F821
                "Select this to upload ePub files encumbered by DRM. If this "
                "is not selected, it is a fatal error to upload an encumbered "
                "file"
            ),
            device.get_pref("upload_encumbered"),
        )

        self.skip_failed_checkbox = create_checkbox(
            _("Silently Ignore Failed Conversions"),  # noqa: F821
            _(  # noqa: F821
                "Select this to not upload any book that fails conversion to "
                "kepub. If this is not selected, the upload process will be "
                "stopped at the first book that fails. If this is selected, "
                "failed books will be silently removed from the upload queue."
            ),
            device.get_pref("skip_failed"),
        )

        self.hyphenate_checkbox = create_checkbox(
            _("Hyphenate Files"),  # noqa: F821
            _(  # noqa: F821
                "Select this to add a CSS file which enables hyphenation. The "
                "language used will be the language defined for the book in "
                "calibre. Please see the README file for directions on "
                "updating hyphenation dictionaries."
            ),
            device.get_pref("hyphenate"),
        )

        self.smarten_punctuation_checkbox = create_checkbox(
            _("Smarten Punctuation"),  # noqa: F821
            _("Select this to smarten punctuation in the ePub"),  # noqa: F821
            device.get_pref("smarten_punctuation"),
        )

        self.clean_markup_checkbox = create_checkbox(
            _("Clean up ePub Markup"),  # noqa: F821
            _("Select this to clean up the internal ePub markup."),  # noqa: F821
            device.get_pref("clean_markup"),
        )

        self.file_copy_dir_checkbox = create_checkbox(
            _("Copy generated KePub files to a directory"),  # noqa: F821
            _(  # noqa: F821
                "Enter an absolute directory path to copy all generated KePub "
                "files into for debugging purposes."
            ),
            device.get_pref("file_copy_dir"),
        )
        self.file_copy_dir_label = QLabel(
            _("Copy generated KePub files to a directory")  # noqa: F821
        )
        self.file_copy_dir_edit = QLineEdit(self)
        self.file_copy_dir_edit.setToolTip(
            _(  # noqa: F821
                "Enter an absolute directory path to copy all generated KePub "
                "files into for debugging purposes."
            )
        )
        self.file_copy_dir_edit.setText(device.get_pref("file_copy_dir"))
        self.file_copy_dir_label.setBuddy(self.file_copy_dir_edit)

        self.full_page_numbers_checkbox = create_checkbox(
            _("Use full book page numbers"),  # noqa: F821
            _(  # noqa: F821
                "Select this to show page numbers for the whole book, instead "
                "of each chapter. This will also affect regular ePub page "
                "number display!"
            ),
            device.get_pref("full_page_numbers"),
        )

        self.disable_hyphenation_checkbox = create_checkbox(
            _("Disable hyphenation"),  # noqa: F821
            _("Select this to disable hyphenation for books."),  # noqa: F821
            device.get_pref("disable_hyphenation"),
        )

        self.options_layout.addWidget(self.extra_features_checkbox, 0, 0, 1, 1)
        self.options_layout.addWidget(self.upload_encumbered_checkbox, 0, 1, 1, 1)
        self.options_layout.addWidget(self.skip_failed_checkbox, 1, 0, 1, 1)
        self.options_layout.addWidget(self.hyphenate_checkbox, 1, 1, 1, 1)
        self.options_layout.addWidget(self.smarten_punctuation_checkbox, 2, 1, 1, 1)
        self.options_layout.addWidget(self.clean_markup_checkbox, 3, 0, 1, 1)
        self.options_layout.addWidget(self.file_copy_dir_label, 4, 0, 1, 1)
        self.options_layout.addWidget(self.file_copy_dir_edit, 4, 1, 1, 1)
        self.options_layout.addWidget(self.full_page_numbers_checkbox, 5, 0, 1, 1)
        self.options_layout.addWidget(self.disable_hyphenation_checkbox, 5, 1, 1, 1)
        self.options_layout.setRowStretch(6, 2)

    @property
    def extra_features(self):
        """Determine if Kobo extra features are enabled."""
        return self.extra_features_checkbox.isChecked()

    @property
    def upload_encumbered(self):
        """Determine if DRM-encumbered files will be uploaded."""
        return self.upload_encumbered_checkbox.isChecked()

    @property
    def skip_failed(self):
        """Determine if failed conversions will be skipped."""
        return self.skip_failed_checkbox.isChecked()

    @property
    def hyphenate(self):
        """Determine if hyphenation should be enabled."""
        return self.hyphenate_checkbox.isChecked()

    @property
    def smarten_punctuation(self):
        """Determine if punctuation should be converted to smart punctuation."""
        return self.smarten_punctuation_checkbox.isChecked()

    @property
    def clean_markup(self):
        """Determine if additional markup cleanup will be done."""
        return self.clean_markup_checkbox.isChecked()

    @property
    def full_page_numbers(self):
        """Determine if full-book page numbers will be displayed."""
        return self.full_page_numbers_checkbox.isChecked()

    @property
    def disable_hyphenation(self):
        """Determine if hyphenation should be disabled."""
        return self.disable_hyphenation_checkbox.isChecked()

    @property
    def file_copy_dir(self):
        """Determine where to copy converted KePub books to."""
        return self.file_copy_dir_edit.text().strip()
