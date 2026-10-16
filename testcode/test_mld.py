"""
Unit tests for the processing of an MLD document.

Run with:  python3 -m unittest discover -s testcode
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import memory_layout.simpleyaml  # noqa: E402
from memory_layout import __main__ as mld  # noqa: E402


def build(text):
    """
    Returns (sequence, defaults, list of problem messages) for some MLD text.
    """
    problems = mld.Problems()
    doc = memory_layout.simpleyaml.load(io.StringIO(text))
    sequence, defaults = mld.build_sequence(doc, problems)
    return sequence, defaults, list(problems)


def label_texts(region):
    return sorted(label.label for label in region.labels.values())


class TestDecoders(unittest.TestCase):

    def test_distance_numbers(self):
        self.assertEqual(mld.decode_distance(2), 2)
        self.assertEqual(mld.decode_distance(0.5), 0.5)
        self.assertEqual(mld.decode_distance(0), 0)

    def test_distance_points(self):
        self.assertEqual(mld.decode_distance('72pt'), 1)
        self.assertEqual(mld.decode_distance('36 pt'), 0.5)

    def test_distance_numeric_string(self):
        self.assertEqual(mld.decode_distance('1.5'), 1.5)

    def test_distance_rejects(self):
        for value in ('tall', '3cm', '-1', -1, True, None, 'pt', [1]):
            with self.assertRaises(mld.MLDError, msg=repr(value)):
                mld.decode_distance(value)

    def test_colour_accepts(self):
        for value in ('#FFF', '#ffff', '#112233', '#11223344', 'red', 'Red', 'none', 'rgb(1, 2, 3)'):
            self.assertEqual(mld.decode_colour(value), value)

    def test_colour_rejects(self):
        for value in ('#12', '#12345', '#GGG', 'reddish', '', 5, True, ['red']):
            with self.assertRaises(mld.MLDError, msg=repr(value)):
                mld.decode_colour(value)

    def test_colour_none_mentions_quoting(self):
        with self.assertRaises(mld.MLDError) as ctx:
            mld.decode_colour(None)
        self.assertIn('quoted', str(ctx.exception))

    def test_position_shortcuts(self):
        self.assertEqual(mld.decode_position('tl'), ('il', 'it'))
        self.assertEqual(mld.decode_position('c'), ('ic', 'ic'))

    def test_position_canonical(self):
        self.assertEqual(mld.decode_position('er,ib'), ('er', 'ib'))
        self.assertEqual(mld.decode_position('elf, jt'), ('elf', 'jt'))

    def test_position_rejects(self):
        for value in ('middle', 'zz,ib', 'il,zz', 'il,it,ic', 5, None):
            with self.assertRaises(mld.MLDError, msg=repr(value)):
                mld.decode_position(value)

    def test_formatter(self):
        self.assertIsInstance(mld.decode_formatter('acorn'), mld.ValueFormatterAcorn)
        with self.assertRaises(mld.MLDError):
            mld.decode_formatter('shiny')


class TestChecker(unittest.TestCase):

    def setUp(self):
        self.problems = mld.Problems()
        self.check = mld.Checker(self.problems)

    def test_keys_suggests_close_match(self):
        self.check.keys({'address': True}, ('addresses', 'discontinuities'), "'automatic'")
        self.assertEqual(len(self.problems), 1)
        self.assertIn("did you mean 'addresses'", list(self.problems)[0])

    def test_keys_lists_known_when_nothing_close(self):
        self.check.keys({'zzzzzz': 1}, ('size', 'label'), 'here')
        self.assertIn('known keys are: size, label', list(self.problems)[0])

    def test_keys_accepts_known(self):
        self.check.keys({'size': 1, 'label': 'x'}, ('size', 'label'), 'here')
        self.assertEqual(len(self.problems), 0)

    def test_integer_is_not_boolean(self):
        self.assertIsNone(self.check.integer(True, 'x'))
        self.assertEqual(self.check.integer(4, 'x'), 4)
        self.assertIsNone(self.check.integer(0, 'x', minimum=1))
        self.assertIsNone(self.check.integer('4', 'x'))
        self.assertEqual(len(self.problems), 3)

    def test_boolean_is_not_integer(self):
        self.assertIsNone(self.check.boolean(1, 'x'))
        self.assertIs(self.check.boolean(False, 'x'), False)

    def test_text_converts_numbers_but_not_structures(self):
        self.assertEqual(self.check.text(1234, 'x'), '1234')
        self.assertIsNone(self.check.text(None, 'x'))
        self.assertIsNone(self.check.text([1], 'x'))
        self.assertIsNone(self.check.text(True, 'x'))

    def test_mapping(self):
        self.assertEqual(self.check.mapping(None, 'x'), {})
        self.assertEqual(self.check.mapping({'a': 1}, 'x'), {'a': 1})
        self.assertEqual(self.check.mapping(3, 'x'), {})
        self.assertEqual(len(self.problems), 1)


class TestBuildSequence(unittest.TestCase):

    def test_minimal(self):
        sequence, defaults, problems = build("layout:\n  0: Low\n  0x1000: High\n")
        self.assertEqual(problems, [])
        self.assertEqual([r.address for r in sequence.regions], [0, 0x1000])

    def test_regions_are_sorted_by_address(self):
        sequence, defaults, problems = build("layout:\n  0x2000: C\n  0: A\n  0x1000: B\n")
        self.assertEqual([r.address for r in sequence.regions], [0, 0x1000, 0x2000])

    def test_not_a_mapping_is_fatal(self):
        with self.assertRaises(mld.MLDError):
            mld.build_sequence(['a'], mld.Problems())
        with self.assertRaises(mld.MLDError):
            mld.build_sequence(None, mld.Problems())

    def test_missing_layout_is_fatal(self):
        with self.assertRaises(mld.MLDError):
            build("defaults:\n  unit_size: 1\n")

    def test_bad_address_is_fatal(self):
        with self.assertRaises(mld.MLDError):
            build("layout:\n  zzz: A\n")

    def test_region_without_value(self):
        sequence, defaults, problems = build("layout:\n  0:\n  16: B\n")
        self.assertEqual(problems, [])
        self.assertEqual(len(sequence.regions), 2)

    def test_numeric_label_is_text(self):
        sequence, defaults, problems = build("layout:\n  0: 1234\n")
        self.assertEqual(problems, [])
        self.assertEqual(label_texts(sequence.regions[0]), ['1234'])

    def test_same_address_twice_reported_without_crashing(self):
        sequence, defaults, problems = build("layout:\n  16: A\n  0x10: B\n")
        self.assertEqual(len(problems), 1)
        self.assertIn('same address', problems[0])
        self.assertEqual(len(sequence.regions), 2)

    def test_defaults_applied(self):
        sequence, defaults, problems = build(
            "defaults:\n  unit_size: 0x100\n  fill: red\n  outline_width: 4pt\n  position: l\n  colour: blue\n"
            "layout:\n  0: A\n")
        self.assertEqual(problems, [])
        self.assertEqual(sequence.unit_size, 0x100)
        self.assertEqual(defaults.fill, 'red')
        self.assertEqual(defaults.position, ('il', 'ic'))
        self.assertAlmostEqual(defaults.outline_width, 4.0 / 72)
        self.assertEqual(sequence.regions[0].size, 0x100)
        self.assertEqual(sequence.regions[0].fill, 'red')

    def test_invalid_default_leaves_builtin_value(self):
        sequence, defaults, problems = build("defaults:\n  fill: reddish\n  unit_size: big\nlayout:\n  0: A\n")
        self.assertEqual(len(problems), 2)
        self.assertIsNone(defaults.fill)
        self.assertEqual(sequence.regions[0].size, mld.Sequence().unit_size)

    def test_unquoted_colour_is_reported(self):
        sequence, defaults, problems = build("defaults:\n  fill: #FFF\nlayout:\n  0: A\n")
        self.assertEqual(len(problems), 1)
        self.assertIn('quoted', problems[0])

    def test_labels_mapping_and_list_forms(self):
        sequence, defaults, problems = build(
            "layout:\n  0:\n    labels:\n      l: Left\n      r:\n        label: Right\n        colour: red\n"
            "  16:\n    labels:\n      - One\n      - label: Two\n        position: tl\n")
        self.assertEqual(problems, [])
        self.assertEqual(label_texts(sequence.regions[0]), ['Left', 'Right'])
        self.assertEqual(label_texts(sequence.regions[1]), ['One', 'Two'])

    def test_label_without_text_skipped(self):
        sequence, defaults, problems = build("layout:\n  0:\n    labels:\n      - position: tl\n")
        self.assertEqual(len(problems), 1)
        self.assertEqual(label_texts(sequence.regions[0]), [])

    def test_labels_of_wrong_type(self):
        sequence, defaults, problems = build("layout:\n  0:\n    labels: 5\n")
        self.assertEqual(len(problems), 1)

    def test_invalid_label_position_falls_back_to_default(self):
        sequence, defaults, problems = build("layout:\n  0:\n    labels:\n      - label: A\n        position: nowhere\n")
        self.assertEqual(len(problems), 1)
        self.assertEqual(label_texts(sequence.regions[0]), ['A'])

    def test_junctions_validated(self):
        sequence, defaults, problems = build(
            "layout:\n  0:\n    label: A\n    junction_high: dashed\n  16:\n    label: B\n    junction_low: wavy\n")
        self.assertEqual(len(problems), 1)
        self.assertIn('wavy', problems[0])

    def test_addresses_true(self):
        # A boolean 'addresses' must not depend on leftovers from the layout processing.
        sequence, defaults, problems = build("layout:\n  0: Low\n  0x1000: High\nautomatic:\n  addresses: true\n")
        self.assertEqual(problems, [])
        self.assertEqual(label_texts(sequence.regions[0]), ['0x0', 'Low'])
        self.assertEqual(label_texts(sequence.regions[1]), ['0x1000', 'High'])

    def test_addresses_false(self):
        sequence, defaults, problems = build("layout:\n  0: Low\nautomatic:\n  addresses: false\n")
        self.assertEqual(label_texts(sequence.regions[0]), ['Low'])

    def test_addresses_mapping(self):
        sequence, defaults, problems = build(
            "defaults:\n  unit_size: 0x1000\nlayout:\n  0: Low\n  0x1000: High\nautomatic:\n  addresses:\n    start: false\n    end: true\n"
            "    omit: 0x1000\n    side: left\n    colour: red\n")
        self.assertEqual(problems, [])
        # The end of the first region is omitted; the end of the last is not.
        self.assertEqual(label_texts(sequence.regions[0]), ['Low'])
        self.assertEqual(label_texts(sequence.regions[1]), ['0x2000', 'High'])

    def test_addresses_omit_list(self):
        sequence, defaults, problems = build(
            "layout:\n  0: Low\n  0x1000: High\nautomatic:\n  addresses:\n    omit:\n      - 0\n")
        self.assertEqual(problems, [])
        self.assertEqual(label_texts(sequence.regions[0]), ['Low'])

    def test_addresses_wrong_flag_types(self):
        sequence, defaults, problems = build(
            "layout:\n  0: Low\nautomatic:\n  addresses:\n    start: 1\n    side: up\n    omit: x\n")
        self.assertEqual(len(problems), 3)
        # And we still got the default address labels
        self.assertEqual(label_texts(sequence.regions[0]), ['0x0', 'Low'])

    def test_misspelt_addresses_key_is_reported(self):
        sequence, defaults, problems = build("layout:\n  0: A\nautomatic:\n  address: true\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("did you mean 'addresses'", problems[0])
        self.assertEqual(label_texts(sequence.regions[0]), ['A'])

    def test_discontinuities(self):
        sequence, defaults, problems = build(
            "layout:\n  0: A\n  0x100: B\nautomatic:\n  discontinuities:\n    style: dashed\n    fill: red\n")
        self.assertEqual(problems, [])
        self.assertEqual(len(sequence.regions), 3)
        self.assertEqual(sequence.regions[1].discontinuity_style, 'dashed')

    def test_discontinuities_invalid_style(self):
        sequence, defaults, problems = build(
            "layout:\n  0: A\n  0x100: B\nautomatic:\n  discontinuities:\n    style: sparkly\n")
        self.assertEqual(len(problems), 1)
        self.assertEqual(len(sequence.regions), 3)

    def test_discontinuities_disabled(self):
        sequence, defaults, problems = build(
            "layout:\n  0: A\n  0x100: B\nautomatic:\n  discontinuities: false\n")
        self.assertEqual(len(sequence.regions), 2)

    def test_explicit_discontinuity_region(self):
        sequence, defaults, problems = build("layout:\n  0:\n    discontinuity: true\n    size: 16\n")
        self.assertIsInstance(sequence.regions[0], mld.DiscontinuityRegion)


class TestMain(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def run_main(self, text, *args):
        path = os.path.join(self.dir, 'test.mld')
        with open(path, 'w') as fh:
            fh.write(text)
        output = os.path.join(self.dir, 'out.svg')
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = mld.main(list(args) + [path, '--output', output])
        return rc, stderr.getvalue(), os.path.exists(output)

    def test_good_file(self):
        rc, stderr, written = self.run_main("layout:\n  0: A\n")
        self.assertEqual((rc, stderr, written), (0, '', True))

    def test_syntax_error_is_fatal(self):
        rc, stderr, written = self.run_main("layout:\n  0: [unterminated\n")
        self.assertEqual(rc, 1)
        self.assertIn('error:', stderr)
        self.assertIn('line 2', stderr)
        self.assertFalse(written)

    def test_warning_still_writes(self):
        rc, stderr, written = self.run_main("layout:\n  0: A\nautomatic:\n  address: true\n")
        self.assertEqual(rc, 0)
        self.assertIn('warning:', stderr)
        self.assertTrue(written)

    def test_strict_makes_warning_an_error(self):
        rc, stderr, written = self.run_main("layout:\n  0: A\nautomatic:\n  address: true\n", '--strict')
        self.assertEqual(rc, 1)
        self.assertIn('error:', stderr)
        self.assertNotIn('warning:', stderr)
        self.assertFalse(written)

    def test_strict_good_file(self):
        rc, stderr, written = self.run_main("layout:\n  0: A\n", '--strict')
        self.assertEqual((rc, stderr, written), (0, '', True))

    def test_every_problem_is_reported(self):
        rc, stderr, written = self.run_main("defaults:\n  fill: nonsense\nlayout:\n  0: A\nextra: 1\n")
        self.assertEqual(rc, 0)
        self.assertEqual(len(stderr.splitlines()), 2)

    def test_missing_input(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = mld.main([os.path.join(self.dir, 'nonexistent.mld')])
        self.assertEqual(rc, 1)
        self.assertIn('error:', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
