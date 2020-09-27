# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

"""KePub metadata reader."""

__license__ = "GPL v3"
__copyright__ = "2015, David Forrester <davidfor@internode.on.net>"
__docformat__ = "markdown en"

from calibre.customize.builtins import EPUBMetadataReader

from calibre_plugins.kepubmdreader import common

# Support load_translations() without forcing calibre 1.9+
try:
    load_translations()
except NameError:
    pass


class KEPUBMetadataReader(EPUBMetadataReader):
    """KePub metadata is identical to ePub, we just need to tell calibre."""

    name = "KePub Metadata Reader"
    author = "David Forrester"
    description = _("Read metadata from Kobo KePub files")  # noqa: F821
    file_types = {"kepub"}
    version = common.PLUGIN_VERSION
    minimum_calibre_version = common.PLUGIN_MINIMUM_CALIBRE_VERSION
