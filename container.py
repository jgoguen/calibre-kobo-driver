#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import posixpath
import re
import sys
import tempfile
import time
import urllib
import zipfile

from lxml import etree
from lxml.etree import XMLSyntaxError

from calibre import guess_type
from calibre import prepare_string_for_xml
from calibre.constants import iswindows
from calibre.ebooks.chardet import detect
from calibre.ebooks.chardet import strip_encoding_declarations
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import Log
from calibre.utils.unsmarten import unsmarten_text
from calibre.utils.zipfile import ZipFile
from calibre.utils.zipfile import ZIP_DEFLATED
from calibre.utils.zipfile import ZIP_STORED

exists, join = os.path.exists, os.path.join

HTML_EXTENSIONS = ['.htm', '.html', '.xhtml']
EXCLUDE_FROM_ZIP = ['mimetype', '.DS_Store', 'thumbs.db', '.directory']

class InvalidEpub(ValueError):
	pass

class ParseError(ValueError):

	def __init__(self, name, desc):
		self.name = name
		self.desc = desc
		ValueError.__init__(self, _('Failed to parse: {0} with error: {1}').format(name, desc))

class Container(object):
	META_INF = {
			'container.xml' : True,
			'manifest.xml' : False,
			'encryption.xml' : False,
			'metadata.xml' : False,
			'signatures.xml' : False,
			'rights.xml' : False,
	}

	OCF_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'
	OPF_NS = 'http://www.idpf.org/2007/opf'
	NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
	DC_NS = "http://purl.org/dc/elements/1.1/"
	XHTML_NS = "http://www.w3.org/1999/xhtml"
	OPF_MIMETYPE = 'application/oebps-package+xml'
	NCX_MIMETYPE = "application/x-dtbncx+xml"

	def __init__(self, path):
		tmpdir = PersistentTemporaryDirectory("_kobo-driver-extended")
		zf = zipfile.ZipFile(path)
		zf.extractall(tmpdir)

		self.root = os.path.abspath(tmpdir)
		self.log = Log()
		self.dirtied = set([])
		self.cache = {}
		self.mime_map = {}

		print("Got container path {0}".format(self.root))

		if os.path.exists(os.path.join(self.root, 'mimetype')):
			os.remove(os.path.join(self.root, 'mimetype'))

		container_path = os.path.join(self.root, 'META-INF', 'container.xml')
		if not os.path.exists(container_path):
			raise InvalidEpub('No META-INF/container.xml in epub')
		self.container = etree.fromstring(open(container_path, 'rb').read())
		opf_files = self.container.xpath((r'child::ocf:rootfiles/ocf:rootfile[@media-type="{0}" and @full-path]'.format(guess_type('a.opf')[0])), namespaces = {'ocf': self.OCF_NS})
		if not opf_files:
			raise InvalidEpub('META-INF/container.xml contains no link to OPF file')
		opf_path = os.path.join(self.root, *opf_files[0].get('full-path').split('/'))
		if not os.path.exists(opf_path):
			raise InvalidEpub('OPF file does not exist at location pointed to by META-INF/container.xml')

		# Map of relative paths with / separators to absolute
		# paths on filesystem with os separators
		self.name_map = {}
		for dirpath, dirnames, filenames in os.walk(self.root):
			for f in filenames:
				path = os.path.join(dirpath, f)
				name = os.path.relpath(path, self.root).replace(os.sep, '/')
				self.name_map[name] = path
				if path == opf_path:
					self.opf_name = name
					self.mime_map[name] = guess_type('a.opf')[0]

		for item in self.opf.xpath('//opf:manifest/opf:item[@href and @media-type]', namespaces = {'opf': self.OPF_NS}):
			href = item.get('href')
			self.mime_map[self.href_to_name(href, posixpath.dirname(self.opf_name))] = item.get('media-type')

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
		data = self.get(name)
		if not data:
			return None
		try:
			data = strip_encoding_declarations(data)
		except Exception as e:
			data = unsmarten_text(data)
			try:
				data = strip_encoding_declarations(data)
			except Exception as e2:
				encoding = detect(data)
				try:
					data = data.decode(encoding["encoding"])
				except Exception as e3:
					data = data.decode(encoding["encoding"], 'ignore')
			data = strip_encoding_declarations(data)
		ext = name[name.rfind('.'):]
		if ext in HTML_EXTENSIONS:
			return etree.fromstring(data, parser = etree.HTMLParser())
		else:
			return etree.fromstring(data)

	def manifest_worthy_names(self):
		for name in self.name_map:
			if name.endswith('.opf'): continue
			if name.startswith('META-INF') and posixpath.basename(name) in self.META_INF:
				continue
			yield name

	def delete_name(self, name):
		self.mime_map.pop(name, None)
		path = self.name_map[name]
		os.remove(path)
		self.name_map.pop(name)

	def manifest_item_for_name(self, name):
		href = self.name_to_href(name, posixpath.dirname(self.opf_name))
		q = prepare_string_for_xml(href, attribute = True)
		existing = self.opf.xpath('//opf:manifest/opf:item[@href="{0}"]'.format(q), namespaces = {'opf': self.OPF_NS})
		if not existing:
			return None
		return existing[0]

	def add_name_to_manifest(self, name, mt = None):
		item = self.manifest_item_for_name(name)
		if item is not None:
			return
		manifest = self.opf.xpath('//opf:manifest', namespaces = {'opf': self.OPF_NS})[0]
		item = manifest.makeelement('{%s}item' % self.OPF_NS, nsmap = {'opf': self.OPF_NS}, href = self.name_to_href(name, posixpath.dirname(self.opf_name)), id = self.generate_manifest_id())
		if not mt:
			mt = guess_type(posixpath.basename(name))[0]
		if not mt:
			mt = 'application/octest-stream'
		item.set('media-type', mt)
		manifest.append(item)
		self.fix_tail(item)

	def fix_tail(self, item):
		'''
		Designed only to work with self closing elements after item has
		just been inserted/appended
		'''
		parent = item.getparent()
		idx = parent.index(item)
		if idx == 0:
			item.tail = parent.text
		else:
			item.tail = parent[idx - 1].tail
			if idx == len(parent) - 1:
				parent[idx - 1].tail = parent.text

	def generate_manifest_id(self):
		items = self.opf.xpath('//opf:manifest/opf:item[@id]', namespaces = {'opf': self.OPF_NS})
		ids = set([x.get('id') for x in items])
		for x in xrange(sys.maxint):
			c = 'id{0}'.format(x)
			if c not in ids:
				return c

	@property
	def opf(self):
		return self.get(self.opf_name)

	def href_to_name(self, href, base = ''):
		"""Changed to fix a bug which incorrectly splits the href on
		'#' when '#' is part of the file name. Also normalizes the
		path.

		Taken from the calibre Modify Epub plugin's Container implementation.
		"""
		hash_index = href.find('#')
		period_index = href.find('.')
		if hash_index > 0 and hash_index > period_index:
			href = href.partition('#')[0]
		href = urllib.unquote(href)
		name = href
		if base:
			name = posixpath.join(base, href)
		name = os.path.normpath(name).replace('\\', '/')
		return name

	def name_to_href(self, name, base):
		"""Changed to ensure that blank href names are referenced as the
		empty string instead of '.'.

		Taken from the calibre Modify Epub plugin's Container implementation.
		"""
		if not base:
			return name
		href = posixpath.relpath(name, base)
		if href == '.':
			href = ''
		return href

	def get_raw(self, name):
		path = self.name_map[name]
		return open(path, 'rb').read()

	def get(self, name):
		if name in self.cache:
			return self.cache[name]
		raw = self.get_raw(name)
		if name in self.mime_map:
			try:
				raw = self._parse(raw, self.mime_map[name])
			except XMLSyntaxError as err:
				raise ParseError(name, unicode(err))
		self.cache[name] = raw
		return raw

	def set(self, name, val):
		self.cache[name] = val
		self.dirtied.add(name)

	def _parse(self, raw, mimetype):
		mt = mimetype.lower()
		if mt.endswith('+xml'):
			parser = etree.XMLParser(no_network = True, huge_tree = not iswindows)
			raw = xml_to_unicode(raw,
				strip_encoding_pats = True, assume_utf8 = True,
				resolve_entities = True)[0].strip()
			idx = raw.find('<html')
			if idx == -1:
				idx = raw.find('<HTML')
			if idx > -1:
				pre = raw[:idx]
				raw = raw[idx:]
				if '<!DOCTYPE' in pre:
					user_entities = {}
					for match in re.finditer(r'<!ENTITY\s+(\S+)\s+([^>]+)', pre):
						val = match.group(2)
						if val.startswith('"') and val.endswith('"'):
							val = val[1:-1]
						user_entities[match.group(1)] = val
					if user_entities:
						pat = re.compile(r'&(%s);' % ('|'.join(user_entities.keys())))
						raw = pat.sub(lambda m:user_entities[m.group(1)], raw)
			return etree.fromstring(raw, parser = parser)
		return raw

	def write(self, path):
		for name in self.dirtied:
			data = self.cache[name]
			if hasattr(data, 'xpath'):
				data = etree.tostring(data, encoding = 'UTF-8', xml_declaration = True, pretty_print = True)
			f = open(self.name_map[name], "wb")
			f.write(data)
			f.close()
		self.dirtied.clear()
		if os.path.exists(path):
			os.unlink(path)
		epub = zipfile.ZipFile(path, 'w', compression = zipfile.ZIP_DEFLATED)
		epub.writestr('mimetype', bytes(guess_type('a.epub')[0]), compress_type = zipfile.ZIP_STORED)

		cwd = os.getcwdu()
		os.chdir(self.root)
		zip_prefix = self.root
		if not zip_prefix.endswith(os.sep):
			zip_prefix += os.sep
		for t in os.walk(self.root, topdown = True):
			for f in t[2]:
				if f not in EXCLUDE_FROM_ZIP:
					filepath = os.path.join(t[0], f).replace(zip_prefix, '')
					st = os.stat(filepath)
					mtime = time.localtime(st.st_mtime)
					if mtime[0] < 1980:
						os.utime(filepath, None)
					epub.write(filepath)
		epub.close()
		os.chdir(cwd)
