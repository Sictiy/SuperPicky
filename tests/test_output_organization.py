import os
import unittest

from tools.output_organization import (
    build_organization_folder,
    sanitize_folder_name,
    should_include_species_folder,
)


class OutputOrganizationTests(unittest.TestCase):
    def test_rating_and_species_folder(self):
        folder = build_organization_folder(
            rating=5,
            species_name="麻雀",
            organize_by_rating=True,
            organize_by_species=True,
            use_en=False,
        )
        self.assertEqual(folder, os.path.join("5星_精选", "麻雀"))

    def test_rating_only_folder(self):
        folder = build_organization_folder(
            rating=4,
            species_name="麻雀",
            organize_by_rating=True,
            organize_by_species=False,
            use_en=False,
        )
        self.assertEqual(folder, "4星_优秀")

    def test_species_only_folder(self):
        folder = build_organization_folder(
            rating=4,
            species_name="麻雀",
            organize_by_rating=False,
            organize_by_species=True,
            use_en=False,
        )
        self.assertEqual(folder, "麻雀")

    def test_species_only_uses_other_for_empty_species(self):
        folder = build_organization_folder(
            rating=4,
            species_name="",
            organize_by_rating=False,
            organize_by_species=True,
            use_en=False,
        )
        self.assertEqual(folder, "其他")

    def test_no_organization_returns_none(self):
        folder = build_organization_folder(
            rating=4,
            species_name="麻雀",
            organize_by_rating=False,
            organize_by_species=False,
            use_en=False,
        )
        self.assertIsNone(folder)

    def test_rating_and_species_skips_species_for_low_rating(self):
        folder = build_organization_folder(
            rating=1,
            species_name="麻雀",
            organize_by_rating=True,
            organize_by_species=True,
            use_en=False,
        )
        self.assertEqual(folder, "1星_普通")

    def test_rating_and_species_uses_custom_fallback_for_empty_species(self):
        folder = build_organization_folder(
            rating=5,
            species_name="",
            organize_by_rating=True,
            organize_by_species=True,
            use_en=False,
            species_fallback="其他鸟类",
        )
        self.assertEqual(folder, os.path.join("5星_精选", "其他鸟类"))

    def test_english_rating_folder(self):
        folder = build_organization_folder(
            rating=5,
            species_name="",
            organize_by_rating=True,
            organize_by_species=True,
            use_en=True,
            species_fallback="Other_Birds",
        )
        self.assertEqual(folder, os.path.join("5star_picked", "Other_Birds"))

    def test_species_folder_rule(self):
        self.assertFalse(should_include_species_folder(1, True, True))
        self.assertTrue(should_include_species_folder(2, True, True))
        self.assertTrue(should_include_species_folder(1, False, True))

    def test_sanitize_windows_reserved_name(self):
        self.assertEqual(sanitize_folder_name("CON", "其他"), "CON_")

    def test_sanitize_windows_reserved_name_with_extension(self):
        self.assertEqual(sanitize_folder_name("nul.folder", "其他"), "nul.folder_")

    def test_sanitize_invalid_path_characters(self):
        self.assertEqual(sanitize_folder_name("麻雀/幼鸟:精选", "其他"), "麻雀_幼鸟_精选")

    def test_sanitize_trailing_dots_and_spaces(self):
        self.assertEqual(sanitize_folder_name("麻雀. ", "其他"), "麻雀")


if __name__ == "__main__":
    unittest.main()
