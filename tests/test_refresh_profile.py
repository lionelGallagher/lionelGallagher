import tempfile
import unittest
from datetime import date
from pathlib import Path

try:
    from scripts.refresh_profile import elapsed, save_svg, select_first_commit
except ImportError:
    elapsed = save_svg = select_first_commit = None


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(elapsed, "experience generator is not implemented")

    def test_current_duration_uses_completed_calendar_months(self):
        self.assertEqual(elapsed(date(2022, 11, 9), date(2026, 10, 30)), (3, 11, 21))

    def test_anniversary_advances_year(self):
        self.assertEqual(elapsed(date(2022, 11, 9), date(2026, 11, 9)), (4, 0, 0))

    def test_month_end_is_clamped(self):
        self.assertEqual(elapsed(date(2025, 1, 31), date(2025, 2, 28)), (0, 1, 0))

    def test_leap_day_anniversary(self):
        self.assertEqual(elapsed(date(2024, 2, 29), date(2025, 2, 28)), (1, 0, 0))

    def test_future_start_is_rejected(self):
        with self.assertRaises(ValueError):
            elapsed(date(2027, 1, 1), date(2026, 10, 30))


class FirstCommitTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(select_first_commit, "commit selection is not implemented")
        self.known = {
            "date": "2022-11-09T10:31:35Z",
            "sha": "verified",
            "url": "https://github.com/owner/repo/commit/verified",
        }

    def item(self, author, when):
        return {"author": {"login": author}, "commit": {"author": {"date": when}},
                "sha": "candidate", "html_url": "https://github.com/owner/repo/commit/candidate"}

    def test_fork_original_author_does_not_change_baseline(self):
        items = [self.item("someone-else", "2010-01-01T00:00:00Z")]
        self.assertEqual(select_first_commit(items, self.known, "lionelGallagher"), self.known)

    def test_missing_search_history_does_not_erase_earlier_known_commit(self):
        items = [self.item("lionelGallagher", "2025-01-01T00:00:00Z")]
        self.assertEqual(select_first_commit(items, self.known, "lionelGallagher"), self.known)

    def test_verified_earlier_author_commit_can_extend_history(self):
        items = [self.item("lionelGallagher", "2021-01-01T00:00:00Z")]
        self.assertEqual(select_first_commit(items, self.known, "lionelGallagher")["date"],
                         "2021-01-01T00:00:00Z")


class CardCacheTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(save_svg, "SVG cache is not implemented")

    def test_error_svg_does_not_overwrite_last_successful_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.svg"
            original = b'<svg xmlns="http://www.w3.org/2000/svg"><text>good card</text></svg>'
            path.write_bytes(original)
            with self.assertRaises(ValueError):
                save_svg(path, b'<svg xmlns="http://www.w3.org/2000/svg"><text>Something went wrong!</text></svg>')
            self.assertEqual(path.read_bytes(), original)

    def test_html_error_does_not_overwrite_last_successful_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.svg"
            path.write_bytes(b"previous good card")
            with self.assertRaises(ValueError):
                save_svg(path, b"<html>Payment required</html>")
            self.assertEqual(path.read_bytes(), b"previous good card")

    def test_valid_svg_is_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.svg"
            payload = b'<svg xmlns="http://www.w3.org/2000/svg"><text>GitHub Stats</text></svg>'
            save_svg(path, payload)
            self.assertEqual(path.read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
