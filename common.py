# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2013, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

# Be careful editing this! This file has to work in two different packages at once,
# so don't import anything from calibre_plugins.kobotouch_extended or
# calibre_plugins.kepubout or calibre_plugins.kepubin

import os
import re

from calibre.constants import config_dir
from calibre.ebooks.metadata.book.base import NULL_VALUES
from calibre.ebooks.oeb.polish.container import OPF_NAMESPACES
from calibre.ebooks.oeb.polish.container import EpubContainer
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.logging import default_log

kobo_js_re = re.compile(r'.*/?kobo.*\.js$', re.IGNORECASE)
XML_NAMESPACE = 'http://www.w3.org/XML/1998/namespace'
configdir = os.path.join(config_dir, 'plugins')
reference_kepub = os.path.join(configdir, 'reference.kepub.epub')
plugin_version = (2, 5, 3)
plugin_minimum_calibre_version = (1, 3, 0)


# The logic here to detect a cover image is mostly duplicated from
# metadata/writer.py. Updates to the logic here probably need an accompanying
# update over there.
def modify_epub(container, filename, metadata=None, opts={}):
    print(str(opts))
    # Search for the ePub cover
    found_cover = False
    opf = container.opf
    cover_meta_node = opf.xpath('./opf:metadata/opf:meta[@name="cover"]', namespaces=OPF_NAMESPACES)
    if len(cover_meta_node) > 0:
        cover_meta_node = cover_meta_node[0]
        cover_id = cover_meta_node.attrib["content"] if "content" in cover_meta_node.attrib else None
        if cover_id is not None:
            print("KoboTouchExtended:common:modify_epub:Found cover image ID '{0}'".format(cover_id))
            cover_node = opf.xpath('./opf:manifest/opf:item[@id="{0}"]'.format(cover_id), namespaces=OPF_NAMESPACES)
            if len(cover_node) > 0:
                cover_node = cover_node[0]
                if "properties" not in cover_node.attrib or cover_node.attrib["properties"] != "cover-image":
                    print("KoboTouchExtended:common:modify_epub:Setting cover-image property")
                    cover_node.set("properties", "cover-image")
                    container.dirty(container.opf_name)
                    found_cover = True
    # It's possible that the cover image can't be detected this way. Try looking for the cover image ID in the OPF manifest.
    if not found_cover:
        print("KoboTouchExtended:common:modify_epub:Looking for cover image in OPF manifest")
        node_list = opf.xpath('./opf:manifest/opf:item[(translate(@id, \'ABCDEFGHIJKLMNOPQRSTUVWXYZ\', \'abcdefghijklmnopqrstuvwxyz\')="cover" or starts-with(translate(@id, \'ABCDEFGHIJKLMNOPQRSTUVWXYZ\', \'abcdefghijklmnopqrstuvwxyz\'), "cover")) and starts-with(@media-type, "image")]', namespaces=OPF_NAMESPACES)
        if len(node_list) > 0:
            node = node_list[0]
            if "properties" not in node.attrib or node.attrib["properties"] != 'cover-image':
                print("KoboTouchExtended:common:modify_epub:Setting cover-image")
                node.set("properties", "cover-image")
                container.dirty(container.opf_name)
                found_cover = True

    # Because of the changes made to the markup here, cleanup needs to be done before any other content file processing
    container.forced_cleanup()
    if 'clean_markup' in opts and opts['clean_markup'] is True:
        container.clean_markup()

    # Hyphenate files?
    if 'no-hyphens' in opts and opts['no-hyphens'] is True:
        nohyphen_css = PersistentTemporaryFile(suffix="_nohyphen", prefix="kepub_")
        nohyphen_css.write(get_resources("css/no-hyphens.css"))
        nohyphen_css.close()
        css_path = os.path.basename(container.copy_file_to_container(nohyphen_css.name, name='kte-css/no-hyphens.css'))
        container.add_content_file_reference("kte-css/{0}".format(css_path))
    elif 'hyphenate' in opts and opts['hyphenate'] is True:
        if ('replace_lang' not in opts or opts['replace_lang'] is not True) or (metadata is not None and metadata.language == NULL_VALUES['language']):
            print("KoboTouchExtended:common:modify_epub:WARNING - Hyphenation is enabled but not overriding content file language. Hyphenation may use the wrong dictionary.")
        hyphenation_css = PersistentTemporaryFile(suffix='_hyphenate', prefix='kepub_')
        hyphenation_css.write(get_resources('css/hyphenation.css'))
        hyphenation_css.close()
        css_path = os.path.basename(container.copy_file_to_container(hyphenation_css.name, name='kte-css/hyphenation.css'))
        container.add_content_file_reference("kte-css/{0}".format(css_path))

    # Override content file language
    if 'replace_lang' in opts and opts['replace_lang'] is True and (metadata is not None and metadata.language != NULL_VALUES["language"]):
        # First override for the OPF file
        lang_node = container.opf_xpath('//opf:metadata/dc:language')
        if len(lang_node) > 0:
            print("KoboTouchExtended:common:modify_epub:Overriding OPF language")
            lang_node = lang_node[0]
            lang_node.text = metadata.language
        else:
            print("KoboTouchExtended:common:modify_epub:Setting OPF language")
            metadata_node = container.opf_xpath('//opf:metadata')[0]
            lang_node = metadata_node.makeelement("{%s}language" % OPF_NAMESPACES['dc'])
            lang_node.text = metadata.language
            container.insert_into_xml(metadata_node, lang_node)
        container.dirty(container.opf_name)

        # Now override for content files
        for name in container.get_html_names():
            print("KoboTouchExtended:common:modify_epub:Overriding content file language :: {0}".format(name))
            root = container.parsed(name)
            root.attrib["{%s}lang" % XML_NAMESPACE] = metadata.language
            root.attrib["lang"] = metadata.language

    # Now smarten punctuation
    if 'smarten_punctuation' in opts and opts['smarten_punctuation'] is True:
        container.smarten_punctuation()

    if 'extended_kepub_features' in opts and opts['extended_kepub_features'] is True:
        if metadata is not None:
            print("KoboTouchExtended:common:modify_epub:Adding extended Kobo features to {0} by {1}".format(metadata.title, ' and '.join(metadata.authors)))
        # Add the Kobo span tags
        container.add_kobo_spans()
        # Add the Kobo style hacks div tags
        container.add_kobo_divs()

        skip_js = False
        # Check to see if there's already a kobo*.js in the ePub
        for name in container.name_path_map:
            if kobo_js_re.match(name):
                skip_js = True
                break
        if not skip_js:
            if os.path.isfile(reference_kepub):
                reference_container = EpubContainer(reference_kepub, default_log)
                for name in reference_container.name_path_map:
                    if kobo_js_re.match(name):
                        jsname = container.copy_file_to_container(os.path.join(reference_container.root, name), name='kobo.js')
                        container.add_content_file_reference(jsname)
                        break

        # Add the Kobo style hacks
        stylehacks_css = PersistentTemporaryFile(suffix='_stylehacks', prefix='kepub_')
        stylehacks_css.write(get_resources('css/style-hacks.css'))
        stylehacks_css.close()
        css_path = os.path.basename(container.copy_file_to_container(stylehacks_css.name, name='kte-css/stylehacks.css'))
        container.add_content_file_reference("kte-css/{0}".format(css_path))
    os.unlink(filename)
    container.commit(filename)
