import os
import tempfile
import unittest

from tools.report_db import ReportDB
from tools.result_reorganizer import reorganize_results_by_current_metadata


class _FakeReorganizeDB:
    def __init__(self, rows):
        self._rows = rows
        self.updated = {}

    def get_reorganize_rows(self):
        return self._rows

    def update_current_path(self, photo_key, current_path):
        self.updated[photo_key] = current_path
        return True


class ResultReorganizerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.db = ReportDB(self.root)

        self._write_file("IMG_0001.ARW")
        self._write_file("IMG_0002.ARW")

        self.db.insert_photo({
            "filename": "IMG_0001.ARW",
            "rating": 5,
            "bird_species_cn": "麻雀",
            "bird_species_en": "Sparrow",
            "current_path": "IMG_0001.ARW",
            "original_path": "IMG_0001.ARW",
        })
        self.db.insert_photo({
            "filename": "IMG_0002.ARW",
            "rating": 4,
            "bird_species_cn": None,
            "bird_species_en": None,
            "current_path": "IMG_0002.ARW",
            "original_path": "IMG_0002.ARW",
        })

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _write_file(self, relative_path, content="raw"):
        path = os.path.join(self.root, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_reorganize_moves_by_rating_and_species(self):
        summary = reorganize_results_by_current_metadata(self.root, self.db, use_en=False)

        self.assertEqual(summary["moved"], 2)
        self.assertEqual(summary["failed"], 0)

        p1 = os.path.join(self.root, "5星_精选", "麻雀", "IMG_0001.ARW")
        p2 = os.path.join(self.root, "4星_优秀", "其他", "IMG_0002.ARW")
        self.assertTrue(os.path.exists(p1))
        self.assertTrue(os.path.exists(p2))

        row = self.db.get_photo("IMG_0001.ARW")
        self.assertEqual(
            row["current_path"],
            os.path.join("5星_精选", "麻雀", "IMG_0001.ARW"),
        )

    def test_reorganize_skips_missing_files(self):
        os.remove(os.path.join(self.root, "IMG_0002.ARW"))

        summary = reorganize_results_by_current_metadata(self.root, self.db, use_en=False)

        self.assertEqual(summary["missing"], 1)
        self.assertEqual(summary["failed"], 0)

    def test_reorganize_handles_destination_collision_without_overwrite(self):
        self._write_file(os.path.join("5星_精选", "麻雀", "IMG_0001.ARW"), content="existing")

        summary = reorganize_results_by_current_metadata(self.root, self.db, use_en=False)

        self.assertEqual(summary["moved"], 2)
        self.assertFalse(os.path.exists(os.path.join(self.root, "IMG_0001.ARW")))
        self.assertTrue(
            os.path.exists(os.path.join(self.root, "5星_精选", "麻雀", "IMG_0001_1.ARW"))
        )

        with open(os.path.join(self.root, "5星_精选", "麻雀", "IMG_0001.ARW"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "existing")

        row = self.db.get_photo("IMG_0001.ARW")
        self.assertEqual(
            row["current_path"],
            os.path.join("5星_精选", "麻雀", "IMG_0001_1.ARW"),
        )

    def test_reorganize_use_en_uses_english_species_and_other_fallback(self):
        summary = reorganize_results_by_current_metadata(self.root, self.db, use_en=True)

        self.assertEqual(summary["moved"], 2)
        self.assertTrue(
            os.path.exists(os.path.join(self.root, "5星_精选", "Sparrow", "IMG_0001.ARW"))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.root, "4星_优秀", "Other", "IMG_0002.ARW"))
        )

    def test_reorganize_rolls_back_file_when_db_update_fails_after_move(self):
        self.db.delete_photo("IMG_0002.ARW")
        os.remove(os.path.join(self.root, "IMG_0002.ARW"))

        original_update = self.db.update_current_path

        def _always_fail(_photo_key, _current_path):
            return False

        self.db.update_current_path = _always_fail
        try:
            summary = reorganize_results_by_current_metadata(self.root, self.db, use_en=False)
        finally:
            self.db.update_current_path = original_update

        expected_target = os.path.join(self.root, "5星_精选", "麻雀", "IMG_0001.ARW")
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["moved"], 0)
        self.assertTrue(os.path.exists(os.path.join(self.root, "IMG_0001.ARW")))
        self.assertFalse(os.path.exists(expected_target))
        row = self.db.get_photo("IMG_0001.ARW")
        self.assertEqual(row["current_path"], "IMG_0001.ARW")

    def test_reorganize_merged_row_uses_source_dir_base_and_relative_current_path(self):
        with tempfile.TemporaryDirectory() as root:
            src_rel = os.path.join("subdir", "IMG_0003.ARW")
            src_abs = os.path.join(root, src_rel)
            os.makedirs(os.path.dirname(src_abs), exist_ok=True)
            with open(src_abs, "w", encoding="utf-8") as f:
                f.write("raw")

            row = {
                "source_dir": "subdir",
                "filename": "IMG_0003.ARW",
                "rating": 5,
                "bird_species_cn": "麻雀",
                "bird_species_en": "Sparrow",
                "current_path": "IMG_0003.ARW",
                "original_path": "IMG_0003.ARW",
            }
            fake_db = _FakeReorganizeDB([row])

            summary = reorganize_results_by_current_metadata(root, fake_db, use_en=False)

            expected_rel = os.path.join("5星_精选", "麻雀", "IMG_0003.ARW")
            expected_abs = os.path.join(root, "subdir", expected_rel)

            self.assertEqual(summary["moved"], 1)
            self.assertTrue(os.path.exists(expected_abs))
            self.assertEqual(
                fake_db.updated[("subdir", "IMG_0003.ARW")],
                expected_rel,
            )

    def test_reorganize_invalid_rating_defaults_to_zero_star(self):
        self.db.insert_photo({
            "filename": "IMG_BAD_RATING.ARW",
            "rating": "not-an-int",
            "bird_species_cn": "麻雀",
            "bird_species_en": "Sparrow",
            "current_path": "IMG_BAD_RATING.ARW",
            "original_path": "IMG_BAD_RATING.ARW",
        })
        self._write_file("IMG_BAD_RATING.ARW")

        summary = reorganize_results_by_current_metadata(self.root, self.db, use_en=False)

        self.assertEqual(summary["failed"], 0)
        self.assertTrue(
            os.path.exists(os.path.join(self.root, "0星_放弃", "麻雀", "IMG_BAD_RATING.ARW"))
        )

    def test_reorganize_sanitizes_reserved_species_folder_name(self):
        self.db.insert_photo({
            "filename": "IMG_RESERVED.ARW",
            "rating": 5,
            "bird_species_cn": "CON",
            "bird_species_en": "CON",
            "current_path": "IMG_RESERVED.ARW",
            "original_path": "IMG_RESERVED.ARW",
        })
        self._write_file("IMG_RESERVED.ARW")

        summary = reorganize_results_by_current_metadata(self.root, self.db, use_en=False)

        self.assertEqual(summary["failed"], 0)
        self.assertTrue(
            os.path.exists(os.path.join(self.root, "5星_精选", "CON_", "IMG_RESERVED.ARW"))
        )


if __name__ == "__main__":
    unittest.main()
