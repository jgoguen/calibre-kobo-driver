# vim: fileencoding=UTF-8:expandtab:autoindent:ts=4:sw=4:sts=4

# To import from calibre, some things need to be added to `sys` first. Do not import
# anything from calibre or the plugins yet.
import glob
import os
import shutil
import sys
import tempfile
import unittest
import uuid
import warnings

test_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(test_dir)
test_libdir = os.path.join(src_dir, "pylib", f"python{sys.version_info.major}")
sys.path = [src_dir] + glob.glob(os.path.join(test_libdir, "*.zip")) + sys.path

from unittest import mock

from calibre_plugins.kobotouch_extended import container
from calibre_plugins.kobotouch_extended.device import driver


class MockPropertyTrue:
    def __call__(self, *args, **kwargs):
        return True


class MockPropertyFalse:
    def __call__(self, *args, **kwargs):
        return False


class MockKePubContainer(mock.MagicMock):
    @staticmethod
    def is_drm_encumbered() -> bool:
        return False


class DeviceTestBase(unittest.TestCase):  # skipcq: PTC-W0046
    log = mock.Mock()

    def __init__(self, *args, **kwargs):
        super(DeviceTestBase, self).__init__(*args, **kwargs)
        self.reference_book = os.path.join(test_dir, "reference_book")

        self.mi = mock.MagicMock()
        self.mi.title = "Test Book"
        self.mi.authors = ["John Q. Public", "Suzie Q. Public"]
        self.mi.uuid = uuid.uuid4()

    @classmethod
    def setUpClass(cls):
        driver.common.log = mock.MagicMock()

    def setUp(self):
        self.device = driver.KOBOTOUCHEXTENDED(
            os.path.join(src_dir, "KoboTouchExtended.zip")
        )
        self.device.startup()
        self.device.initialize()
        self.device._main_prefix = "/mnt/kobo"

        self.basedir = tempfile.mkdtemp(prefix="kte-", suffix="-test", dir=test_dir)
        self.epub_dir = os.path.join(self.basedir, "kepub")
        self.tmpdir = os.path.join(self.basedir, "tmp")

        shutil.copytree(self.reference_book, self.epub_dir)
        os.mkdir(self.tmpdir)

        self.container = container.KEPubContainer(
            self.epub_dir, self.log, tdir=self.tmpdir
        )

        if sys.version_info >= (3, 2):
            warnings.simplefilter("ignore", category=ResourceWarning)

    def tearDown(self):
        if self.device:
            self.device.shutdown()
        self.device = None

        self.log.reset_mock()

        if self.basedir and os.path.isdir(self.basedir):
            shutil.rmtree(self.basedir, ignore_errors=True)


@mock.patch.object(driver.KOBOTOUCHEXTENDED, "extra_features", True)
class TestDeviceWithExtendedFeatures(DeviceTestBase):
    def test_filename_callback_not_skipped(self):
        assert self.device is not None

        mi = mock.MagicMock()
        mi.uuid = uuid.uuid4()

        for ext in ("kepub", "epub"):
            cb_name = self.device.filename_callback(f"reference.{ext}", mi)
            self.assertEqual(cb_name, "reference.kepub.epub")

        cb_name = self.device.filename_callback("reference.mobi", mi)
        self.assertEqual(cb_name, "reference.mobi")

    def test_filename_callback_skipped(self):
        assert self.device is not None

        mi = mock.MagicMock()
        mi.uuid = uuid.uuid4()
        self.device.skip_renaming_files.add(mi.uuid)

        for ext in ("mobi", "epub"):
            cb_name = self.device.filename_callback(f"reference.{ext}", mi)
            self.assertEqual(cb_name, f"reference.{ext}")

        cb_name = self.device.filename_callback("reference.kepub", mi)
        self.assertEqual(cb_name, "reference.kepub.epub")

    def test_sanitize_filename_components(self):
        # Make sure test_components and expected_components stay in the right order!
        assert self.device is not None

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

    @mock.patch.object(
        driver.common, "modify_epub", side_effect=ValueError("Testing exception")
    )
    def test_modify_epub_exception_fails(self, _modify_epub):
        assert self.device is not None

        self.assertFalse(self.device.skip_failed)

        with self.assertRaises(ValueError):
            self.device._modify_epub("test.epub", self.mi, self.container)

        self.assertNotIn(self.mi.uuid, self.device.skip_renaming_files)


@mock.patch.object(driver.KOBOTOUCHEXTENDED, "extra_features", False)
@mock.patch.object(driver.KOBOTOUCHEXTENDED, "use_template", False)
class TestDeviceWithoutExtendedFeatures(DeviceTestBase):
    def test_filename_callback_skipped(self):
        assert self.device is not None

        mi = mock.MagicMock()
        mi.uuid = uuid.uuid4()
        self.assertFalse(self.device.extra_features)

        for ext in ("epub", "mobi"):
            cb_name = self.device.filename_callback(f"reference.{ext}", mi)
            self.assertEqual(cb_name, f"reference.{ext}")


@mock.patch.object(driver.KOBOTOUCHEXTENDED, "extra_features", True)
@mock.patch.object(driver.KOBOTOUCHEXTENDED, "skip_failed", True)
class TestDeviceSkippingErrors(DeviceTestBase):
    @mock.patch.object(
        driver.common, "modify_epub", side_effect=ValueError("Testing exception")
    )
    @mock.patch.object(driver.KOBOTOUCH, "_modify_epub")
    def test_modify_epub_skip_exceptions(
        self, _extended_modify_epub, _base_modify_epub
    ):
        assert self.device is not None

        self.assertTrue(self.device.skip_failed)

        self.device._modify_epub("test.epub", self.mi, self.container)

        self.assertIn(self.mi.uuid, self.device.skip_renaming_files)


if __name__ == "__main__":
    unittest.main(module="test_device", verbosity=2)
