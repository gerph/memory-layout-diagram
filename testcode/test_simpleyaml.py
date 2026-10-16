"""
Unit tests for the bundled YAML subset parser.

Run with:  python3 -m unittest discover -s testcode
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from memory_layout import simpleyaml  # noqa: E402


def load(text):
    return simpleyaml.load(io.StringIO(text))


class TestValid(unittest.TestCase):

    def test_mapping_and_scalars(self):
        doc = load("a: 1\nb: 0x10\nc: true\nd: false\ne: 1.5\nf: text\n")
        self.assertEqual(doc, {'a': 1, 'b': 16, 'c': True, 'd': False, 'e': 1.5, 'f': 'text'})

    def test_single_digit_zero(self):
        self.assertEqual(load("a: 0\nb:\n  - 0\n  - 1\n"), {'a': 0, 'b': [0, 1]})

    def test_nested_mapping(self):
        doc = load("outer:\n  inner: 1\n  other: 2\n")
        self.assertEqual(doc, {'outer': {'inner': 1, 'other': 2}})

    def test_list_values(self):
        doc = load("key:\n  - one\n  - two\n")
        self.assertEqual(doc, {'key': ['one', 'two']})

    def test_quoted_strings_may_contain_indicators(self):
        doc = load("a: \"[not a list]\"\nb: '{nor this}'\nc: \"#FFF\"\nd: '&00010C00'\n")
        self.assertEqual(doc, {'a': '[not a list]', 'b': '{nor this}', 'c': '#FFF', 'd': '&00010C00'})

    def test_quoted_string_with_trailing_comment(self):
        self.assertEqual(load('a: "text"  # comment\n'), {'a': 'text'})

    def test_indicators_are_fine_inside_plain_text(self):
        doc = load("a: size [64K]\nb: a > b\nc: x*y\n")
        self.assertEqual(doc, {'a': 'size [64K]', 'b': 'a > b', 'c': 'x*y'})

    def test_unquoted_hash_is_a_comment(self):
        # As in real YAML, so the value is null; callers must cope with that.
        self.assertEqual(load("fill: #FFF\n"), {'fill': None})

    def test_same_key_in_different_mappings(self):
        doc = load("a:\n  size: 1\nb:\n  size: 2\n")
        self.assertEqual(doc, {'a': {'size': 1}, 'b': {'size': 2}})


class TestErrors(unittest.TestCase):

    def assertError(self, text, lineno, fragment):
        with self.assertRaises(simpleyaml.YAMLError) as ctx:
            load(text)
        self.assertEqual(ctx.exception.lineno, lineno, str(ctx.exception))
        self.assertIn(fragment, str(ctx.exception))
        self.assertTrue(str(ctx.exception).startswith("line %d: " % (lineno,)))

    def test_inline_list(self):
        self.assertError("layout:\n  0: [unterminated\n", 2, "flow style")

    def test_inline_mapping(self):
        self.assertError("layout:\n  0: {a: b}\n", 2, "flow style")

    def test_inline_list_as_list_item(self):
        self.assertError("layout:\n  - [a, b]\n", 2, "flow style")

    def test_unterminated_double_quote(self):
        self.assertError('a: 1\nb: "abc\n', 2, "not terminated")

    def test_unterminated_single_quote(self):
        self.assertError("a: 'abc\n", 1, "not terminated")

    def test_text_after_closing_quote(self):
        self.assertError('a: "abc" def\n', 1, "not terminated")

    def test_block_string(self):
        self.assertError("a: |\n  text\n", 1, "block strings")
        self.assertError("a: >\n  text\n", 1, "block strings")

    def test_anchors_aliases_and_tags(self):
        self.assertError("a: &anchor 1\n", 1, "anchors")
        self.assertError("a: *alias\n", 1, "aliases")
        self.assertError("a: !!str 1\n", 1, "type tags")

    def test_duplicate_key(self):
        self.assertError("a: 1\nb: 2\na: 3\n", 3, "Duplicate key 'a'")

    def test_duplicate_key_in_nested_mapping(self):
        self.assertError("outer:\n  a: 1\n  a: 2\n", 3, "Duplicate key 'a'")

    def test_line_numbers_count_comments_and_blank_lines(self):
        self.assertError("# comment\n\na: 1\nb: [x\n", 4, "flow style")

    def test_unparseable_line(self):
        with self.assertRaises(simpleyaml.YAMLError):
            load("a: 1\nnot a key\n")

    def test_error_without_line_number_has_no_prefix(self):
        self.assertEqual(str(simpleyaml.YAMLError("message")), "message")


if __name__ == '__main__':
    unittest.main()
