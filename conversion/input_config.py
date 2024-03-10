# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

"""Configuration for reading KePub files."""

__license__ = "GPL v3"
__copyright__ = "2015, David Forrester <davidfor@internode.on.net>"
__docformat__ = "markdown en"

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget
from calibre.gui2.convert.epub_output_ui import Ui_Form as EPUBUIForm
from calibre.gui2.preferences.conversion import OutputOptions as BaseOutputOptions


try:
    from PyQt5.Qt import QIcon
    from PyQt5 import Qt as QtGui
    from PyQt5 import QtCore
except ImportError:
    from PyQt4.Qt import QIcon
    from PyQt4 import QtCore, QtGui

try:
    load_translations()
except NameError:
    pass


class PluginWidget(Widget, EPUBUIForm):
    """Configuration widget for KePub input parser."""

    TITLE = "KePub Input"
    COMMIT_NAME = "kepub_input"
    ICON = I("mimetypes/epub.png")  # noqa: F821 - defined by calibre
    HELP = _("Options specific to KePub input.")  # noqa: F821 - calibre

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        """Initialize KePub input configuration."""
        Widget.__init__(
            self,
            parent,
            OPTIONS["input"].get("epub", ()) + ("strip_kobo_spans",),
        )

        if book_id:
            self._icon = QIcon(I("forward.png"))  # noqa: F821 - calibre
        self.initialize_options(get_option, get_help, db, book_id)

    def setupUi(self, Form):  # noqa: N802, N803
        """Set up configuration UI."""
        super(PluginWidget, self).setupUi(Form)

        rows = self.gridLayout.rowCount() - 1

        spacer = self.gridLayout.itemAtPosition(rows, 0)
        self.gridLayout.removeItem(spacer)

        self.opt_strip_kobo_spans = QtGui.QCheckBox(Form)  # skipcq: PYL-W0201
        self.opt_strip_kobo_spans.setObjectName("opt_strip_kobo_spans")
        self.opt_strip_kobo_spans.setText(_("Strip Kobo spans"))  # noqa: F821
        self.gridLayout.addWidget(self.opt_strip_kobo_spans, rows, 0, 1, 1)
        rows = rows + 1

        # Next options here
        self.gridLayout.addItem(spacer, rows, 0, 1, 1)

        # Copy from calibre.gui2.convert.epub_output_ui.Ui_Form to make the
        # new additions work
        QtCore.QMetaObject.connectSlotsByName(Form)


class OutputOptions(BaseOutputOptions):
    """This allows adding our options to the input process."""

    def load_conversion_widgets(self):
        """Add our configuration to the input processing."""
        super(OutputOptions, self).load_conversion_widgets()
        self.conversion_widgets.append(PluginWidget)
        self.conversion_widgets = sorted(
            self.conversion_widgets, key=lambda x: x.TITLE
        )  # skipcq: PYL-W0201
