#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2012, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

import os
import sqlite3 as sqlite

from calibre.devices.kobo.driver import KOBOTOUCH
from calibre.devices.usbms.driver import debug_print
from calibre_plugins.kobotouch_extended.container import Container

from copy import deepcopy
from lxml import etree

EPUB_EXT = '.epub'

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

	content_types = {
		"main": 6,
		"content": 9,
		"toc": 899
	}
	kobo_epub_mime_type = "application/x-kobo-epub+zip"

	supported_dbversion = 75
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
			':::' + _('Normally, the KOBO readers get the cover image from the'
			' ebook file itself. With this option, calibre will send a '
			'separate cover image to the reader, useful if you '
			'have modified the cover.'),
		_('Upload Black and White Covers'),
		_('Always upload covers') +
			':::' + _('If the Upload covers option is selected, the driver will only replace covers already on the device.'
			' Select this option if you want covers uploaded the first time you send the book to the device.'),
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
			':::' + _('Choose whether to enable extra customisations')
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
		True
	]

	OPT_COLLECTIONS = 0
	OPT_CREATE_BOOKSHELVES = 1
	OPT_DELETE_BOOKSHELVES = 2
	OPT_UPLOAD_COVERS = 3
	OPT_UPLOAD_GRAYSCALE_COVERS = 4
	OPT_ALWAYS_UPLOAD_COVERS = 5
	OPT_SHOW_EXPIRED_BOOK_RECORDS = 6
	OPT_SHOW_PREVIEWS = 7
	OPT_SHOW_RECOMMENDATIONS = 8
	OPT_UPDATE_SERIES_DETAILS = 9
	OPT_SUPPORT_NEWER_FIRMWARE = 10
	OPT_DEBUGGING_TITLE = 11
	OPT_EXTRA_FEATURES = 12

	def _modify_epub(self, file):
		debug_print("KoboTouchExtended:_modify_epub:Processing file {0}".format(file))
		changed = False
		container = Container(file)
		if container.is_drm_encrypted():
			debug_print("KoboTouchExtended:_modify_epub:ERROR: ePub is DRM-encrypted, not modifying")
			return False

		opf = container.get_parsed(container.opf_file)
		cover_meta_node = opf.xpath('./ns:metadata/ns:meta[@name="cover"]', namespaces = {"ns": container.opf_ns})
		if len(cover_meta_node) > 0:
			cover_meta_node = cover_meta_node[0]
			cover_id = cover_meta_node.attrib["content"] if "content" in cover_meta_node.attrib else None
			if cover_id is not None:
				debug_print("KoboTouchExtended:_modify_epub:Found cover image id {0}".format(cover_id))
				cover_node = opf.xpath('./ns:manifest/ns:item[@id="{0}"]'.format(cover_id), namespaces = {"ns": container.opf_ns})
				if len(cover_node) > 0:
					cover_node = cover_node[0]
					if "properties" not in cover_node.attrib or cover_node.attrib["properties"] != "cover-image":
						debug_print("KoboTouchExtended:_modify_epub:Setting cover-image")
						cover_node.set("properties", "cover-image")
						container.set(container.opf_file, opf)
						changed = True

		# It's possible that the cover image can't be detected this way. Try looking for the cover image ID in the OPF manifest.
		if not changed:
			debug_print("KoboTouchExtended:_modify_epub:Looking for cover image in OPF manifest")
			for node in opf.xpath('./ns:manifest/ns:item[@id="cover" or starts-with(@id, "cover") and not(substring(@id, string-length(@id) - string-length("html") + 1)) and starts-with(@media-type, "image")]', namespaces = {"ns": container.opf_ns}):
				if "properties" not in node.attrib or node.attrib["properties"] != 'cover-image':
					debug_print("KoboTouchExtended:_modify_epub:Setting cover-image")
					node.set("properties", "cover-image")
					container.set(container.opf_file, opf)
					changed = True

		for name in container.get_html_names():
			debug_print("KoboTouchExtended:_modify_epub:Processing HTML {0}".format(name))
			root = container.get_parsed(name)
			count = 0

			for node in root.xpath('./body//h1 | ./body//h2 | ./body//h3 | ./body//h4 | ./body//h5 | ./body//h6 | ./body//p'):
				children = node.xpath('node()')
				if not len(children):
					node.getparent().remove(node)
					continue
				if not len(node.xpath("./span[starts-with(@id, 'kobo.')]")):
					count += 1
					attrs = {}
					for key in node.attrib.keys():
						attrs[key] = node.attrib[key]
					new_span = etree.Element("span", attrib = {"id": "kobo.{0}.1".format(count), "class": "koboSpan"})
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
				changed = True
				container.set(name, root)
		if changed:
			os.unlink(file)
			container.write(file)
		return changed

	def upload_books(self, files, names, on_card = None, end_session = True, metadata = None):
		opts = self.settings()
		if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
			debug_print("KoboTouchExtended:upload_books:Enabling extra ePub features for Kobo devices")
			for file in files:
				ext = file[file.rfind('.'):]
				if ext == EPUB_EXT:
					self._modify_epub(file)

		result = super(KOBOTOUCHEXTENDED, self).upload_books(files, names, on_card, end_session, metadata)

		return result

	def filename_callback(self, path, mi):
		opts = self.settings()
		if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
			debug_print("KoboTouchExtended:filename_callback:Path - {0}".format(path))

			idx = path.rfind('.')
			ext = path[idx:]
			if ext == EPUB_EXT:
				path = "{0}.kepub{1}".format(path[:idx], EPUB_EXT)
				debug_print("KoboTouchExtended:filename_callback:New path - {0}".format(path))

		return path

	def sync_booklists(self, booklists, end_session = True):
		debug_print("KoboTouchExtended:sync_booklists:Setting ImageId fields")

		db = sqlite.connect(os.path.join(self._main_prefix, ".kobo", "koboreader.sqlite"), isolation_level = None)
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
