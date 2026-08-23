"""
rename_resources.py

Walks a folder tree and renames files that have spaces (or other
characters risky for GitHub/jsDelivr URLs) into clean, URL-safe names.

By default this is a DRY RUN: it prints what it *would* rename and
writes a log, but doesn't touch any files. Pass --apply to actually
rename them.

Usage:
    python rename_resources.py "/path/to/folder"              # dry run, just shows the plan
    python rename_resources.py "/path/to/folder" --apply       # actually renames
    python rename_resources.py "/path/to/folder" --apply --strict
        # --strict also strips ® ™ , ( ) and other symbols, not just spaces
"""

import os
import sys
import csv
import re
from pathlib import Path

# Skip these entirely (temp/lock files, hidden files)
SKIP_PREFIXES = (".", "~$")


def clean_name(filename, strict=False):
    stem = Path(filename).stem
    ext = Path(filename).suffix

    new_stem = stem.replace(" ", "-")

    if strict:
        # Strip anything that isn't a letter, number, hyphen, or underscore
        new_stem = re.sub(r"[^A-Za-z0-9\-_]", "-", new_stem)
        # Collapse multiple hyphens into one
        new_stem = re.sub(r"-{2,}", "-", new_stem)
        new_stem = new_stem.strip("-")

    return f"{new_stem}{ext}"


def plan_renames(root_path, strict=False):
    root = Path(root_path).resolve()
    if not root.exists():
        print(f"Folder not found: {root}")
        sys.exit(1)

    plan = []

    for dirpath, dirnames, filenames in os.walk(root):
        used_names = set(filenames)  # track names already in this folder

        for filename in filenames:
            if filename.startswith(SKIP_PREFIXES):
                continue

            new_name = clean_name(filename, strict=strict)

            if new_name == filename:
                continue  # nothing to do

            # Avoid collisions if the cleaned name already exists in this folder
            candidate = new_name
            counter = 2
            while candidate in used_names and candidate != filename:
                stem = Path(new_name).stem
                ext = Path(new_name).suffix
                candidate = f"{stem}-{counter}{ext}"
                counter += 1

            used_names.add(candidate)

            plan.append({
                "folder": str(Path(dirpath).relative_to(root)),
                "old_name": filename,
                "new_name": candidate,
                "old_path": str(Path(dirpath) / filename),
                "new_path": str(Path(dirpath) / candidate),
            })

    return plan


def write_log(plan, log_path="rename_log.csv"):
    if not plan:
        return
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["folder", "old_name", "new_name", "old_path", "new_path"])
        writer.writeheader()
        writer.writerows(plan)


def apply_renames(plan):
    done = 0
    for item in plan:
        old_path = Path(item["old_path"])
        new_path = Path(item["new_path"])
        try:
            old_path.rename(new_path)
            done += 1
        except OSError as e:
            print(f"  FAILED: {item['old_name']} -> {item['new_name']} ({e})")
    return done


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python rename_resources.py "/path/to/folder" [--apply] [--strict]')
        sys.exit(1)

    folder = sys.argv[1]
    apply = "--apply" in sys.argv
    strict = "--strict" in sys.argv

    plan = plan_renames(folder, strict=strict)

    if not plan:
        print("No files need renaming. You're clean.")
        sys.exit(0)

    print(f"{len(plan)} file(s) would be renamed:\n")
    for item in plan[:20]:
        print(f"  [{item['folder']}]  {item['old_name']}  ->  {item['new_name']}")
    if len(plan) > 20:
        print(f"  ... and {len(plan) - 20} more (see rename_log.csv)")

    write_log(plan)
    print(f"\nFull plan written to rename_log.csv")

    if apply:
        print("\nApplying renames...")
        done = apply_renames(plan)
        print(f"Renamed {done}/{len(plan)} files.")
    else:
        print("\nThis was a DRY RUN — no files were changed.")
        print("Review rename_log.csv, then re-run with --apply to actually rename.")
