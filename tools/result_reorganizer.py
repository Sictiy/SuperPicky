#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reorganize result files by current metadata without rescoring/re-identification."""

from __future__ import annotations

import os
import shutil
from typing import Any, Callable, Dict, Optional

from advanced_config import get_advanced_config
from tools.output_organization import build_organization_folder

_LEGACY_OTHER_BIRDS = {
    False: "其他鸟类",
    True: "Other_Birds",
}


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


def _remove_empty_directories(start_dirs: set[str], stop_dirs: set[str]) -> int:
    removed = 0
    stops = {_normalize_path(path) for path in stop_dirs}
    for start_dir in sorted(start_dirs, key=lambda path: path.count(os.sep), reverse=True):
        current = os.path.abspath(start_dir)
        while os.path.isdir(current) and _normalize_path(current) not in stops:
            try:
                os.rmdir(current)
                removed += 1
            except OSError:
                break
            current = os.path.dirname(current)
    return removed


def reorganize_results_by_current_metadata(
    root_dir: str,
    db,
    use_en: bool = False,
    organize_by_rating: bool | None = None,
    organize_by_species: bool | None = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """
    Reorganize existing result files by current manual rating/species metadata.

    This function only moves files and updates current_path in DB wrappers.
    It does not invoke scoring, bird identification, exif writing, or post-adjustment.
    """
    if organize_by_rating is None or organize_by_species is None:
        cfg = get_advanced_config()
        if organize_by_rating is None:
            organize_by_rating = cfg.organize_by_rating
        if organize_by_species is None:
            organize_by_species = cfg.organize_by_species

    root_abs = os.path.abspath(root_dir)
    rows = db.get_reorganize_rows() or []

    summary = {
        "moved": 0,
        "unchanged": 0,
        "missing": 0,
        "failed": 0,
        "removed_dirs": 0,
    }
    moved_from_dirs = set()
    stop_dirs = {root_abs}

    species_column = "bird_species_en" if use_en else "bird_species_cn"
    total = len(rows)

    for index, row in enumerate(rows, start=1):
        if progress_callback:
            progress_callback(index - 1, total)
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

            organization_folder = build_organization_folder(
                rating,
                row.get(species_column),
                organize_by_rating=organize_by_rating,
                organize_by_species=organize_by_species,
                use_en=use_en,
                species_fallback=_LEGACY_OTHER_BIRDS[bool(use_en)] if organize_by_rating else None,
            )
            filename = os.path.basename(src_path)
            photo_key = _build_photo_key(row)

            if organization_folder is None:
                relative_src = os.path.relpath(src_path, relative_root)
                if photo_key and row.get("current_path") != relative_src:
                    ok = db.update_current_path(photo_key, relative_src)
                    if not ok:
                        summary["failed"] += 1
                        continue
                summary["unchanged"] += 1
                continue

            target_dir = os.path.join(base_dir, organization_folder)
            desired_dest = os.path.join(target_dir, filename)

            src_norm = _normalize_path(src_path)
            dest_norm = _normalize_path(desired_dest)

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
            source_dir = os.path.dirname(src_path)
            shutil.move(src_path, final_dest)
            moved_from_dirs.add(source_dir)
            stop_dirs.add(relative_root)

            relative_dest = os.path.relpath(final_dest, relative_root)
            if not photo_key or not db.update_current_path(photo_key, relative_dest):
                rollback_ok = False
                try:
                    if not os.path.exists(src_path):
                        src_parent = os.path.dirname(src_path)
                        os.makedirs(src_parent, exist_ok=True)
                        shutil.move(final_dest, src_path)
                        moved_from_dirs.discard(source_dir)
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

        if progress_callback:
            progress_callback(index, total)

    summary["removed_dirs"] = _remove_empty_directories(moved_from_dirs, stop_dirs)
    return summary
