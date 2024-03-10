# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

"""Configuration for exporting KePub files."""

__license__ = "GPL v3"
__copyright__ = "2013, Joel Goguen <jgoguen@jgoguen.ca>"
__docformat__ = "markdown en"

import functools

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget
from calibre.gui2.convert.epub_output import PluginWidget as EPUBPluginWidget
from calibre.gui2.convert.epub_output_ui import Ui_Form as EPUBUIForm
from calibre.gui2.preferences.conversion import OutputOptions as BaseOutputOptions

from calibre_plugins.kepubout import common

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
    # If something seems wrong, start by checking for changes there.
    # We copy that instead of calling super().__init__() because the super __init__
    # calls Widget.__init__() with ePub options and there's no easy way to add and link
    # new UI elements once that's been done.
    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        """Initialize the KePub output configuration widget."""
        Widget.__init__(
            self,
            parent,
            OPTIONS["output"].get("epub", ())
            + (
                "kepub_hyphenate",
                "kepub_clean_markup",
                "kepub_disable_hyphenation",
                "kepub_hyphenate_chars",
                "kepub_hyphenate_chars_before",
                "kepub_hyphenate_chars_after",
                "kepub_hyphenate_limit_lines",
            ),
        )
        self.opt_no_svg_cover.toggle()
        self.opt_no_svg_cover.toggle()
        ev = get_option("epub_version")
        self.opt_epub_version.addItems(list(ev.option.choices))
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

    def setupUi(self, Form):  # noqa: N802, N803
        """Set up the plugin widget UI."""
        super(PluginWidget, self).setupUi(Form)

        from PyQt5 import QtWidgets
        from PyQt5 import QtCore

        rows = self.gridLayout.rowCount() - 1

        spacer = self.gridLayout.itemAtPosition(rows, 0)
        self.gridLayout.removeItem(spacer)

        self.opt_kepub_hyphenate = QtWidgets.QCheckBox(Form)  # skipcq: PYL-W0201
        self.opt_kepub_hyphenate.setObjectName("opt_kepub_hyphenate")  # noqa: F821
        self.opt_kepub_hyphenate.setText(_("Hyphenate Files"))  # noqa: F821
        self.gridLayout.addWidget(self.opt_kepub_hyphenate, rows, 0, 1, 1)

        self.opt_kepub_disable_hyphenation = QtWidgets.QCheckBox(
            Form
        )  # skipcq: PYL-W0201
        self.opt_kepub_disable_hyphenation.setObjectName(
            "opt_kepub_disable_hyphenation"  # noqa: F821
        )
        self.opt_kepub_disable_hyphenation.setText(
            _("Disable hyphenation")  # noqa: F821
        )
        self.gridLayout.addWidget(self.opt_kepub_disable_hyphenation, rows, 1, 1, 1)

        rows += 1

        self.opt_kepub_hyphenate_chars_label = QtWidgets.QLabel(
            _("Minimum word length to hyphenate") + ":"  # noqa: F821
        )  # skipcq: PYL-W0201
        self.gridLayout.addWidget(self.opt_kepub_hyphenate_chars_label, rows, 0, 1, 1)

        self.opt_kepub_hyphenate_chars = QtWidgets.QSpinBox(Form)  # skipcq: PYL-W0201
        self.opt_kepub_hyphenate_chars_label.setBuddy(self.opt_kepub_hyphenate_chars)
        self.opt_kepub_hyphenate_chars.setObjectName("opt_kepub_hyphenate_chars")
        self.opt_kepub_hyphenate_chars.setSpecialValueText(_("Disabled"))  # noqa: F821
        self.opt_kepub_hyphenate_chars.valueChanged.connect(
            functools.partial(
                common.intValueChanged,
                self.opt_kepub_hyphenate_chars,
                _("character"),  # noqa: F821
                _("characters"),  # noqa: F821
            )
        )
        self.gridLayout.addWidget(self.opt_kepub_hyphenate_chars, rows, 1, 1, 1)

        rows += 1

        self.opt_kepub_hyphenate_chars_before_label = QtWidgets.QLabel(
            _("Minimum characters before hyphens") + ":"  # noqa: F821
        )  # skipcq: PYL-W0201
        self.gridLayout.addWidget(
            self.opt_kepub_hyphenate_chars_before_label, rows, 0, 1, 1
        )

        self.opt_kepub_hyphenate_chars_before = QtWidgets.QSpinBox(
            Form
        )  # skipcq: PYL-W0201
        self.opt_kepub_hyphenate_chars_before_label.setBuddy(
            self.opt_kepub_hyphenate_chars_before
        )
        self.opt_kepub_hyphenate_chars_before.setObjectName(
            "opt_kepub_hyphenate_chars_before"
        )
        self.opt_kepub_hyphenate_chars_before.valueChanged.connect(
            functools.partial(
                common.intValueChanged,
                self.opt_kepub_hyphenate_chars_before,
                _("character"),  # noqa: F821
                _("characters"),  # noqa: F821
            )
        )
        self.opt_kepub_hyphenate_chars_before.setMinimum(2)
        self.gridLayout.addWidget(self.opt_kepub_hyphenate_chars_before, rows, 1, 1, 1)

        rows += 1

        self.opt_kepub_hyphenate_chars_after_label = QtWidgets.QLabel(
            _("Minimum characters after hyphens") + ":"  # noqa: F821
        )  # skipcq: PYL-W0201
        self.gridLayout.addWidget(
            self.opt_kepub_hyphenate_chars_after_label, rows, 0, 1, 1
        )

        self.opt_kepub_hyphenate_chars_after = QtWidgets.QSpinBox(
            Form
        )  # skipcq: PYL-W0201
        self.opt_kepub_hyphenate_chars_after_label.setBuddy(
            self.opt_kepub_hyphenate_chars_after
        )
        self.opt_kepub_hyphenate_chars_after.setObjectName(
            "opt_kepub_hyphenate_chars_after"
        )
        self.opt_kepub_hyphenate_chars_after.valueChanged.connect(
            functools.partial(
                common.intValueChanged,
                self.opt_kepub_hyphenate_chars_after,
                _("character"),  # noqa: F821
                _("characters"),  # noqa: F821
            )
        )
        self.opt_kepub_hyphenate_chars_after.setMinimum(2)
        self.gridLayout.addWidget(self.opt_kepub_hyphenate_chars_after, rows, 1, 1, 1)

        rows += 1

        self.opt_kepub_hyphenate_limit_lines_label = QtWidgets.QLabel(
            _("Maximum consecutive hyphenated lines") + ":"  # noqa: F821
        )  # skipcq: PYL-W0201
        self.gridLayout.addWidget(
            self.opt_kepub_hyphenate_limit_lines_label, rows, 0, 1, 1
        )

        self.opt_kepub_hyphenate_limit_lines = QtWidgets.QSpinBox(
            Form
        )  # skipcq: PYL-W0201
        self.opt_kepub_hyphenate_limit_lines_label.setBuddy(
            self.opt_kepub_hyphenate_limit_lines
        )
        self.opt_kepub_hyphenate_limit_lines.setObjectName(
            "opt_kepub_hyphenate_limit_lines"
        )
        self.opt_kepub_hyphenate_limit_lines.setSpecialValueText(
            _("Disabled")  # noqa: F821
        )
        self.opt_kepub_hyphenate_limit_lines.valueChanged.connect(
            functools.partial(
                common.intValueChanged,
                self.opt_kepub_hyphenate_limit_lines,
                _("line"),  # noqa: F821
                _("lines"),  # noqa: F821
            )
        )
        self.gridLayout.addWidget(self.opt_kepub_hyphenate_limit_lines, rows, 1, 1, 1)

        rows += 1

        self.opt_kepub_clean_markup = QtWidgets.QCheckBox(Form)  # skipcq: PYL-W0201
        self.opt_kepub_clean_markup.setObjectName(
            "opt_kepub_clean_markup"  # noqa: F821
        )
        self.opt_kepub_clean_markup.setText(_("Clean up ePub markup"))  # noqa: F821
        self.gridLayout.addWidget(self.opt_kepub_clean_markup, rows, 0, 1, 1)

        # Next options here

        rows += 1

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
        self.conversion_widgets = sorted(
            self.conversion_widgets, key=lambda x: x.TITLE
        )  # skipcq: PYL-W0201
