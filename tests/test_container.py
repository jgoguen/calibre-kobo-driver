# vim: fileencoding=UTF-8:expandtab:autoindent:ts=4:sw=4:sts=4

# To import from calibre, some things need to be added to `sys` first. Do not import
# anything from calibre or the plugins yet.
import glob
import hashlib
import os
import re
import shutil
import sys
import tempfile
import unittest
import warnings

from collections import defaultdict
from lxml import etree
from unittest import mock

test_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(test_dir)
test_libdir = os.path.join(src_dir, "pylib", f"python{sys.version_info.major}")
sys.path = [src_dir] + glob.glob(os.path.join(test_libdir, "*.zip")) + sys.path

from tests.assertions import TestAssertions
from calibre_plugins.kobotouch_extended import container


OFFICE_NAMESPACE = "urn:schemas-microsoft-com:office:office"


# Only subclass TestAssertions because that class subclasses unittest.TestCase
class TestContainer(TestAssertions):
    tmpdir = ""  # type: str
    log = mock.Mock()
    files = {}

    def __init__(self, *args, **kwargs):
        super(TestContainer, self).__init__(*args, **kwargs)
        self.reference_book = os.path.join(test_dir, "reference_book")
        self.testfile_basedir = os.path.join(test_dir, "test_files")
        self.files.update(
            {
                "test_with_spans": os.path.join(
                    self.testfile_basedir, "page_with_kobo_spans.html"
                ),
                "test_without_spans": os.path.join(
                    self.testfile_basedir, "page_without_spans.html"
                ),
                "test_without_spans_with_comments": os.path.join(
                    self.testfile_basedir, "page_without_spans_with_comments.html"
                ),
                "dirty_markup": os.path.join(
                    self.testfile_basedir, "page_dirty_markup.html"
                ),
                "needs_cleanup": os.path.join(
                    self.testfile_basedir, "page_needs_cleanup.html"
                ),
                "css": os.path.join(self.testfile_basedir, "test.css"),
                "js": os.path.join(self.testfile_basedir, "test.js"),
            }
        )

    def setUp(self):
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
        if self.basedir and os.path.isdir(self.basedir):
            shutil.rmtree(self.basedir, ignore_errors=True)
        self.log.reset_mock()

    def test_add_html_file(self):
        container_name = self.container.copy_file_to_container(
            self.files["test_with_spans"]
        )
        self.assertIn(container_name, self.container.name_path_map)
        self.assertIn(container_name, self.container.mime_map)
        self.assertIn(self.container.mime_map[container_name], container.HTML_MIMETYPES)
        self.assertIn("content.opf", self.container.dirtied)

    def __run_added_test(
        self, expect_changed, added_func
    ):  # type: (bool, Callable) -> None
        if expect_changed:
            source_file = self.files["test_without_spans_with_comments"]
        else:
            source_file = self.files["test_with_spans"]
        with open(source_file, "r") as f:
            data = f.read().encode("UTF-8")
            orig_hash = hashlib.sha256(data).hexdigest()

        container_name = self.container.copy_file_to_container(source_file)
        with open(os.path.join(self.tmpdir, container_name), "r") as f:
            data = f.read().encode("UTF-8")
            self.assertEqual(orig_hash, hashlib.sha256(data).hexdigest())

        html_names = list(self.container.html_names())
        self.assertGreaterEqual(len(html_names), 1)
        self.assertIn(container_name, html_names)

        added_func(container_name)

        with open(os.path.join(self.tmpdir, container_name), "r") as f:
            if expect_changed:
                assert_func = self.assertNotEqual
            else:
                assert_func = self.assertEqual
            data = f.read().encode("UTF-8")
            assert_func(orig_hash, hashlib.sha256(data).hexdigest())

    def test_divs_added(self):
        self.__run_added_test(True, self.container.add_kobo_divs)
        o = self.container.parsed(
            os.path.basename(self.files["test_without_spans_with_comments"])
        )
        for div_id in {"book-columns", "book-inner"}:
            element_count = o.xpath(
                f'count(//xhtml:div[@id="{div_id}"])',
                namespaces={"xhtml": container.XHTML_NAMESPACE},
            )
            self.assertEqual(element_count, 1)

    def test_not_adding_divs_twice(self):
        self.__run_added_test(False, self.container.add_kobo_divs)
        o = self.container.parsed(os.path.basename(self.files["test_with_spans"]))
        for div_id in {"book-columns", "book-inner"}:
            element_count = o.xpath(
                f'count(//xhtml:div[@id="{div_id}"])',
                namespaces={"xhtml": container.XHTML_NAMESPACE},
            )
            self.assertEqual(element_count, 1)

    def test_spans_added(self):
        self.__run_added_test(True, self.container.add_kobo_spans)
        o = self.container.parsed(
            os.path.basename(self.files["test_without_spans_with_comments"])
        )
        element_count = o.xpath(
            'count(//xhtml:span[@class="koboSpan"])',
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(element_count, 5)

    def test_not_adding_spans_twice(self):
        self.__run_added_test(False, self.container.add_kobo_spans)
        o = self.container.parsed(os.path.basename(self.files["test_with_spans"]))
        element_count = o.xpath(
            'count(//xhtml:span[@class="koboSpan"])',
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(element_count, 5)

    def test_clean_markup(self):
        container_name = self.container.copy_file_to_container(
            self.files["dirty_markup"]
        )
        self.assertIn(container_name, self.container.name_path_map)

        html = self.container.raw_data(
            container_name, decode=True, normalize_to_nfc=True
        )
        self.assertIsNotNone(container.MS_CRUFT_RE_1.search(html))
        self.assertIsNotNone(container.EMPTY_HEADINGS_RE.search(html))

        self.container.clean_markup(container_name)

        html = self.container.raw_data(
            container_name, decode=True, normalize_to_nfc=True
        )
        self.assertIsNone(container.MS_CRUFT_RE_1.search(html))
        self.assertIsNone(container.EMPTY_HEADINGS_RE.search(html))

    def test_forced_cleanup(self):
        container_name = self.container.copy_file_to_container(
            self.files["needs_cleanup"]
        )
        self.assertIn(container_name, self.container.name_path_map)

        test_regexs = [
            r'<link href="fake\.css">',
            r'<script src="fake.js" ?/>',
            r"<p ?/>",
        ]

        for regex in test_regexs:
            self.assertIsNotNone(
                re.search(
                    regex,
                    self.container.raw_data(container_name),
                    re.UNICODE | re.MULTILINE,
                )
            )

    # This test also covers KEPubContainer.fix_tail()
    def test_add_css(self):
        html_container_name = self.container.copy_file_to_container(
            self.files["test_with_spans"]
        )
        css_container_name = self.container.copy_file_to_container(self.files["css"])

        html = self.container.parsed(html_container_name)
        css_pre_count = html.xpath(
            f'count(//xhtml:head/xhtml:style[@href="{css_container_name}"])',
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(css_pre_count, 0)

        self.container.add_content_file_reference(css_container_name)
        html = self.container.parsed(html_container_name)
        css_post_count = html.xpath(
            f'count(//xhtml:head/xhtml:link[@href="{css_container_name}"])',
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(css_post_count, 1)

        self.assertIsNotNone(
            re.search(
                rf'<link.+?href="{css_container_name}".*? ?/>',
                self.container.raw_data(html_container_name),
                re.UNICODE | re.MULTILINE,
            )
        )

    def test_add_js(self):
        html_container_name = self.container.copy_file_to_container(
            self.files["test_with_spans"]
        )
        js_container_name = self.container.copy_file_to_container(self.files["js"])

        html = self.container.parsed(html_container_name)
        js_pre_count = html.xpath(
            f'count(//xhtml:head/xhtml:script[@src="{js_container_name}"])',
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(js_pre_count, 0)

        self.container.add_content_file_reference(js_container_name)
        html = self.container.parsed(html_container_name)
        js_post_count = html.xpath(
            f'count(//xhtml:head/xhtml:script[@src="{js_container_name}"])',
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(js_post_count, 1)

        self.assertIsNotNone(
            re.search(
                rf'<script.+?src="{js_container_name}".*?></script>',
                self.container.raw_data(html_container_name),
                re.UNICODE | re.MULTILINE,
            )
        )

    def test_add_spans_to_text(self):
        text_samples = [
            "Hello, World!",
            "    Hello, World!",
            "Hello, World!    ",
            "    Hello, World!    ",
            "\n\n    GIF is pronounced as it's spelled.\n   ",
        ]

        for text in text_samples:
            for text_only in {True, False}:
                self.container.paragraph_counter = defaultdict(lambda: 1)
                node = etree.Element(f"{{{container.XHTML_NAMESPACE}}}p")

                if text_only:
                    self.assertTrue(
                        self.container._append_kobo_spans_from_text(node, text, "test")
                    )
                else:
                    node.text = text
                    node = self.container._add_kobo_spans_to_node(node, "test")

                self.assertEqual(len(node.getchildren()), 1)

                span = node.getchildren()[0]
                self.assertIsNone(span.tail)
                # attrib is technically of type lxml.etree._Attrib, but functionally
                # it's a dict. Cast it here to make assertDictEqual() happy.
                self.assertDictEqual(
                    dict(span.attrib), {"id": "kobo.1.1", "class": "koboSpan"}
                )
                self.assertEqual(span.text, text)

    def __run_multiple_node_test(self, text_nodes):  # type: (List[str]) -> None
        html = "<div>"
        for text in text_nodes:
            # DeepSource falsely detects this as simply concatenating the values from
            # the iterable.
            html += f"<p>{text}</p>"  # skipqa: PYL-R1713
        html += "</div>"
        node = etree.fromstring(html)
        self.container._paragraph_counter = 1
        self.container._segment_counter = 1

        node = self.container._add_kobo_spans_to_node(node, "test")
        children = node.getchildren()
        self.assertEqual(len(children), len(text_nodes))

        for node_idx, node in enumerate(children):
            spans = node.getchildren()
            text_chunks = [
                g
                for g in container.TEXT_SPLIT_RE.split(text_nodes[node_idx])
                if g.strip() != ""
            ]
            self.assertEqual(len(spans), len(text_chunks))

            for text_idx, text_chunk in enumerate(text_chunks):
                self.assertEqual(spans[text_idx].text, text_chunk)

    def test_add_spans_to_multiple_sentences(self):
        self.__run_multiple_node_test(
            ["Copyright", "by me.", "All rights reserved. All wrongs on retainer."]
        )

    def test_add_spans_to_pretty_printed_text(self):
        self.__run_multiple_node_test(
            [
                "\n    Copyright\n  ",
                "\n   by\nme.  \n    ",
                "\n  All rights reserved.\nAll wrongs on retainer.\n  ",
                "\n\n    GIF is pronounced as it's spelled.\n   ",
            ]
        )

    def test_gitub_pr_106(self):
        source_file = os.path.join(self.testfile_basedir, "page_github_106.html")
        container_name = self.container.copy_file_to_container(source_file)
        self.assertIn(container_name, self.container.name_path_map)

        pre_span = self.container.parsed(container_name)
        text_chunks = [
            g.lstrip("\n\t")
            for g in pre_span.xpath(
                "//xhtml:p//text()", namespaces={"xhtml": container.XHTML_NAMESPACE}
            )
        ]

        self.container.add_kobo_spans(container_name)

        post_span = self.container.parsed(container_name)
        post_text_chunks = [
            g.lstrip("\n\t")
            for g in post_span.xpath(
                "//xhtml:p//text()", namespaces={"xhtml": container.XHTML_NAMESPACE}
            )
        ]
        self.assertListEqual(text_chunks, post_text_chunks)

    def test_github_issue_136(self):
        source_file = os.path.join(self.testfile_basedir, "page_github_136.html")
        container_name = self.container.copy_file_to_container(source_file)
        self.assertIn(container_name, self.container.name_path_map)

        self.container.smarten_punctuation()

        html = self.container.parsed(container_name)
        capitolo_p_count = html.xpath(
            'count(//xhtml:body//xhtml:p[@class="corpo---titolo-capitolo"])',
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(capitolo_p_count, 1)

    def test_github_issue_90(self):
        source_file = os.path.join(self.testfile_basedir, "page_github_90.html")
        container_name = self.container.copy_file_to_container(source_file)
        self.assertIn(container_name, self.container.name_path_map)

        pre_span = self.container.parsed(container_name)
        pre_p_count = pre_span.xpath(
            "count(//xhtml:body/xhtml:p)",
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        pre_span_count = pre_span.xpath(
            "count(//xhtml:body/xhtml:span)",
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(pre_p_count, 2)
        self.assertEqual(pre_span_count, 0)

        self.container.add_kobo_spans(container_name)

        post_span = self.container.parsed(container_name)

        post_body = post_span.xpath(
            "//xhtml:body", namespaces={"xhtml": container.XHTML_NAMESPACE}
        )[0]
        self.assertEqual(len(post_body.getchildren()), 2)

        post_p = post_span.xpath(
            "//xhtml:body/xhtml:p",
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        post_span_count = post_span.xpath(
            "count(//xhtml:body/xhtml:span)",
            namespaces={"xhtml": container.XHTML_NAMESPACE},
        )
        self.assertEqual(len(post_p), 2)
        self.assertEqual(post_span_count, 0)
        for p in post_p:
            self.assertIsNoneOrEmptyString(p.text)
            self.assertIsNoneOrEmptyString(p.tail)

            for child in p.getchildren():
                self.assertIsNoneOrEmptyString(child.tail)

                if child.tag == "span":
                    self.assertIsNotNoneOrEmptyString(child.text)

    def test_assert_none_or_empty_string(self):
        self.assertIsNoneOrEmptyString(None)
        self.assertIsNoneOrEmptyString("   ")
        self.assertIsNoneOrEmptyString("\n")
        self.assertIsNoneOrEmptyString("\n\t   \t\n")

        with self.assertRaises(AssertionError):
            self.assertIsNoneOrEmptyString("Hello, World")

        with self.assertRaises(AssertionError):
            self.assertIsNoneOrEmptyString(Exception("Hello, World"))

    def test_assert_not_none_or_empty_string(self):
        self.assertIsNotNoneOrEmptyString("Hello, World")
        self.assertIsNotNoneOrEmptyString("\n\n   Hello")
        self.assertIsNotNoneOrEmptyString(", World  \n   \t")

        for s in {"", "   ", "\n  \t", "\t\n\n    \n"}:
            with self.assertRaises(AssertionError):
                self.assertIsNotNoneOrEmptyString(s)

        with self.assertRaises(AssertionError):
            self.assertIsNotNoneOrEmptyString(Exception("Hello, World"))


if __name__ == "__main__":
    unittest.main(module="test_container", verbosity=2)
