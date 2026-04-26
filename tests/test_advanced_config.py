import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from advanced_config import AdvancedConfig


class AdvancedConfigOutputOrganizationTests(unittest.TestCase):
    def test_defaults_enable_both_organization_dimensions(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = AdvancedConfig(config_file=f"{d}/advanced_config.json")
            self.assertTrue(cfg.organize_by_rating)
            self.assertTrue(cfg.organize_by_species)
            self.assertEqual(cfg.last_directory, "")

    def test_setters_persist_organization_and_last_directory(self):
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/advanced_config.json"
            cfg = AdvancedConfig(config_file=path)
            cfg.set_organize_by_rating(False)
            cfg.set_organize_by_species(True)
            cfg.set_last_directory(d)
            cfg.save()
            loaded = AdvancedConfig(config_file=path)
            self.assertFalse(loaded.organize_by_rating)
            self.assertTrue(loaded.organize_by_species)
            self.assertEqual(loaded.last_directory, os.path.normpath(d))

    def test_add_recent_directory_normalizes_and_dedupes_trailing_slash_variants(self):
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/advanced_config.json"
            cfg = AdvancedConfig(config_file=path)
            photos_dir = Path(d) / "photos"

            cfg.add_recent_directory(str(photos_dir) + os.sep)
            cfg.add_recent_directory(str(photos_dir))

            expected = os.path.normpath(str(photos_dir))
            self.assertEqual(cfg.get_recent_directories(), [expected])
            self.assertEqual(cfg.last_directory, expected)

    def test_add_recent_directory_empty_string_is_noop_and_does_not_save(self):
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/advanced_config.json"
            cfg = AdvancedConfig(config_file=path)
            first_dir = Path(d) / "first"
            cfg.add_recent_directory(str(first_dir))

            previous_recent = list(cfg.get_recent_directories())
            previous_last = cfg.last_directory

            with patch.object(cfg, "save") as mock_save:
                cfg.add_recent_directory("")
                mock_save.assert_not_called()

            self.assertEqual(cfg.get_recent_directories(), previous_recent)
            self.assertEqual(cfg.last_directory, previous_last)

    def test_add_recent_directory_keeps_only_10_most_recent_first(self):
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/advanced_config.json"
            cfg = AdvancedConfig(config_file=path)

            added = []
            for i in range(12):
                directory = os.path.normpath(str(Path(d) / f"dir{i}"))
                added.append(directory)
                cfg.add_recent_directory(directory)

            expected = list(reversed(added))[:10]
            self.assertEqual(len(cfg.get_recent_directories()), 10)
            self.assertEqual(cfg.get_recent_directories(), expected)
            self.assertEqual(cfg.last_directory, expected[0])

    def test_clear_recent_directories_clears_history_and_last_directory(self):
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/advanced_config.json"
            cfg = AdvancedConfig(config_file=path)
            cfg.add_recent_directory(str(Path(d) / "a"))
            cfg.add_recent_directory(str(Path(d) / "b"))

            cfg.clear_recent_directories()

            self.assertEqual(cfg.get_recent_directories(), [])
            self.assertEqual(cfg.last_directory, "")

            loaded = AdvancedConfig(config_file=path)
            self.assertEqual(loaded.get_recent_directories(), [])
            self.assertEqual(loaded.last_directory, "")


if __name__ == "__main__":
    unittest.main()
