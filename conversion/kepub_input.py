from __future__ import with_statement
__license__ = 'GPL v3'
__copyright__ = '2015, David Forrester <davidfor@internode.on.net>'
__docformat__ = 'markdown en'

import os

from calibre.ebooks.conversion.plugins.epub_input import EPUBInput
from calibre.customize.conversion import OptionRecommendation
from calibre_plugins.kepubin.common import plugin_version

# Support load_translations() without forcing calibre 1.9+
try:
    load_translations()
except NameError:
    pass


class KEPUBInput(EPUBInput):

    name = 'KePub Input'
    description = 'Convert KEPUB files (.kepub) to HTML'
    author = 'David Forrester'
    file_types = set(['kepub'])
    version = plugin_version
    minimum_calibre_version = (0, 1, 0)

    options = {
        OptionRecommendation(
            name='strip_kobo_spans',
            recommended_value=True,
            help=_(
                'Kepubs have spans wrapping each sentence. These are used by the ereader for the reading location '
                'and bookmark location. They are not used by an ePub reader but are valid code and can be safely be '
                'left in the ePub. If you plan to edit the ePub, it is recommended that you remove the spans.')),
    }

    recommendations = set([])

    def gui_configuration_widget(self,
                                 parent,
                                 get_option_by_name,
                                 get_option_help,
                                 db,
                                 book_id=None):
        from calibre_plugins.kepubin.conversion.input_config import PluginWidget
        return PluginWidget(parent, get_option_by_name, get_option_help, db,
                            book_id)

    def convert(self, stream, options, file_ext, log, accelerators):
        log("KEPUBInput::convert - start")
        from calibre.utils.zipfile import ZipFile
        from calibre import walk
        from calibre.ebooks import DRMError
        from calibre.ebooks.metadata.opf2 import OPF
        try:
            zf = ZipFile(stream)
            zf.extractall(os.getcwdu())
        except:
            log.exception('KEPUB appears to be invalid ZIP file, trying a '
                          'more forgiving ZIP parser')
            from calibre.utils.localunzip import extractall
            stream.seek(0)
            extractall(stream)
        opf = self.find_opf()
        if opf is None:
            for f in walk(u'.'):
                if f.lower().endswith('.opf') and '__MACOSX' not in f and \
                        not os.path.basename(f).startswith('.'):
                    opf = os.path.abspath(f)
                    break
        path = getattr(stream, 'name', 'stream')

        if opf is None:
            raise ValueError(
                _('%s is not a valid KEPUB file (could not find opf)') % path)

        encfile = os.path.abspath('rights.xml')
        if os.path.exists(encfile):
            raise DRMError(os.path.basename(path))

        opf = os.path.relpath(opf, os.getcwdu())
        parts = os.path.split(opf)
        opf = OPF(opf, os.path.dirname(os.path.abspath(opf)))

        self.encrypted_fonts = []

        if len(parts) > 1 and parts[0]:
            delta = '/'.join(parts[:-1]) + '/'
            for elem in opf.itermanifest():
                elem.set('href', delta + elem.get('href'))
            for elem in opf.iterguide():
                elem.set('href', delta + elem.get('href'))

        self.removed_cover = self.rationalize_cover(opf, log)

        self.optimize_opf_parsing = opf
        for x in opf.itermanifest():
            if x.get('media-type', '') == 'application/x-dtbook+xml':
                raise ValueError(_(
                    'EPUB files with DTBook markup are not supported'))

        not_for_spine = set()
        for y in opf.itermanifest():
            id_ = y.get('id', None)
            if id_ and y.get('media-type', None) in {
                    'application/vnd.adobe-page-template+xml',
                    'application/vnd.adobe.page-template+xml',
                    'application/adobe-page-template+xml',
                    'application/adobe.page-template+xml', 'application/text'
            }:
                not_for_spine.add(id_)

        seen = set()
        for x in list(opf.iterspine()):
            ref = x.get('idref', None)
            if not ref or ref in not_for_spine or ref in seen:
                x.getparent().remove(x)
                continue
            seen.add(ref)

        if len(list(opf.iterspine())) == 0:
            raise ValueError(_('No valid entries in the spine of this EPUB'))

        with open('content.opf', 'wb') as nopf:
            nopf.write(opf.render())

        return os.path.abspath(u'content.opf')

    def postprocess_book(self, oeb, opts, log):
        log("KEPUBInput::postprocess_book - start")
        from calibre.ebooks.oeb.base import XHTML_NS

        # The Kobo spans wrap each sentence. Remove them and add their text to
        # the parent tag.
        def refactor_span(a):
            p = a.getparent()
            idx = p.index(a) - 1
            p.remove(a)

            if idx < 0:
                if p.text is None:
                    p.text = ''
                p.text += a.text if a.text else ''
                p.text += a.tail if a.tail else ''
            else:
                if p[idx].tail is None:
                    p[idx].tail = ''
                p[idx].tail += a.text if a.text else ''
                p[idx].tail += a.tail if a.tail else ''

        super(KEPUBInput, self).postprocess_book(oeb, opts, log)
        if not opts.strip_kobo_spans:
            log("KEPUBInput::postprocess_book - not stripping kobo spans")
            return

        for item in oeb.spine:
            log("item.__class__.__name__", item.__class__.__name__)
            if not hasattr(item.data, 'xpath'):
                continue

            for a in item.data.xpath('//h:span[@class="koboSpan"]',
                                     namespaces={'h': XHTML_NS}):
                refactor_span(a)

        log("KEPUBInput::postprocess_book - end")

    def process_encryption(self, encfile, opf, log):
        # Shouldn't get called, but overriding just in case.
        encfile = os.path.abspath('rights.xml')
        return not os.path.exists(encfile)
