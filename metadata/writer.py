# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2015, David Forrester <davidfor@internode.on.net>'
__docformat__ = 'markdown en'

import os

from cStringIO import StringIO

from calibre.customize.builtins import EPUBMetadataWriter
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.metadata.epub import get_zip_reader
from calibre.ebooks.metadata.opf2 import OPF
from calibre.utils.localunzip import LocalZipFile
from calibre.utils.zipfile import safe_replace
from calibre_plugins.kepubmdwriter.common import plugin_minimum_calibre_version
from calibre_plugins.kepubmdwriter.common import plugin_version

class KEPUBMetadataWriter(EPUBMetadataWriter):

    name = 'KePub Metadata Writer'
    author = 'David Forrester'
    description = _('Set metadata in %s files') % 'Kobo ePub'
    file_types  = set(['kepub'])
    version = plugin_version
    minimum_calibre_version = plugin_minimum_calibre_version

    # The logic in here to detect a cover image is mostly duplicated from
    # modify_epub() in common.py. Updates to the logic here probably need an
    # accompanying update there.
    def set_metadata(self, stream, mi, type):
        debug_print("KEPUBMetadataWriter::set_metadata - self.__class__=%s" %(self.__class__))
        super(KEPUBMetadataWriter, self).set_metadata(stream, mi, type)

        stream.seek(0)
        reader = get_zip_reader(stream, root=os.getcwdu())
        raster_cover = reader.opf.raster_cover

        found_cover = False
        covers = reader.opf.raster_cover_path(reader.opf.metadata)
        if len(covers) > 0:
            debug_print("KEPUBMetadataWriter::set_metadata - covers=", covers)
            cover_id = covers[0].get('content')
            debug_print("KEPUBMetadataWriter::set_metadata - cover_id=", cover_id)
            for item in reader.opf.itermanifest():
                if item.get('id', None) == cover_id:
                    mt = item.get('media-type', '')
                    if mt and mt.startswith('image/'):
                        debug_print("KEPUBMetadataWriter::set_metadata - found cover")
                        item.set("properties", "cover-image")
                        found_cover = True
                        break
            if not found_cover:
                debug_print("KEPUBMetadataWriter::set_metadata - looking for cover using href")
                for item in reader.opf.itermanifest():
                    if item.get('href', None) == cover_id:
                        mt = item.get('media-type', '')
                        if mt and mt.startswith('image/'):
                            debug_print("KEPUBMetadataWriter::set_metadata -found cover")
                            item.set("properties", "cover-image")
                            found_cover = True

            if found_cover:
                newopf = StringIO(reader.opf.render())
                if isinstance(reader.archive, LocalZipFile):
                    reader.archive.safe_replace(reader.container[OPF.MIMETYPE], newopf)
                else:
                    safe_replace(stream, reader.container[OPF.MIMETYPE], newopf)
