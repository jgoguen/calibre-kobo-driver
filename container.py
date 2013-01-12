#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'MIT'
__copyright__ = '2012, Joel Goguen <jgoguen@jgoguen.ca>'
__docformat__ = 'markdown en'

import os
import tempfile
import zipfile

from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.chardet import strip_encoding_declarations
from calibre.ebooks.epub.fix.container import Container as _Container
from calibre.libunzip import extract
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import Log
from lxml import etree

HTML_EXTENSIONS = ['.htm', '.html', '.xhtml']
EXCLUDE_FROM_ZIP = ['mimetype', '.DS_Store', 'thumbs.db', '.directory']

class Container(_Container):
	"""An extension of the standard Calibre ePub Container class to
	allow easier listing of only desired files.
	"""

	data_map = {}

	def __init__(self, path):
		tmpdir = PersistentTemporaryDirectory("_kobo-driver-extended")
		extract(path, tmpdir)
		super(Container, self).__init__(tmpdir, Log())

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
		data = strip_encoding_declarations(data)
		ext = name[name.rfind('.'):]
		if ext in HTML_EXTENSIONS:
			return etree.fromstring(data, parser = etree.HTMLParser())
		else:
			return etree.fromstring(data)

	def set(self, name, val):
		data = val
		if hasattr(data, 'xpath'):
			data = etree.tostring(data, encoding = "UTF-8")
		super(Container, self).set(name, val)

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
		debug_print("Container:write:In directory {0}".format(os.getcwdu()))
		epub.writestr('mimetype', bytes('application/epub+zip'), compress_type = zipfile.ZIP_STORED)
		zip_prefix = self.root
		if not zip_prefix.endswith(os.sep):
			zip_prefix += os.sep
		debug_print("Container:write:ZIP file contents prefix - {0}".format(zip_prefix))
		for t in os.walk(self.root, topdown = True):
			for f in t[2]:
				if f not in EXCLUDE_FROM_ZIP:
					debug_print("Container:write:Adding file {0} from directory {1}".format(f, t[0]))
					filepath = os.path.join(t[0], f).replace(zip_prefix, '')
					debug_print("Container:write:Resolved file path {0}".format(filepath))
					epub.write(filepath, compress_type = zipfile.ZIP_DEFLATED)
		epub.close()
		os.chdir(cwd)
