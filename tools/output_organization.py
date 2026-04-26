#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Optional

from constants import RATING_FOLDER_NAMES, RATING_FOLDER_NAMES_EN

_INVALID_FOLDER_CHARS = set('<>:"/\\|?*')
_RESERVED_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_folder_name(name: Optional[str], fallback: str) -> str:
    cleaned = (name or "").strip() or fallback
    cleaned = "".join(
        "_" if ord(char) < 32 or char in _INVALID_FOLDER_CHARS else char
        for char in cleaned
    ).strip(" .")

    if cleaned in {"", ".", ".."}:
        cleaned = fallback.strip(" .") or "_"

    if cleaned.split(".", 1)[0].upper() in _RESERVED_DEVICE_NAMES:
        cleaned += "_"

    return cleaned


def should_include_species_folder(
    rating: int,
    organize_by_rating: bool,
    organize_by_species: bool,
) -> bool:
    return bool(organize_by_species and (not organize_by_rating or int(rating or 0) >= 2))


def build_organization_folder(
    rating: int,
    species_name: Optional[str],
    organize_by_rating: bool,
    organize_by_species: bool,
    use_en: bool = False,
    species_fallback: Optional[str] = None,
) -> Optional[str]:
    parts = []

    if organize_by_rating:
        rating_folders = RATING_FOLDER_NAMES_EN if use_en else RATING_FOLDER_NAMES
        parts.append(rating_folders.get(int(rating or 0), rating_folders.get(0, "0star_reject")))

    if should_include_species_folder(rating, organize_by_rating, organize_by_species):
        fallback = species_fallback or ("Other" if use_en else "其他")
        parts.append(sanitize_folder_name(species_name, fallback))

    if not parts:
        return None

    return os.path.join(*parts)
