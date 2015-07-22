# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

__license__ = 'GPL v3'
__copyright__ = '2015, David Forrester <davidfor@internode.on.net>'
__docformat__ = 'markdown en'

from calibre.gui2.convert.epub_output import PluginWidget as EPUBPluginWidget
from calibre.gui2.convert.epub_output_ui import Ui_Form as EPUBUIForm
from calibre.gui2.convert import Widget
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


class PluginWidget(EPUBPluginWidget, EPUBUIForm):

    TITLE = 'KePub Input'
    COMMIT_NAME = 'kepub_input'
    ICON = I('mimetypes/epub.png')
    HELP = _('Options specific to KePub input.')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, ['dont_split_on_page_breaks', 'flow_size',
                                       'no_default_epub_cover', 'no_svg_cover',
                                       'epub_inline_toc', 'epub_toc_at_end', 'toc_title',
                                       'preserve_cover_aspect_ratio', 'epub_flatten',
                                       'strip_kobo_spans',])
        if book_id:
            self._icon = QIcon(I('forward.png'))
        self.initialize_options(get_option, get_help, db, book_id)

    def setupUi(self, Form):
        super(PluginWidget, self).setupUi(Form)

        rows = self.gridLayout.rowCount() - 1

        spacer = self.gridLayout.itemAtPosition(rows, 0)
        self.gridLayout.removeItem(spacer)

        self.opt_strip_kobo_spans = QtGui.QCheckBox(Form)
        self.opt_strip_kobo_spans.setObjectName(unicode("opt_strip_kobo_spans"))
        self.opt_strip_kobo_spans.setText(_("Strip Kobo spans"))
        self.gridLayout.addWidget(self.opt_strip_kobo_spans, rows, 0, 1, 1)
        rows = rows + 1

        # Next options here
        self.gridLayout.addItem(spacer, rows, 0, 1, 1)

        # Copy from calibre.gui2.convert.epub_output_ui.Ui_Form to make the new additions work
        QtCore.QMetaObject.connectSlotsByName(Form)


class OutputOptions(BaseOutputOptions):

    def load_conversion_widgets(self):
        super(OutputOptions, self).load_conversion_widgets()
        self.conversion_widgets.append(PluginWidget)
        self.conversion_widgets = sorted(self.conversion_widgets, key=lambda x: x.TITLE)
