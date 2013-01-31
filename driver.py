#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2012, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

import os
import re
import sqlite3 as sqlite

from calibre.devices.kobo.driver import KOBOTOUCH
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.metadata import authors_to_string
from calibre_plugins.kobotouch_extended.container import Container

from copy import deepcopy
from datetime import datetime
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
		for node in opf.xpath('./ns:manifest/ns:item[@id="cover"]', namespaces = {"ns": container.opf_ns}):
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

		if opts.extra_customization[self.OPT_EXTRA_FEATURES]:
			include_images = opts.extra_customization[self.OPT_UPLOAD_COVERS] or opts.extra_customization[self.OPT_ALWAYS_UPLOAD_COVERS]
			db = sqlite.connect(os.path.join(self._main_prefix, ".kobo", "KoboReader.sqlite"), isolation_level = None)
			db.text_factory = lambda x: unicode(x, "utf-8", "ignore")

			if opts.extra_customization[self.OPT_UPDATE_SERIES_DETAILS] and self.supports_series():
				add_content_query = "INSERT INTO content (ContentID, ContentType, MimeType, BookID, BookTitle, ImageId, Title, Attribution, Description, adobe_location, IsEncrypted, FirstTimeReading, ChapterIDBookmarked, " + \
				"NumShortcovers, VolumeIndex, ___NumPages, ___FileSize, Accessibility, ___UserID, Publisher, ParagraphBookmarked, BookmarkWordOffset, ___SyncTime, ReadStatus, ___PercentRead, IsDownloaded, Depth, " + \
				"InWishlist, WishlistedDate, FeedbackTypeSynced, IsSocialEnabled, Language, ___ExpirationStatus, Series, SeriesNumber) VALUES " + \
				"(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'true', ?, " + \
				"?, ?, 0, ?, -1, ?, ?, 0, 0, ?, 0, 0, 'true', 0, " + \
				"'false', '', 48, 'true', ?, 0, ?, ?)"
			else:
				add_content_query = "INSERT INTO content (ContentID, ContentType, MimeType, BookID, BookTitle, ImageId, Title, Attribution, Description, adobe_location, IsEncrypted, FirstTimeReading, ChapterIDBookmarked, " + \
				"NumShortcovers, VolumeIndex, ___NumPages, ___FileSize, Accessibility, ___UserID, Publisher, ParagraphBookmarked, BookmarkWordOffset, ___SyncTime, ReadStatus, ___PercentRead, IsDownloaded, Depth, " + \
				"InWishlist, WishlistedDate, FeedbackTypeSynced, IsSocialEnabled, Language, ___ExpirationStatus) VALUES " + \
				"(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'true', ?, " + \
				"?, ?, 0, ?, -1, ?, ?, 0, 0, ?, 0, 0, 'true', 0, " + \
				"'false', '', 48, 'true', ?, 0)"
			add_shortcover_query = "INSERT INTO volume_shortcovers (volumeId, shortcoverId, VolumeIndex) VALUES (?, ?, ?)"
			for path, card in result:
				ext = path[path.rfind('.'):]
				if ext != '.epub':
					continue
				epub = None
				cursor = None
				try:
					# Begin the transaction for the entire book
					cursor = db.cursor()
					cursor.execute("BEGIN TRANSACTION")

					epub_uri = self.contentid_from_path(path, 6)
					epub_path = re.sub(r'^file\:\/\/', '', epub_uri)
					debug_print("KoboTouchExtended:upload_books:URI - {0}".format(epub_uri))
					debug_print("KoboTouchExtended:upload_books:Path - {0}".format(epub_path))
					epub = Container(path)

					metadata = self.metadata_from_path(path)

					# Create the internal content rows
					debug_print("KoboTouchExtended:upload_books:Parsing OPF file {0}".format(epub.opf_file))
					opf = epub.get_parsed(epub.opf_file)
					opf_path_prefix = ""
					idx = epub.opf_file.rfind('/')
					if idx > -1:
						opf_path_prefix = epub.opf_file[:idx]
					content_id_to_href_map = {}
					ncx_path = None
					for node in opf.xpath('./ns:manifest/ns:item[@id and @href]', namespaces = {"ns": epub.opf_ns}):
						content_id_to_href_map[node.attrib["id"]] = node.attrib["href"]
						debug_print("KoboTouchExtended:upload_books:Adding content ID {0} -> {1}".format(node.attrib["id"], content_id_to_href_map[node.attrib["id"]]))
						if node.attrib["media-type"] == epub.ncx_mime_type:
							ncx_path = "{0}/{1}".format(opf_path_prefix, node.attrib["href"])
							debug_print("KoboTouchExtended:upload_books:Found NCX file {0}".format(ncx_path))

					# Add general content entries
					num_rows = 0
					for id in opf.xpath('./ns:spine[@toc="ncx"]/ns:itemref[@idref]/@idref', namespaces = {"ns": epub.opf_ns}):
						if opts.extra_customization[self.OPT_UPDATE_SERIES_DETAILS] and self.supports_series():
							t = ("{0}!{1}!{2}".format(epub_path, opf_path_prefix, content_id_to_href_map[id]), self.content_types["content"], self.kobo_epub_mime_type, epub_uri, metadata.title, "", content_id_to_href_map[id], "", "", "", "false", "",
								"", num_rows, 0, "", "", "",
								"", "", "")
						else:
							t = ("{0}!{1}!{2}".format(epub_path, opf_path_prefix, content_id_to_href_map[id]), self.content_types["content"], self.kobo_epub_mime_type, epub_uri, metadata.title, "", content_id_to_href_map[id], "", "", "", "false", "",
								"", num_rows, 0, "", "", "",
								"")
						cursor.execute(add_content_query, t)
						t = (epub_uri, "{0}!{1}!{2}".format(epub_path, opf_path_prefix, content_id_to_href_map[id]), num_rows)
						cursor.execute(add_shortcover_query, t)
						num_rows += 1
						debug_print("KoboTouchExtended:upload_books:Inserting new database row for ContentID = {0}, Title = {1}".format("{0}!{1}!{2}".format(epub_path, opf_path_prefix, content_id_to_href_map[id]), content_id_to_href_map[id]))

					# Find the language
					lang = opf.xpath('./ns:metadata/dc:language/text()', namespaces = {"ns": epub.opf_ns, "dc": epub.dc_ns})
					if len(lang) > 0:
						lang = lang[0]
					else:
						lang = "en"

					# Add TOC entries
					if ncx_path is not None:
						debug_print("KoboTouchExtended:upload_books:Parsing NCX file {0}".format(ncx_path))
						ncx = epub.get_parsed(ncx_path)
						hrefs = ncx.xpath('./ns:navMap/ns:navPoint/ns:content[@src]/@src', namespaces = {"ns": epub.ncx_ns})
						titles = ncx.xpath('./ns:navMap/ns:navPoint/ns:navLabel/ns:text/text()', namespaces = {"ns": epub.ncx_ns})
						for idx in range(len(hrefs)):
							if opts.extra_customization[self.OPT_UPDATE_SERIES_DETAILS] and self.supports_series():
								t = ("{0}!{1}!{2}-1".format(epub_path, opf_path_prefix, hrefs[idx]), self.content_types["toc"], self.kobo_epub_mime_type, epub_uri, metadata.title, "", titles[idx], "", "", "", "false", "{0}!{1}!{2}".format(epub_path, opf_path_prefix, hrefs[idx]),
									"", idx, 0, "", "", "",
									"", "", "")
							else:
								t = ("{0}!{1}!{2}-1".format(epub_path, opf_path_prefix, hrefs[idx]), self.content_types["toc"], self.kobo_epub_mime_type, epub_uri, metadata.title, "", titles[idx], "", "", "", "false", "{0}!{1}!{2}".format(epub_path, opf_path_prefix, hrefs[idx]),
									"", idx, 0, "", "", "",
									"")
							cursor.execute(add_content_query, t)
							debug_print("KoboTouchExtended:upload_books:Inserting new database row for TOC ContentID = {0} Title = {1}".format("{0}!{1}!{2}-1".format(epub_path, opf_path_prefix, hrefs[idx]), titles[idx]))

					# Create the main kepub entry
					if opts.extra_customization[self.OPT_UPDATE_SERIES_DETAILS] and self.supports_series():
						t = (epub_uri, self.content_types["main"], self.kobo_epub_mime_type, "", "", self.imageid_from_contentid(epub_uri) if include_images else "", metadata.title, authors_to_string(metadata.authors).split(' & ')[0].strip(), metadata.comments, epub_path, "true", "",
							num_rows, 0, os.path.getsize(path), "kobo_user", metadata.publisher, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
							lang, metadata.series, metadata.format_series_index())
					else:
						t = (epub_uri, self.content_types["main"], self.kobo_epub_mime_type, "", "", self.imageid_from_contentid(epub_uri) if include_images else "", metadata.title, authors_to_string(metadata.authors).split(' & ')[0].strip(), metadata.comments, epub_path, "true", "",
							num_rows, 0, os.path.getsize(path), "kobo_user", metadata.publisher, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
							lang)
					cursor.execute(add_content_query, t)
					debug_print("KoboTouchExtended:upload_books:Inserting new database row for ePub file {0}, ImageID = {1}".format(path, self.imageid_from_contentid(epub_uri)))

					# Commit the transaction and close the cursor.
					# MAKE SURE THIS IS AFTER ALL THE BOOK INSERTIONS ARE DONE
					cursor.execute("COMMIT TRANSACTION")
					cursor.close()
				except Exception as e:
					debug_print("KoboTouchExtended:upload_books:ERROR:{0}".format(e.message))
					if cursor:
						cursor.execute("ROLLBACK TRANSACTION")
						cursor.close()
					raise
			db.close()

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
