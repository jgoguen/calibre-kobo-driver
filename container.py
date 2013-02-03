#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2012, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

import os
import tempfile
import time
import zipfile

from calibre import isbytestring
from calibre.constants import filesystem_encoding
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.chardet import strip_encoding_declarations
from calibre.ebooks.epub.fix.container import Container as _Container
from calibre.libunzip import extract
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import Log
from calibre.utils.unsmarten import unsmarten_text
from lxml import etree

HTML_EXTENSIONS = ['.htm', '.html', '.xhtml']
EXCLUDE_FROM_ZIP = ['mimetype', '.DS_Store', 'thumbs.db', '.directory']

class Container(_Container):
	"""An extension of the standard Calibre ePub Container class to
	allow easier listing of only desired files.
	"""

	opf_mime_type = 'application/oebps-package+xml'
	opf_ns = "http://www.idpf.org/2007/opf"
	container_ns = "urn:oasis:names:tc:opendocument:xmlns:container"
	ncx_mime_type = "application/x-dtbncx+xml"
	ncx_ns = "http://www.daisy.org/z3986/2005/ncx/"
	dc_ns = "http://purl.org/dc/elements/1.1/"

	data_map = {}
	opf_file = None

	def __init__(self, path):
		tmpdir = PersistentTemporaryDirectory("_kobo-driver-extended")
		extract(path, tmpdir)
		super(Container, self).__init__(tmpdir, Log())
		container = self.get_parsed('META-INF/container.xml')
		self.opf_file = container.xpath('./ns:rootfiles/ns:rootfile/@full-path', namespaces = {"ns": self.container_ns})[0]
		debug_print("Container:__init__:OPF file - {0}".format(self.opf_file))

	def get_html_names(self):
		"""A generator function that yields only HTML file names from
		the ePub.
		"""
		for name in self.name_map.keys():
			ext = name[name.lower().rfind('.'):].lower()
			if ext in HTML_EXTENSIONS:
				yield name

	def is_drm_encrypted(self):
		"""Determine if the ePub container is encumbered with Digital
		Restrictions Management.

		This method looks for the 'encryption.xml' file which denotes an
		ePub encumbered by Digital Restrictions Management. DRM-encumbered
		files cannot be edited.
		"""
		for name in self.name_map:
			if name.lower().endswith('encryption.xml'):
				try:
					xml = self.get_raw(name)
					root = etree.fromstring(xml)
					for elem in root.xpath('.//*[contains(name(), "EncryptionMethod")]'):
						alg = elem.get('Algorithm')
						return alg != 'http://ns.adobe.com/pdf/enc#RC'
				except:
					self.log.error("Could not parse encryption.xml")
					return True # If encryption.xml is present, assume the file is encumbered
		return False

	def get_parsed(self, name):
		"""Get the named resource parsed with etree.

		Parses the named resource with lxml.etree and returns the
		resulting Element. Returns None if the named resource doesn't
		exist.
		"""
		if not name or name not in self.name_map:
			return None
		data = self.get_raw(name)
		if not data:
			return None
		try:
			if isbytestring(data):
				data = data.decode(filesystem_encoding)
			data = strip_encoding_declarations(data)
		except UnicodeDecodeError as ude:
			# With the decoding based on the filesystem encoding, I'm not expecting this to actually happen now, but you never know...
			debug_print("Container:get_parsed:Error decoding data with {0} codec, removing 'smart' punctuation and trying again".format(filesystem_encoding))
			data = unsmarten_text(data)
			if isbytestring(data):
				data = data.decode(filesystem_encoding)
			data = strip_encoding_declarations(data)
		ext = name[name.rfind('.'):]
		if ext in HTML_EXTENSIONS:
			return etree.fromstring(data, parser = etree.HTMLParser())
		else:
			return etree.fromstring(data)

	def write(self, path):
		"""Overridden to not use add_dir and to exclude OS special files.
		"""
		for name in self.dirtied:
			data = self.cache[name]
			if hasattr(data, 'xpath'):
				data = etree.tostring(data, encoding = 'UTF-8', xml_declaration = True, pretty_print = True)
			f = open(self.name_map[name], 'wb')
			f.write(data)
			f.close()
		self.dirtied.clear()
		if os.path.exists(path):
			os.unlink(path)
		epub = zipfile.ZipFile(path, 'w')
		cwd = os.getcwdu()
		os.chdir(self.root)
		epub.writestr('mimetype', bytes('application/epub+zip'), compress_type = zipfile.ZIP_STORED)
		zip_prefix = self.root
		if not zip_prefix.endswith(os.sep):
			zip_prefix += os.sep
		for t in os.walk(self.root, topdown = True):
			for f in t[2]:
				if f not in EXCLUDE_FROM_ZIP:
					filepath = os.path.join(t[0], f).replace(zip_prefix, '')
					debug_print("Container:write:Adding file {0}".format(filepath))
					st = os.stat(filepath)
					mtime = time.localtime(st.st_mtime)
					if mtime[0] < 1980:
						debug_print("Container:write:File mtime is before 1980 ({0}-{1}-{2}), updating to current time.".format(mtime[:3]))
						os.utime(filepath, None)
						st = os.stat(filepath)
						mtime = time.localtime(st.st_mtime)
					epub.write(filepath, compress_type = zipfile.ZIP_DEFLATED)
		epub.close()
		os.chdir(cwd)
