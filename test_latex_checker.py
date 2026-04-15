import unittest

from latex_checker import analyze_text, fix_spacing_inside_delimiters, fix_remove_bold_commands


class LatexCheckerRegressionTests(unittest.TestCase):
    def test_fix_spacing_inside_straight_quotes_preserves_outer_spaces(self):
        text = 'This is " an " example.'
        fixed, stats = fix_spacing_inside_delimiters(text)

        self.assertEqual(fixed, 'This is "an" example.')
        self.assertGreaterEqual(stats["removed"], 2)

        spacing_issues = [issue for issue in analyze_text(fixed) if issue["kind"] == "spacing"]
        self.assertEqual(spacing_issues, [])

    def test_fix_spacing_inside_parentheses(self):
        text = 'The ordered tuple ( a, b, c ) should be fixed.'
        fixed, _ = fix_spacing_inside_delimiters(text)

        self.assertEqual(fixed, 'The ordered tuple (a, b, c) should be fixed.')

    def test_display_math_punctuation_is_not_flagged(self):
        display_math = '$$a,b:c$$'
        inline_math = '$a,b:c$'

        display_kinds = [issue["kind"] for issue in analyze_text(display_math)]
        inline_kinds = [issue["kind"] for issue in analyze_text(inline_math)]

        self.assertNotIn("punct", display_kinds)
        self.assertIn("punct", inline_kinds)

    def test_remove_bold_commands_keeps_contents(self):
        text = r'This has \mathbf{A} and \boldsymbol{x+y} inside.'
        fixed, stats = fix_remove_bold_commands(text)

        self.assertEqual(fixed, 'This has A and x+y inside.')
        self.assertEqual(stats["removed"], 2)

    def test_remove_bold_commands_leaves_plain_text_unchanged(self):
        text = 'Nothing to change here.'
        fixed, stats = fix_remove_bold_commands(text)

        self.assertEqual(fixed, text)
        self.assertEqual(stats["removed"], 0)


if __name__ == "__main__":
    unittest.main()
