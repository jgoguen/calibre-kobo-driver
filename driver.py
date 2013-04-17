#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2012, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

import os
import sqlite3 as sqlite
import sys

from calibre.constants import config_dir
from calibre.devices.kobo.driver import KOBOTOUCH
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.metadata.book.base import NULL_VALUES
from calibre_plugins.kobotouch_extended.container import Container

from copy import deepcopy
from hyphenator import Hyphenator
from lxml import etree

EPUB_EXT = '.epub'

class DRMEncumberedEPub(ValueError):
	def __init__(self, name, author):
		self.name = name
		self.author = author
		ValueError.__init__(self, _("ePub '{0}' by '{1}' is encumbered by DRM").format(name, author))

class InvalidEPub(ValueError):
	def __init__(self, name, author, message, fname = None, lineno = None):
		self.name = name
		self.author = author
		self.message = message
		self.fname = fname
		self.lineno = lineno
		ValueError.__init__(self, _("Failed to parse '{0}' by '{1}' with error: '{2}' (file: {3}, line: {4})".format(name, author, message, fname, lineno)))

class KOBOTOUCHEXTENDED(KOBOTOUCH):
	'''Extended driver for Kobo Touch, Kobo Glo, and Kobo Mini devices.

	This driver automatically modifies ePub files to include extra information
	used by Kobo devices to enable annotations and display of chapter names and
	page numbers on a per-chapter basis. Files are also transferred using the
	'kepub' designation ({name}.kepub.{ext}) automatically to trigger the Kobo
	device to enable these features. This also enabled more detailed reading
	statistics accessible within each book.
	'''

	name = 'KoboTouchExtended'
	gui_name = 'Kobo Touch/Glo/Mini'
	author = 'Joel Goguen'
	description = 'Communicate with the Kobo Touch, Glo, and Mini firmwares and enable extended Kobo ePub features.'
	configdir = os.path.join(config_dir, 'plugins', 'KoboTouchExtended')

	minimum_calibre_version = (0, 9, 25)
	version = (1, 2, 6)

	content_types = {
		"main": 6,
		"content": 9,
		"toc": 899
	}

	supported_dbversion = 77
	min_supported_dbversion = 65

	EXTRA_CUSTOMIZATION_MESSAGE = [
		_('The Kobo Touch from firmware V2.0.0 supports bookshelves.') + \
					'These are created on the Kobo Touch. ' + \
					_('Specify a tags type column for automatic management'),
			_('Create Bookshelves') +
			':::' + _('Create new bookshelves on the Kobo Touch if they do not exist. This is only for firmware V2.0.0 or later.'),
			_('Delete Empty Bookshelves') +
			':::' + _('Delete any empty bookshelves from the Kobo Touch when syncing is finished. This is only for firmware V2.0.0 or later.'),
			_('Upload covers for books') +
			':::' + _('Upload cover images from the calibre library when sending books to the device.'),
			_('Upload Black and White Covers'),
			_('Keep cover aspect ratio') +
			':::' + _('When uploading covers, do not change the aspect ratio when resizing for the device.'
					' This is for firmware versions 2.3.1 and later.'),
			_('Show expired books') +
			':::' + _('A bug in an earlier version left non kepubs book records'
				' in the database.  With this option Calibre will show the '
				'expired records and allow you to delete them with '
				'the new delete logic.'),
			_('Show Previews') +
			':::' + _('Kobo previews are included on the Touch and some other versions'
				' by default they are no longer displayed as there is no good reason to '
				'see them.  Enable if you wish to see/delete them.'),
			_('Show Recommendations') +
			':::' + _('Kobo shows recommendations on the device.  In some cases these have '
				'files but in other cases they are just pointers to the web site to buy. '
				'Enable if you wish to see/delete them.'),
			_('Set Series information') +
			':::' + _('The book lists on the Kobo devices can display series information. '
					'This is not read by the device from the sideloaded books. '
					'Series information can only be added to the device after the book has been processed by the device. '
					'Enable if you wish to set series information.'),
			_('Attempt to support newer firmware') +
			':::' + _('Kobo routinely updates the firmware and the '
				'database version.  With this option Calibre will attempt '
				'to perform full read-write functionality - Here be Dragons!! '
				'Enable only if you are comfortable with restoring your kobo '
				'to factory defaults and testing software. '
				'This driver supports firmware V2.x.x and DBVersion up to ' + unicode(supported_dbversion)),
			_('Title to test when debugging') +
			':::' + _('Part of title of a book that can be used when doing some tests for debugging. '
					'The test is to see if the string is contained in the title of a book. '
					'The better the match, the less extraneous output.'),
		_('Enable Extended Features') + \
			':::' + _('Choose whether to enable extra customisations'),
		_('Delete Files not in Manifest') + \
			':::' + _('Select this to silently delete files that are not in the manifest if they are encountered during processing. '
				'If this option is not selected, files not in the manifest will be silently added to the manifest and processed as if they always were in the manifest.'),
		_('Upload DRM-encumbered ePub files') + \
			':::' + _('Select this to upload ePub files encumbered by DRM. If this is not selected, it is a fatal error to upload an encumbered file'),
		_('Silently Ignore Failed Conversions') + \
			':::' + _('Select this to not upload any book that fails conversion to kepub. If this is not selected, the upload process '
				'will be stopped at the first book that fails. If this is selected, failed books will be silently removed from the upload queue.'),
		_('Hyphenate Files') + \
			':::' + _('Select this to add soft hyphens to uploaded ePub files. The language used will be the language defined for the book in calibre. '
				' It is necessary to have a LibreOffice/OpenOffice hyphenation dictionary in ' + os.path.join(config_dir, 'plugins', 'KoboTouchExtended') + \
				' named like hyph_{language}.dic, where {language} is the ISO 639 3-letter language code. For example, \'eng\' but not \'en_CA\'. The default dictionary to use '
				' if none is found may be named \'hyph.dic\' instead.'),
		_('Replace Content Language Code') + \
			':::' + _('Select this to replace the defined language in each content file inside the ePub.')
	]

	EXTRA_CUSTOMIZATION_DEFAULT = [
		u'',
		False,
		False,
		False,
		False,
		False,
		False,
		False,
		False,
		False,
		False,
		u'',
		True,
		False,
		False,
		False,
		False,
		False
	]

	OPT_COLLECTIONS = 0
	OPT_CREATE_BOOKSHELVES = 1
	OPT_DELETE_BOOKSHELVES = 2
	OPT_UPLOAD_COVERS = 3
	OPT_UPLOAD_GRAYSCALE_COVERS = 4
	OPT_KEEP_COVER_ASPECT_RATIO = 5
	OPT_SHOW_EXPIRED_BOOK_RECORDS = 6
	OPT_SHOW_PREVIEWS = 7
	OPT_SHOW_RECOMMENDATIONS = 8
	OPT_UPDATE_SERIES_DETAILS = 9
	OPT_SUPPORT_NEWER_FIRMWARE = 10
	OPT_DEBUGGING_TITLE = 11
	OPT_EXTRA_FEATURES = 12
	OPT_DELETE_UNMANIFESTED = 13
	OPT_UPLOAD_ENCUMBERED = 14
	OPT_SKIP_FAILED = 15
	OPT_HYPHENATE = 16
	OPT_REPLACE_LANG = 17

	skip_renaming_files = []

	hyphenator = None

	def initialize(self):
		if not os.path.isdir(self.configdir):
			os.makedirs(self.configdir)

		super(KOBOTOUCHEXTENDED, self).initialize()

	def _hyphenate_node(self, elem, hyphenator, hyphen = u'\u00AD'):
		if isinstance(elem, basestring):
			newstr = []
			for w in elem.split():
				if '-' not in w and hyphen not in w:
					w = hyphenator.inserted(w, hyphen = hyphen)
				newstr.append(w)
			return " ".join(newstr)
		if elem is not None:
			elem.text = self._hyphenate_node(elem.text, hyphenator)
			elem.tail = self._hyphenate_node(elem.tail, hyphenator)
		return elem


	def _modify_epub(self, file, metadata):
		opts = self.settings()
		debug_print("KoboTouchExtended:_modify_epub:Processing {0}".format(metadata.title))

		skip_failed = opts.extra_customization[self.OPT_SKIP_FAILED]
		if skip_failed:
			debug_print("KoboTouchExtended:_modify_epub:Failed conversions will be skipped")
		else:
			debug_print("KoboTouchExtended:_modify_epub:Failed conversions will raise exceptions")

		container = Container(file)
		if container.is_drm_encumbered:
			debug_print("KoboTouchExtended:_modify_epub:ERROR: ePub is DRM-encumbered, not modifying")
			self.skip_renaming_files.append(metadata.uuid)
			if opts.extra_customization[self.OPT_UPLOAD_ENCUMBERED]:
				raise DRMEncumberedEPub(metadata.title, ", ".join(metadata.authors))
			else:
				return False

		found_cover = False
		opf = container.opf
		cover_meta_node = opf.xpath('./opf:metadata/opf:meta[@name="cover"]', namespaces = container.namespaces)
		if len(cover_meta_node) > 0:
			cover_meta_node = cover_meta_node[0]
			cover_id = cover_meta_node.attrib["content"] if "content" in cover_meta_node.attrib else None
			if cover_id is not None:
				debug_print("KoboTouchExtended:_modify_epub:Found cover image id {0}".format(cover_id))
				cover_node = opf.xpath('./opf:manifest/opf:item[@id="{0}"]'.format(cover_id), namespaces = container.namespaces)
				if len(cover_node) > 0:
					cover_node = cover_node[0]
					if "properties" not in cover_node.attrib or cover_node.attrib["properties"] != "cover-image":
						debug_print("KoboTouchExtended:_modify_epub:Setting cover-image")
						cover_node.set("properties", "cover-image")
						container.set(container.opf_name, opf)
						found_cover = True

		# It's possible that the cover image can't be detected this way. Try looking for the cover image ID in the OPF manifest.
		if not found_cover:
			debug_print("KoboTouchExtended:_modify_epub:Looking for cover image in OPF manifest")
			node_list = opf.xpath('./opf:manifest/opf:item[@id="cover" or starts-with(@id, "cover") and not(substring(@id, string-length(@id) - string-length("html") + 1)) and starts-with(@media-type, "image")]', namespaces = container.namespaces)
			if len(node_list) > 0:
				node = node_list[0]
				if "properties" not in node.attrib or node.attrib["properties"] != 'cover-image':
					debug_print("KoboTouchExtended:_modify_epub:Setting cover-image")
					node.set("properties", "cover-image")
					container.set(container.opf_name, opf)

		hyphenator = None
		if opts.extra_customization[self.OPT_HYPHENATE]:
			dictfile = None
			for lang in metadata.languages:
				if lang == 'und':
					continue
				dictfile = os.path.join(self.configdir, "hyph_{0}.dic".format(lang))
				if os.path.isfile(dictfile):
					break
			if dictfile is None or not os.path.isfile(dictfile):
				dictfile = os.path.join(self.configdir, "hyph.dic")
			if dictfile is not None and os.path.isfile(dictfile):
				debug_print("KoboTouchExtended:_modify_epub:Using hyphenation dictionary {0}".format(dictfile))
				hyphenator = Hyphenator(dictfile)

		for name in container.get_html_names():
			debug_print("KoboTouchExtended:_modify_epub:Processing HTML {0}".format(name))
			root = container.get(name)
			if not hasattr(root, 'xpath'):
				if opts.extra_customization[self.OPT_DELETE_UNMANIFESTED]:
					debug_print("KoboTouchExtended:_modify_epub:Removing unmanifested file {0}".format(name))
					os.unlink(os.path.join(container.root, name).replace('/', os.sep))
					continue
				else:
					item = container.manifest_item_for_name(name)
					if item is None:
						debug_print("KoboTouchExtended:_modify_epub:Adding unmanifested item {0} to the manifest".format(name))
						container.add_name_to_manifest(name)
						root = container.get(name)
					if item is not None or not hasattr(root, "xpath"):
						debug_print("KoboTouchExtended:_modify_epub:{0} is not a XML-based format".format(name))
						continue
			count = 0

			if opts.extra_customization[self.OPT_REPLACE_LANG] and metadata.language != NULL_VALUES["language"]:
				root.attrib["{%s}lang" % container.namespaces["xml"]] = metadata.language
				root.attrib["lang"] = metadata.language

			for node in root.xpath('./xhtml:body//xhtml:h1 | ./xhtml:body//xhtml:h2 | ./xhtml:body//xhtml:h3 | ./xhtml:body//xhtml:h4 | ./xhtml:body//xhtml:h5 | ./xhtml:body//xhtml:h6 | ./xhtml:body//xhtml:p', namespaces = container.namespaces):
				children = node.xpath('node()')
				if not len(children):
					node.getparent().remove(node)
					continue
				if not len(node.xpath("./xhtml:span[starts-with(@id, 'kobo.')]", namespaces = {"xhtml": container.namespaces["xhtml"]})):
					count += 1
					attrs = {}
					for key in node.attrib.keys():
						attrs[key] = node.attrib[key]
					new_span = etree.Element("{%s}span" % (container.namespaces["xhtml"],), attrib = {"id": "kobo.{0}.1".format(count), "class": "koboSpan"})
					if isinstance(children[0], basestring):
						new_span.text = unicode(deepcopy(children.pop(0)))
					for child in children:
						if not isinstance(child, basestring):
							new_span.append(deepcopy(child))
					node.clear()
					for key in attrs.keys():
						node.set(key, attrs[key])
					node.append(new_span)

			if count > 0:
				debug_print("KoboTouchExtended:_modify_epub:Added Kobo tags to {0}".format(name))
				container.set(name, root)

			if opts.extra_customization[self.OPT_HYPHENATE] and hyphenator is not None:
				for node in root.xpath("./xhtml:body//xhtml:span[starts-with(@id, 'kobo.')]", namespaces = container.namespaces):
					node = self._hyphenate_node(node, hyphenator)
				container.set(name, root)

		os.unlink(file)
		container.write(file)

		return True

	def upload_books(self, files, names, on_card = None, end_session = True, metadata = None):
		opts = self.settings()
		skip_failed = opts.extra_customization[self.OPT_SKIP_FAILED]
		new_files = []
		new_names = []
		new_metadata = []
		errors = []
		if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
			debug_print("KoboTouchExtended:upload_books:Enabling extra ePub features for Kobo devices")
			i = 0
			for file, n, mi in zip(files, names, metadata):
				self.report_progress(i / float(len(files)), "Processing book: {0} by {1}".format(mi.title, " and ".join(mi.authors)))
				ext = file[file.rfind('.'):]
				if ext == EPUB_EXT:
					try:
						self._modify_epub(file, mi)
					except Exception as e:
						(exc_type, exc_obj, exc_tb) = sys.exc_info()
						if exc_tb.tb_next:
							exc_tb = exc_tb.tb_next
						fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
						if not skip_failed:
							raise InvalidEPub(mi.title, " and ".join(mi.authors), e.message, fname = fname, lineno = exc_tb.tb_lineno)
						else:
							errors.append("Failed to upload {0} with error: {1}".format("'{0}' by '{1}'".format(mi.title, " and ".join(mi.authors)), e.message))
							if mi.uuid not in self.skip_renaming_files:
								self.skip_renaming_files.append(mi.uuid)
							debug_print("Failed to process {0} by {1} with error: {2} (file: {3}, lineno: {4})".format(mi.title, " and ".join(mi.authors), e.message, fname, exc_tb.tb_lineno))
					else:
						new_files.append(file)
						new_names.append(n)
						new_metadata.append(mi)
				else:
					new_files.append(file)
					new_names.append(n)
					new_metadata.append(mi)
				i += 1
		else:
			new_files = files
			new_names = names
			new_metadata = metadata

		if metadata and new_metadata and len(metadata) != len(new_metadata) and len(new_metadata) > 0:
			print("The following books could not be processed and will not be uploaded to your device:")
			print("\n".join(errors))

		self.report_progress(0, 'Working...')
		result = super(KOBOTOUCHEXTENDED, self).upload_books(new_files, new_names, on_card, end_session, new_metadata)

		return result

	def filename_callback(self, path, mi):
		opts = self.settings()
		if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
			debug_print("KoboTouchExtended:filename_callback:Path - {0}".format(path))

			idx = path.rfind('.')
			ext = path[idx:]
			if ext == EPUB_EXT and mi.uuid not in self.skip_renaming_files:
				path = "{0}.kepub{1}".format(path[:idx], EPUB_EXT)
				debug_print("KoboTouchExtended:filename_callback:New path - {0}".format(path))

		return path

	def sanitize_path_components(self, components):
		return [x.replace('!', '_') for x in components]

	def sync_booklists(self, booklists, end_session = True):
		debug_print("KoboTouchExtended:sync_booklists:Setting ImageId fields")

		db = sqlite.connect(os.path.join(self._main_prefix, ".kobo", "KoboReader.sqlite"), isolation_level = None)
		db.text_factory = lambda x: unicode(x, "utf-8", "ignore")

		def _rows_needing_imageid():
			"""A generator function returning a 2-tuple (ImageId, ContentId) for rows
			in the database that require an image ID.
			"""
			c = db.cursor()
			c.execute("SELECT ContentId FROM content WHERE ContentType = ? AND (ImageId IS NULL OR ImageId = '')", (self.content_types["main"],))
			for row in c:
				yield (self.imageid_from_contentid(row[0]), row[0])

		cursor = db.cursor()
		cursor.executemany("UPDATE content SET ImageId = ? WHERE ContentId = ?", _rows_needing_imageid())
		cursor.close()
		db.close()
		debug_print("KoboTouchExtended:sync_booklists:done setting ImageId fields")

		super(KOBOTOUCHEXTENDED, self).sync_booklists(booklists, end_session)
