# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2013, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

from calibre.gui2.convert.epub_output import PluginWidget as EPUBPluginWidget
from calibre.gui2.convert.epub_output_ui import Ui_Form as EPUBUIForm

class PluginWidget(EPUBPluginWidget, EPUBUIForm):
    TITLE = 'KePub Output'
    HELP = 'Options specific to KePub output'
    COMMIT_NAME = 'kepub_output'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        EPUBPluginWidget.__init__(self, parent, get_option, get_help, db, book_id)

    def setupUi(self, Form):
        super(PluginWidget, self).setupUi(Form)

        from PyQt4 import QtCore
        from PyQt4 import QtGui
        from calibre.gui2.convert.epub_output_ui import _fromUtf8

        rows = self.gridLayout.rowCount() - 1

        spacer = self.gridLayout.itemAtPosition(rows, 0)
        self.gridLayout.removeItem(spacer)

        self.opt_kepub_enable_extended_features = QtGui.QCheckBox(Form)
        self.opt_kepub_enable_extended_features.setObjectName(_fromUtf8("opt_kepub_enable_extended_features"))
        self.opt_kepub_enable_extended_features.setText("Enable extended KePub features")
        self.gridLayout.addWidget(self.opt_kepub_enable_extended_features, rows, 0, 1, 1)

        self.opt_kepub_hyphenate = QtGui.QCheckBox(Form)
        self.opt_kepub_hyphenate.setObjectName(_fromUtf8("opt_kepub_hyphenate"))
        self.opt_kepub_hyphenate.setText("Hyphenate files")
        self.gridLayout.addWidget(self.opt_kepub_hyphenate, rows, 1, 1, 1)
        rows = rows + 1

        self.opt_kepub_replace_lang = QtGui.QCheckBox(Form)
        self.opt_kepub_replace_lang.setObjectName(_fromUtf8("opt_kepub_replace_lang"))
        self.opt_kepub_replace_lang.setText("Update content file language")
        self.gridLayout.addWidget(self.opt_kepub_replace_lang, rows, 0, 1, 1)

        self.opt_kepub_clean_markup = QtGui.QCheckBox(Form)
        self.opt_kepub_clean_markup.setObjectName(_fromUtf8("opt_kepub_clean_markup"))
        self.opt_kepub_clean_markup.setText("Clean ePub markup")
        self.gridLayout.addWidget(self.opt_kepub_clean_markup, rows, 1, 1, 1)
        rows = rows + 1

        # Next options here

        self.gridLayout.addItem(spacer, rows, 0, 1, 1)

        # Copy from calibre.gui2.convert.epub_output_ui.Ui_Form to make the new additions work
        QtCore.QObject.connect(self.opt_no_svg_cover, QtCore.SIGNAL(_fromUtf8("toggled(bool)")), self.opt_preserve_cover_aspect_ratio.setDisabled)
        QtCore.QMetaObject.connectSlotsByName(Form)