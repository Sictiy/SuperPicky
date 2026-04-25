#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reorganize result files by current metadata without rescoring/re-identification."""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, Optional

from constants import get_rating_folder_name


_INVALID_FOLDER_CHARS = set('<>:"/\\|?*')
_RESERVED_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def _sanitize_folder_name(name: Optional[str], fallback: str) -> str:
    """Sanitize folder name for Windows/macOS while preserving unicode text."""
    text = (name or "").strip()
    if not text:
        return fallback

    cleaned_chars = []
    for ch in text:
        if ord(ch) < 32 or ch in _INVALID_FOLDER_CHARS:
            cleaned_chars.append("_")
        else:
            cleaned_chars.append(ch)

    cleaned = "".join(cleaned_chars).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        return fallback

    if cleaned.upper() in _RESERVED_DEVICE_NAMES:
        cleaned = f"{cleaned}_"

    return cleaned


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _resolve_row_base_dirs(root_dir: str, row: Dict[str, Any]) -> tuple[str, str]:
    """Return (base_dir, stored_relative_root) for a row."""
    source_dir = (row.get("source_dir") or "").strip()
    if source_dir:
        base_dir = os.path.join(root_dir, source_dir)
        return base_dir, base_dir
    return root_dir, root_dir


def _choose_source_path(root_dir: str, row: Dict[str, Any]) -> Optional[str]:
    """Resolve source path by priority: current_path -> original_path -> filename."""
    source_dir = (row.get("source_dir") or "").strip()
    base_dir, _ = _resolve_row_base_dirs(root_dir, row)
    candidates = []

    for key in ("current_path", "original_path", "filename"):
        value = row.get(key)
        if not value:
            continue

        source_value = str(value)
        if os.path.isabs(source_value):
            candidates.append(source_value)
            continue

        if source_dir:
            # Merged/source rows: resolve against source base first.
            candidates.append(os.path.join(base_dir, source_value))
            # Legacy fallback: keep root-based resolution.
            candidates.append(os.path.join(root_dir, source_value))
        else:
            # Regular ReportDB rows: relative to root_dir.
            candidates.append(os.path.join(root_dir, source_value))

    seen = set()
    deduped = []
    for candidate in candidates:
        normalized = _normalize_path(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)

    for candidate in deduped:
        if os.path.isfile(candidate):
            return candidate
    return None


def _build_photo_key(row: Dict[str, Any]):
    source_dir = row.get("source_dir")
    filename = row.get("filename")
    if source_dir not in (None, "") and filename:
        return (source_dir, filename)
    return filename


def _unique_destination_path(dest_path: str) -> str:
    if not os.path.exists(dest_path):
        return dest_path

    folder = os.path.dirname(dest_path)
    base = os.path.basename(dest_path)
    stem, ext = os.path.splitext(base)

    index = 1
    while True:
        candidate = os.path.join(folder, f"{stem}_{index}{ext}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def reorganize_results_by_current_metadata(root_dir: str, db, use_en: bool = False) -> dict:
    """
    Reorganize existing result files by current manual rating/species metadata.

    This function only moves files and updates current_path in DB wrappers.
    It does not invoke scoring, bird identification, exif writing, or post-adjustment.
    """
    root_abs = os.path.abspath(root_dir)
    rows = db.get_reorganize_rows() or []

    summary = {
        "moved": 0,
        "unchanged": 0,
        "missing": 0,
        "failed": 0,
    }

    species_column = "bird_species_en" if use_en else "bird_species_cn"
    species_fallback = "Other" if use_en else "其他"

    for row in rows:
        src_path = _choose_source_path(root_abs, row)
        if not src_path:
            summary["missing"] += 1
            continue

        try:
            base_dir, relative_root = _resolve_row_base_dirs(root_abs, row)

            try:
                rating = int(row.get("rating") or 0)
            except (TypeError, ValueError):
                rating = 0

            rating_folder = get_rating_folder_name(rating)
            species_name = _sanitize_folder_name(row.get(species_column), species_fallback)
            filename = os.path.basename(src_path)

            target_dir = os.path.join(base_dir, rating_folder, species_name)
            desired_dest = os.path.join(target_dir, filename)

            src_norm = _normalize_path(src_path)
            dest_norm = _normalize_path(desired_dest)
            photo_key = _build_photo_key(row)

            os.makedirs(target_dir, exist_ok=True)

            if src_norm == dest_norm:
                relative_dest = os.path.relpath(desired_dest, relative_root)
                if photo_key and row.get("current_path") != relative_dest:
                    ok = db.update_current_path(photo_key, relative_dest)
                    if not ok:
                        summary["failed"] += 1
                        continue
                summary["unchanged"] += 1
                continue

            final_dest = _unique_destination_path(desired_dest)
            shutil.move(src_path, final_dest)

            relative_dest = os.path.relpath(final_dest, relative_root)
            if not photo_key or not db.update_current_path(photo_key, relative_dest):
                rollback_ok = False
                try:
                    if not os.path.exists(src_path):
                        src_parent = os.path.dirname(src_path)
                        os.makedirs(src_parent, exist_ok=True)
                        shutil.move(final_dest, src_path)
                        rollback_ok = True
                except Exception as rollback_error:
                    print(f"[result_reorganizer] rollback failed: {rollback_error}")

                if not rollback_ok:
                    print(
                        f"[result_reorganizer] db update failed; moved file remains at: {final_dest}"
                    )

                summary["failed"] += 1
                continue

            summary["moved"] += 1
        except Exception:
            summary["failed"] += 1

    return summary
