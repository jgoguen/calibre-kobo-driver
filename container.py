#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import posixpath
import re
import sys
import time
import zipfile

from lxml import etree
from lxml.etree import XMLSyntaxError

from calibre import guess_type
from calibre import prepare_string_for_xml
from calibre.constants import iswindows
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import Log

from urllib import unquote

HTML_MIMETYPES = ['text/html', 'application/xhtml+xml']
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

	acceptable_encryption_algorithms = (
		'http://ns.adobe.com/pdf/enc#RC'
	)

	namespaces = {
		'opf': 'http://www.idpf.org/2007/opf',
		'ocf': 'urn:oasis:names:tc:opendocument:xmlns:container',
		'ncx': 'http://www.daisy.org/z3986/2005/ncx/',
		'dc': 'http://purl.org/dc/elements/1.1/',
		'xhtml': 'http://www.w3.org/1999/xhtml',
		'enc': 'http://www.w3.org/2001/04/xmlenc#',
		'deenc': 'http://ns.adobe.com/digitaleditions/enc',
		'xml': 'http://www.w3.org/XML/1998/namespace'
	}

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

		print("Container:__init__:Got container path {0}".format(self.root))

		if os.path.exists(os.path.join(self.root, 'mimetype')):
			os.remove(os.path.join(self.root, 'mimetype'))

		container_path = os.path.join(self.root, 'META-INF', 'container.xml')
		if not os.path.exists(container_path):
			raise InvalidEpub('No META-INF/container.xml in epub')
		self.container = etree.fromstring(open(container_path, 'rb').read())
		opf_files = self.container.xpath((r'child::ocf:rootfiles/ocf:rootfile[@media-type="{0}" and @full-path]'.format(guess_type('a.opf')[0])), namespaces = self.namespaces)
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
				self.mime_map[name] = guess_type(f)[0]
				if path == opf_path:
					self.opf_name = name
					self.mime_map[name] = guess_type('a.opf')[0]

		opf = self.opf
		for item in opf.xpath('//opf:manifest/opf:item[@href and @media-type]', namespaces = self.namespaces):
			href = unquote(item.get('href'))
			item.set("href", href)
			self.mime_map[self.href_to_name(href, posixpath.dirname(self.opf_name))] = item.get('media-type')
		self.set(self.opf_name, opf)

	def get_html_names(self):
		"""A generator function that yields only HTML file names from
		the ePub.
		"""
		for node in self.opf.xpath('//opf:manifest/opf:item[@href and @media-type]', namespaces = self.namespaces):
			if node.get("media-type") in HTML_MIMETYPES:
				href = posixpath.join(posixpath.dirname(self.opf_name), node.get("href"))
				href = os.path.normpath(href).replace(os.sep, '/')
				yield href

	@property
	def is_drm_encumbered(self):
		"""Determine if the ePub container is encumbered with Digital
		Restrictions Management.

		This method looks for the 'encryption.xml' file which denotes an
		ePub encumbered by Digital Restrictions Management. DRM-encumbered
		files cannot be edited.
		"""
		is_encumbered = False
		if 'META-INF/encryption.xml' in self.name_map:
			try:
				xml = self.get('META-INF/encryption.xml')
				if xml is None:
					return True # If encryption.xml can't be parsed, assume its presence means an encumbered file
				for elem in xml.xpath('./enc:EncryptedData/enc:EncryptionMethod[@Algorithm]', namespaces = self.namespaces):
					alg = elem.get('Algorithm')

					# Anything not in acceptable_encryption_algorithms is a sign of an
					# encumbered file.
					if alg not in self.acceptable_encryption_algorithms:
						is_encumbered = True
			except Exception as e:
				self.log.error("Could not parse encryption.xml: " + e.message)
				raise

		return is_encumbered

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
		existing = self.opf.xpath('//opf:manifest/opf:item[@href="{0}"]'.format(q), namespaces = self.namespaces)
		if not existing:
			return None
		return existing[0]

	def add_name_to_manifest(self, name, mt = None):
		item = self.manifest_item_for_name(name)
		if item is not None:
			return
		manifest = self.opf.xpath('//opf:manifest', namespaces = self.namespaces)[0]
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
		items = self.opf.xpath('//opf:manifest/opf:item[@id]', namespaces = self.namespaces)
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
		href = unquote(href)
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

	def decode(self, data):
		"""Automatically decode :param:`data` into a `unicode` object."""
		def fix_data(d):
			return d.replace('\r\n', '\n').replace('\r', '\n')
		if isinstance(data, unicode):
			return fix_data(data)
		bom_enc = None
		if data[:4] in ('\0\0\xfe\xff', '\xff\xfe\0\0'):
			bom_enc = {'\0\0\xfe\xff':'utf-32-be',
					'\xff\xfe\0\0':'utf-32-le'}[data[:4]]
			data = data[4:]
		elif data[:2] in ('\xff\xfe', '\xfe\xff'):
			bom_enc = {'\xff\xfe':'utf-16-le', '\xfe\xff':'utf-16-be'}[data[:2]]
			data = data[2:]
		elif data[:3] == '\xef\xbb\xbf':
			bom_enc = 'utf-8'
			data = data[3:]
		if bom_enc is not None:
			try:
				return fix_data(data.decode(bom_enc))
			except UnicodeDecodeError:
				pass
		try:
			return fix_data(data.decode('utf-8'))
		except UnicodeDecodeError:
			pass
		data, _ = xml_to_unicode(data)
		return fix_data(data)

	def get_raw(self, name):
		path = self.name_map[name]
		return open(path, 'rb').read()

	def get(self, name):
		if name in self.cache:
			return self.cache[name]
		raw = self.get_raw(name)
		raw = self.decode(raw)
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
		if mt.endswith('xml'):
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

	def __hyphenate_node(self, elem, hyphenator, hyphen = u'\u00AD'):
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
			if elem.text is not None and elem.tail is not None:
				elem.text += u' '
		return elem

	def hyphenate(self, hyphenator, hyphen = u'\u00AD'):
		for name in container.get_html_names():
			debug_print("Container:hyphenate:Hyphenating file - {0}".format(name))
			root = self.get(name)

			for node in root.xpath("./xhtml:body/xhtml:div | ./xhtml:body/xhtml:span | ./xhtml:body/xhtml:p", namespaces = self.namespaces):
				node = self.__hyphenate_node(node, hyphenator, hyphen)
			self.set(name, root)
