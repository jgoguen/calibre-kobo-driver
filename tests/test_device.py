# vim: fileencoding=UTF-8:expandtab:autoindent:ts=4:sw=4:sts=4
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# To import from calibre, some things need to be added to `sys` first. Do not import
# anything from calibre or the plugins yet.
import glob
import os
import sys
import unittest
import uuid

test_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(test_dir)
test_libdir = os.path.join(
    src_dir, "pylib", "python{major}".format(major=sys.version_info.major)
)
sys.path = [src_dir] + glob.glob(os.path.join(test_libdir, "*.zip")) + sys.path

try:
    from unittest import mock
except ImportError:
    # Python 2
    import mock

from calibre_plugins.kobotouch_extended.device import driver


class MockPropertyTrue:
    def __call__(self, *args, **kwargs):
        return True


class MockPropertyFalse:
    def __call__(self, *args, **kwargs):
        return False


class DeviceTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        driver.common.log = mock.MagicMock()

    def setUp(self):
        self.device = driver.KOBOTOUCHEXTENDED(
            os.path.join(src_dir, "KoboTouchExtended.zip")
        )
        self.device.startup()
        self.device.initialize()

    def tearDown(self):
        self.device.shutdown()
        self.device = None


@mock.patch.object(driver.KOBOTOUCHEXTENDED, "extra_features", True)
class TestDeviceWithExtendedFeatures(DeviceTestBase):
    def test_filename_callback_not_skipped(self):
        mi = mock.MagicMock()
        mi.uuid = uuid.uuid4()

        for ext in ("kepub", "epub"):
            cb_name = self.device.filename_callback("reference.{0}".format(ext), mi)
            self.assertEqual(cb_name, "reference.kepub.epub")

        cb_name = self.device.filename_callback("reference.mobi", mi)
        self.assertEqual(cb_name, "reference.mobi")

    def test_filename_callback_skipped(self):
        mi = mock.MagicMock()
        mi.uuid = uuid.uuid4()
        self.device.skip_renaming_files.add(mi.uuid)

        for ext in ("mobi", "epub"):
            cb_name = self.device.filename_callback("reference.{0}".format(ext), mi)
            self.assertEqual(cb_name, "reference.{0}".format(ext))

        cb_name = self.device.filename_callback("reference.kepub", mi)
        self.assertEqual(cb_name, "reference.kepub.epub")

    def test_sanitize_filename_components(self):
        # Make sure test_components and expected_components stay in the right order!
        test_components = [
            "home",
            "Calibre Library",
            r"test*path?component%with:lots|of$bad!characters/",
        ]
        expected_components = [
            "home",
            "Calibre Library",
            "test_path_component_with_lots_of_bad_characters_",
        ]
        sanitized_components = self.device.sanitize_path_components(test_components)
        self.assertListEqual(sanitized_components, expected_components)


@mock.patch.object(driver.KOBOTOUCHEXTENDED, "extra_features", False)
class TestDeviceWithoutExtendedFeatures(DeviceTestBase):
    def test_filename_callback_skipped(self):
        mi = mock.MagicMock()
        mi.uuid = uuid.uuid4()
        self.assertFalse(self.device.extra_features)

        for ext in ("kepub", "epub", "mobi"):
            cb_name = self.device.filename_callback("reference.{0}".format(ext), mi)
            self.assertEqual(cb_name, "reference.{0}".format(ext))


if __name__ == "__main__":
    unittest.main(module="test_device", verbosity=2)
