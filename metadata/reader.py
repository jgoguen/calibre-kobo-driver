# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2015, David Forrester <davidfor@internode.on.net>'
__docformat__ = 'markdown en'

from calibre.customize.builtins import EPUBMetadataReader
from calibre_plugins.kepubmdreader.common import plugin_minimum_calibre_version
from calibre_plugins.kepubmdreader.common import plugin_version


class KEPUBMetadataReader(EPUBMetadataReader):

    name = 'KePub Metadata Reader'
    author = 'David Forrester'
    description = _('Read metadata from %s files') % 'Kobo ePub'  # noqa: F821
    file_types = set(['kepub'])
    version = plugin_version
    minimum_calibre_version = plugin_minimum_calibre_version
