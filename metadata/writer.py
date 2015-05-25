# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__ = 'GPL v3'
__copyright__ = '2015, David Forrester <davidfor@internode.on.net>'
__docformat__ = 'markdown en'

from calibre.customize.builtins import EPUBMetadataWriter
from calibre_plugins.kepubmdwriter.common import plugin_minimum_calibre_version
from calibre_plugins.kepubmdwriter.common import plugin_version

class KEPUBMetadataWriter(EPUBMetadataWriter):

    name = 'Set KEPUB metadata'
    author = 'David Forrester'
    description = _('Set metadata in %s files') % 'Kobo ePub'
    file_types  = set(['kepub'])
    version = plugin_version
    minimum_calibre_version = plugin_minimum_calibre_version
