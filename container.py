#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import re
import shutil
import string
import sys
import time

from lxml import etree
from lxml.etree import XMLSyntaxError

from calibre import guess_type
from calibre import prepare_string_for_xml
from calibre.constants import iswindows
from calibre.ebooks.chardet import substitute_entites
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.conversion.utils import HeuristicProcessor
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils import zipfile
from calibre.utils.logging import Log
from calibre.utils.smartypants import smartyPants

from copy import deepcopy
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

	paragraph_counter = 0
	segment_counter = 0

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
			self.mime_map[self.href_to_name(href, os.path.dirname(self.opf_name).replace(os.sep, '/'))] = item.get('media-type')
		self.set(self.opf_name, opf)

	def get_html_names(self):
		"""A generator function that yields only HTML file names from
		the ePub.
		"""
		for node in self.opf.xpath('//opf:manifest/opf:item[@href and @media-type]', namespaces = self.namespaces):
			if node.get("media-type") in HTML_MIMETYPES:
				href = os.path.join(os.path.dirname(self.opf_name), node.get("href"))
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
			if name.startswith('META-INF') and os.path.basename(name) in self.META_INF:
				continue
			yield name

	def delete_name(self, name):
		self.mime_map.pop(name, None)
		path = self.name_map[name]
		os.remove(path)
		self.name_map.pop(name)

	def manifest_item_for_name(self, name):
		href = self.name_to_href(name, os.path.dirname(self.opf_name))
		q = prepare_string_for_xml(href, attribute = True)
		existing = self.opf.xpath('//opf:manifest/opf:item[@href="{0}"]'.format(q), namespaces = self.namespaces)
		if not existing:
			return None
		return existing[0]

	def add_name_to_manifest(self, name, mt = None):
		item = self.manifest_item_for_name(name)
		if item is not None:
			return
		self.log("Adding '{0}' to the manifest".format(name))
		manifest = self.opf.xpath('//opf:manifest', namespaces = self.namespaces)[0]
		item = manifest.makeelement('{%s}item' % self.namespaces['opf'], href = self.name_to_href(name, os.path.dirname(self.opf_name)), id = self.generate_manifest_id())
		if not mt:
			mt = guess_type(os.path.basename(name))[0]
		if not mt:
			mt = 'application/octest-stream'
		item.set('media-type', mt)
		manifest.append(item)
		self.fix_tail(item)
		self.set(self.opf_name, self.opf)
		self.name_map[name] = os.path.join(self.root, name)
		self.mime_map[name] = mt

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

	def copy_file_to_container(self, path, name = None, mt = None):
		'''Copy a file into this Container instance.

		@param path: The path to the file to copy into this Container.
		@param name: The name to give to the copied file, relative to the Container root. Set to None to use the basename of path.
		@param mt: The MIME type of the file to set in the manifest. Set to None to auto-detect.

		@return: The name of the file relative to the Container root
		'''
		if path is None or re.match(r'^\s*$', path, re.MULTILINE):
			raise ValueError("A source path must be given")
		if name is None:
			name = os.path.basename(path)
		self.log("Copying file '{0}' to '{1}'".format(path, os.path.join(self.root, name)))
		shutil.copy(path, os.path.join(self.root, name))
		self.add_name_to_manifest(name, mt)

		return name

	def add_content_file_reference(self, name):
		'''Add a reference to the named file (from self.name_map) to all content files (self.get_html_names()). Currently
		only CSS files with a MIME type of text/css and JavaScript files with a MIME type of application/x-javascript are
		supported.
		'''
		if name not in self.name_map or name not in self.mime_map:
			raise ValueError("A valid file name must be given (got: {0})".format(name))
		for file in self.get_html_names():
			root = self.get(file)
			if root is None:
				self.log("Could not retrieve content file {0}".format(file))
				continue
			head = root.xpath('./xhtml:head', namespaces = self.namespaces)
			if head is None:
				self.log("Could not find a <head> element in content file {0}".format(file))
				continue
			head = head[0]
			if head is None:
				self.log("A <head> section was found but was undefined in content file {0}".format(file))
				continue

			if self.mime_map[name] == guess_type('a.css')[0]:
				elem = head.makeelement("{%s}link" % self.namespaces['xhtml'], rel = 'stylesheet', href = os.path.relpath(name, os.path.dirname(file)).replace(os.sep, '/'))
			elif self.mime_map[name] == guess_type('a.js')[0]:
				elem = head.makeelement("{%s}script" % self.namespaces['xhtml'], type = 'text/javascript', src = os.path.relpath(name, os.path.dirname(file)).replace(os.sep, '/'))
			else:
				elem = None

			if elem is not None:
				head.append(elem)
				if self.mime_map[name] == guess_type('a.css')[0]:
					self.fix_tail(elem)
				self.set(file, root)

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
			name = os.path.join(base, href)
		name = os.path.normpath(name).replace(os.sep, '/')
		return name

	def name_to_href(self, name, base):
		"""Changed to ensure that blank href names are referenced as the
		empty string instead of '.'.

		Taken from the calibre Modify Epub plugin's Container implementation.
		"""
		if not base:
			return name
		href = os.path.relpath(name, base).replace(os.sep, '/')
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
			val = self.cache[name]
			if not hasattr(val, 'xpath'):
				val = self._parse(val, self.mime_map[name])
			return val
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

	def flush_cache(self):
		for name in self.dirtied:
			data = self.cache[name]
			if hasattr(data, 'xpath'):
				data = etree.tostring(data, encoding = 'UTF-8', xml_declaration = True, pretty_print = True)
			data = string.replace(data, u"\uFFFD", "")
			f = open(self.name_map[name], "wb")
			f.write(data)
			f.close()
		self.dirtied.clear()
		self.cache.clear()

	def write(self, path):
		self.flush_cache()

		if os.path.exists(path):
			os.unlink(path)
		epub = zipfile.ZipFile(path, 'w', compression = zipfile.ZIP_DEFLATED)
		epub.writestr('mimetype', bytes(guess_type('a.epub')[0]), compression = zipfile.ZIP_STORED)

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
		if elem is None:
			return None

		if isinstance(elem, basestring):
			newstr = []
			for w in elem.split():
				if len(w) > 3 and '-' not in w and hyphen not in w:
					w = hyphenator.inserted(w, hyphen = hyphen)
				newstr.append(w)
			elem = " ".join(newstr)
		else:
			if elem.text is None and elem.tail is None:
				# If we get here, there's only child nodes
				for node in elem.xpath('./node()'):
					node = self.__hyphenate_node(node, hyphenator, hyphen)
			else:
				elem.text = self.__hyphenate_node(elem.text, hyphenator, hyphen)
				if elem.text is not None:
					elem.text += u" "
				elem.tail = self.__hyphenate_node(elem.tail, hyphenator, hyphen)
		return elem

	def hyphenate(self, hyphenator, hyphen = u'\u00AD'):
		if hyphenator is None or hyphen is None or hyphen == '':
			return False
		for name in self.get_html_names():
			self.log("Hyphenating file {0}".format(name))
			root = self.get(name)
			for node in root.xpath("./xhtml:body//xhtml:span[starts-with(@id, 'kobo.')]", namespaces = self.namespaces):
				node = self.__hyphenate_node(node, hyphenator, hyphen)
			self.set(name, root)
		return True

	def __add_kobo_spans_to_node(self, node):
		if node is None:
			return None

		if isinstance(node, basestring):
			self.segment_counter += 1
			groups = re.split(ur'(\.|;|:|!|\?|,[^\'"\u201d\u2019])', node, flags = re.UNICODE | re.MULTILINE)
			groups = [g.decode("utf-8") for g in groups if not re.match(r'^\s*$', g, re.UNICODE | re.MULTILINE)]

			if len(groups) > 0:
				text_container = etree.Element("{%s}span" % (self.namespaces["xhtml"],), attrib = {"id": "kobo.{0}.{1}".format(self.paragraph_counter, self.segment_counter), "class": "koboSpan"})
				for g in groups:
					self.segment_counter += 1
					span = etree.Element("{%s}span" % (self.namespaces["xhtml"],), attrib = {"id": "kobo.{0}.{1}".format(self.paragraph_counter, self.segment_counter), "class": "koboSpan"})
					span.text = g
					text_container.append(span)
				return text_container
			return None
		else:
			# First process the text
			newtext = None
			if node.text is not None:
				newtext = self.__add_kobo_spans_to_node(node.text)

			# Clone the rest of the node, clear the node, and add the text node
			children = deepcopy(node.getchildren())
			nodeattrs = {}
			for key in node.attrib.keys():
				nodeattrs[key] = node.attrib[key]
			node.clear()
			for key in nodeattrs.keys():
				node.set(key, nodeattrs[key])
			if newtext is not None:
				node.append(newtext)

			# For each child, process the child and then process and append its tail
			for elem in children:
				elemtail = deepcopy(elem.tail) if elem.tail is not None else None
				newelem = self.__add_kobo_spans_to_node(elem)
				if newelem is not None:
					node.append(newelem)

				newtail = None
				if elemtail is not None:
					newtail = self.__add_kobo_spans_to_node(elemtail)
					if newtail is not None:
						node.append(newtail)

				self.paragraph_counter += 1
				self.segment_counter = 1
			return node
		return None

	def add_kobo_spans(self):
		for name in self.get_html_names():
			self.paragraph_counter = 1
			self.segment_counter = 1
			root = self.get(name)
			if len(root.xpath('.//xhtml:span[class=koboSpan]', namespaces = self.namespaces)) > 0:
				continue
			self.log("Adding Kobo spans to {0}".format(name))
			body = root.xpath('./xhtml:body', namespaces = self.namespaces)[0]
			body = self.__add_kobo_spans_to_node(body)
			self.set(name, root)
		self.flush_cache()
		return True

	def smarten_punctuation(self):
		preprocessor = HeuristicProcessor(log = self.log)

		for name in self.get_html_names():
			self.log("Smartening punctuation for file {0}".format(name))
			html = self.get_raw(name)
			html = html.encode("UTF-8")

			# Fix non-breaking space indents
			html = preprocessor.fix_nbsp_indents(html)
			# Smarten punctuation
			html = smartyPants(html)
			# Ellipsis to HTML entity
			html = re.sub(r'(?u)(?<=\w)\s?(\.\s+?){2}\.', '&hellip;', html)
			# Double-dash and unicode char code to em-dash
			html = string.replace(html, '---', ' &#x2013; ')
			html = string.replace(html, u"\x97", ' &#x2013; ')
			html = string.replace(html, '--', ' &#x2014; ')
			html = string.replace(html, u"\u2014", ' &#x2014; ')
			html = string.replace(html, u"\u2013", ' &#x2013; ')
			html = string.replace(html, u"...", "&#x2026;")

			# Remove Unicode replacement characters
			html = string.replace(html, u"\uFFFD", "")

			self.set(name, html)

	def clean_markup(self):
		preprocessor = HeuristicProcessor(log = self.log)
		for name in self.get_html_names():
			self.log("Cleaning markup for file {0}".format(name))
			html = self.get_raw(name)
			html = html.encode("UTF-8")
			html = string.replace(html, u"\u2014", ' -- ')
			html = string.replace(html, u"\u2013", ' --- ')
			html = string.replace(html, u"\x97", ' --- ')
			html = preprocessor.cleanup_markup(html)

			# Remove Unicode replacement characters
			html = string.replace(html, u"\uFFFD", "")

			self.set(name, html)
