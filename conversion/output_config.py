# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

"""Configuration for exporting KePub files."""

from __future__ import unicode_literals

__license__ = "GPL v3"
__copyright__ = "2013, Joel Goguen <jgoguen@jgoguen.ca>"
__docformat__ = "markdown en"

from calibre.gui2.convert import Widget
from calibre.gui2.convert.epub_output import PluginWidget as EPUBPluginWidget
from calibre.gui2.convert.epub_output_ui import Ui_Form as EPUBUIForm
from calibre.gui2.preferences.conversion import OutputOptions as BaseOutputOptions

# Support load_translations() without forcing calibre 1.9+
try:
    load_translations()
except NameError:
    pass


class PluginWidget(EPUBPluginWidget, EPUBUIForm):
    """The plugin configuration widget for a KePub output plugin."""

    TITLE = "KePub Output"
    HELP = _("Options specific to KePub output")  # noqa: F821
    COMMIT_NAME = "kepub_output"

    # A near copy of calibre.gui2.convert.epub_output.PluginWidget#__init__
    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        """Initialize the KePub output configuration widget."""
        Widget.__init__(
            self,
            parent,
            [
                "dont_split_on_page_breaks",
                "flow_size",
                "no_default_epub_cover",
                "no_svg_cover",
                "epub_inline_toc",
                "epub_toc_at_end",
                "toc_title",
                "preserve_cover_aspect_ratio",
                "epub_flatten",
                "kepub_hyphenate",
                "kepub_clean_markup",
                "kepub_disable_hyphenation",
            ],
        )
        for i in range(2):
            self.opt_no_svg_cover.toggle()
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

    def setupUi(self, Form):  # noqa: N802, N803
        """Set up the plugin widget UI."""
        super(PluginWidget, self).setupUi(Form)

        try:
            from PyQt5 import Qt as QtGui
            from PyQt5 import QtCore
        except ImportError:
            from PyQt4 import QtCore
            from PyQt4 import QtGui

        rows = self.gridLayout.rowCount() - 1

        spacer = self.gridLayout.itemAtPosition(rows, 0)
        self.gridLayout.removeItem(spacer)

        self.opt_kepub_hyphenate = QtGui.QCheckBox(Form)
        self.opt_kepub_hyphenate.setObjectName("opt_kepub_hyphenate")  # noqa: F821
        self.opt_kepub_hyphenate.setText(_("Hyphenate Files"))  # noqa: F821
        self.gridLayout.addWidget(self.opt_kepub_hyphenate, rows, 0, 1, 1)

        self.opt_kepub_disable_hyphenation = QtGui.QCheckBox(Form)
        self.opt_kepub_disable_hyphenation.setObjectName(
            "opt_kepub_disable_hyphenation"  # noqa: F821
        )
        self.opt_kepub_disable_hyphenation.setText(
            _("Disable hyphenation")  # noqa: F821
        )
        self.gridLayout.addWidget(self.opt_kepub_disable_hyphenation, rows, 1, 1, 1)

        rows = rows + 1

        self.opt_kepub_clean_markup = QtGui.QCheckBox(Form)
        self.opt_kepub_clean_markup.setObjectName(
            "opt_kepub_clean_markup"  # noqa: F821
        )
        self.opt_kepub_clean_markup.setText(_("Clean up ePub markup"))  # noqa: F821
        self.gridLayout.addWidget(self.opt_kepub_clean_markup, rows, 0, 1, 1)

        rows = rows + 1

        # Next options here

        self.gridLayout.addItem(spacer, rows, 0, 1, 1)

        # Copy from calibre.gui2.convert.epub_output_ui.Ui_Form to make the
        # new additions work
        QtCore.QMetaObject.connectSlotsByName(Form)


class OutputOptions(BaseOutputOptions):
    """This allows adding our options to the output process."""

    def load_conversion_widgets(self):
        """Add our configuration to the output process."""
        super(OutputOptions, self).load_conversion_widgets()
        self.conversion_widgets.append(PluginWidget)
        self.conversion_widgets = sorted(self.conversion_widgets, key=lambda x: x.TITLE)
