# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2013, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

import json
import os

from calibre.constants import config_dir
from calibre.customize.conversion import OutputFormatPlugin
from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.conversion.plugins.epub_output import EPUBOutput
from calibre.ebooks.metadata.book.base import NULL_VALUES
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.logging import default_log
from calibre_plugins.koboconversion.common import modify_epub
from calibre_plugins.koboconversion.container import KEPubContainer
from datetime import datetime

class KEPubOutput(OutputFormatPlugin):
    name = 'KePub Output'
    author = 'Joel Goguen'
    file_type = 'kepub'
    version = (2, 2, 1)
    minimum_calibre_version = (0, 9, 42)

    epub_output_plugin = None
    configdir = os.path.join(config_dir, 'plugins')
    reference_kepub = os.path.join(configdir, 'reference.kepub.epub')
    options = set([
                   OptionRecommendation(name='opt_kepub_enable_extended_features', recommended_value=True, level=OptionRecommendation.HIGH,
                                        help='Choose whether to enable extra customisations'),
                   OptionRecommendation(name='opt_kepub_hyphenate', recommended_value=True,
                                 level=OptionRecommendation.MED,
                                 help='Select this to add a CSS file which enables hyphenation. '
                                 'The language used will be the language defined for the book in '
                                 'calibre. Please see the README file for directions on updating '
                                 'hyphenation dictionaries.'),
                   OptionRecommendation(name='opt_kepub_replace_lang', recommended_value=True,
                                 level=OptionRecommendation.LOW,
                                 help='Select this to replace the defined language in each '
                                 'content file inside the ePub.'),
                   OptionRecommendation(name='opt_kepub_clean_markup', recommended_value=True,
                                 level=OptionRecommendation.MED,
                                 help='Select this to clean up the internal ePub markup.')
    ])
    recommendations = set([
                           ('opt_kepub_enable_extended_features', True, OptionRecommendation.HIGH),
                           ('opt_kepub_hyphenate', True, OptionRecommendation.MED),
                           ('opt_kepub_replace_lang', True, OptionRecommendation.LOW),
                           ('opt_kepub_clean_markup', True, OptionRecommendation.MED)
    ])

    def __init__(self, *args, **kwargs):
        self.epub_output_plugin = EPUBOutput(*args, **kwargs)
        self.options = self.options.union(self.epub_output_plugin.options)
        self.recommendations = self.recommendations.union(self.epub_output_plugin.recommendations)
        OutputFormatPlugin.__init__(self, *args, **kwargs)

    def gui_configuration_widget(self, parent, get_option_by_name, get_option_help, db, book_id=None):
        from calibre_plugins.koboconversion.conversion.config import PluginWidget
        return PluginWidget(parent, get_option_by_name, get_option_help, db, book_id)

    def convert(self, oeb_book, output, input_plugin, opts, log):
        self.epub_output_plugin.convert(oeb_book, output, input_plugin, opts, log)
        container = KEPubContainer(output, default_log)

        if container.is_drm_encumbered:
            return

        # Write the details file
        o = {
             'kepub_output_version': ".".join([str(n) for n in self.version]),
             'kepub_output_currenttime': datetime.utcnow().ctime()
        }
        kte_data_file = self.temporary_file('_KePubOutputPluginInfo')
        kte_data_file.write(json.dumps(o))
        kte_data_file.close()
        container.copy_file_to_container(kte_data_file.name, name='plugininfo.kte', mt='application/json')

        title = container.opf_xpath("./opf:metadata/dc:title/text()")
        if len(title) > 0:
            title = title[0]
        else:
            title = NULL_VALUES['title']
        authors = container.opf_xpath('./opf:metadata/dc:creator[@opf:role="aut"]/text()')
        if len(authors) < 1:
            authors = NULL_VALUES['authors']
        mi = Metadata(title, authors)
        language = container.opf_xpath("./opf:metadata/dc:language/text()")
        if len(language) > 0:
            mi.languages = language
            language = language[0]
        else:
            mi.languages = NULL_VALUES['languages']
            language = NULL_VALUES['language']
        mi.language

        modify_epub(container, output, metadata=mi, opts={
                                                    'clean_markup': opts.opt_kepub_clean_markup,
                                                    'hyphenate': opts.opt_kepub_hyphenate,
                                                    'replace_lang': opts.opt_kepub_replace_lang,
                                                    'smarten_punctuation': False,
                                                    'extended_kepub_features': opts.opt_kepub_enable_extended_features
        })
