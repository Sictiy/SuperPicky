import tempfile
import unittest
from pathlib import Path

from tools.report_db import ReportDB


class ReportDBFilterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = ReportDB(self._tmp.name)
        self.addCleanup(self.db.close)

        fixtures = [
            {
                "filename": "a",
                "rating": 5,
                "bird_species_cn": "喜鹊",
                "focus_status": "BEST",
                "is_flying": 1,
            },
            {
                "filename": "b",
                "rating": 0,
                "bird_species_cn": "   ",
                "focus_status": None,
                "is_flying": None,
            },
            {
                "filename": "c",
                "rating": 3,
                "bird_species_cn": "麻雀",
                "focus_status": "GOOD",
                "is_flying": 0,
            },
            {
                "filename": "d",
                "rating": -1,
                "bird_species_cn": None,
                "focus_status": None,
                "is_flying": None,
            },
            {
                "filename": "e",
                "rating": 3,
                "bird_species_cn": "喜鹊",
                "focus_status": "BAD",
                "is_flying": 1,
            },
        ]
        for row in fixtures:
            self.db.insert_photo(row)

    @staticmethod
    def _filenames(rows):
        return [row["filename"] for row in rows]

    def test_other_species_filter_includes_empty_species(self):
        rows = self.db.get_photos_by_filters({
            "ratings": [0, 1, 2, 3, 4, 5],
            "bird_species_cn": ReportDB.OTHER_SPECIES_SENTINEL,
            "sort_by": "filename",
        })
        self.assertEqual(self._filenames(rows), ["b"])

    def test_other_species_filter_excludes_no_bird_when_no_ratings_filter(self):
        rows = self.db.get_photos_by_filters({
            "bird_species_cn": ReportDB.OTHER_SPECIES_SENTINEL,
            "sort_by": "filename",
        })
        self.assertEqual(self._filenames(rows), ["b"])

    def test_available_ratings_ignores_current_rating_filter(self):
        rows = self.db.get_available_ratings({
            "ratings": [3],
            "focus_statuses": ["BEST", "GOOD"],
            "is_flying": [0, 1],
            "sort_by": "filename",
        })
        self.assertEqual(rows, [-1, 0, 3, 5])

    def test_available_ratings_respects_species_filter(self):
        rows = self.db.get_available_ratings({
            "ratings": [3],
            "bird_species_cn": "喜鹊",
            "focus_statuses": ["BEST", "GOOD"],
            "is_flying": [0, 1],
            "sort_by": "filename",
        })
        self.assertEqual(rows, [5])

    def test_available_ratings_other_species_excludes_no_bird(self):
        rows = self.db.get_available_ratings({
            "bird_species_cn": ReportDB.OTHER_SPECIES_SENTINEL,
        })
        self.assertEqual(rows, [0])

    def test_available_ratings_ignores_null_ratings(self):
        self.db.insert_photo({
            "filename": "null_rating",
            "rating": None,
            "bird_species_cn": "喜鹊",
            "focus_status": "GOOD",
            "is_flying": 0,
        })

        rows = self.db.get_available_ratings()
        self.assertEqual(rows, [-1, 0, 3, 5])


if __name__ == "__main__":
    unittest.main()
