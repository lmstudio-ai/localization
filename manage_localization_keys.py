#!/usr/bin/env python3
"""
Script to manage localization keys:
1. Find keys in localization files not used in code
2. Find keys in code not in localization files
3. Remove unused keys from localization files

Uses filename as prefix for keys (e.g., 'chat:key' for a key in chat.json)
Handles both dot notation (parent.child) and slash notation (parent/child).

Usage:
    python manage_localization_keys.py [--language LANG] [--output-file OUTPUT_FILE]
                                      [--show-matched] [--verbose] [--backup]
                                      [--remove] [--remove-dry-run]

Arguments:
    --language LANG       Language code to process (default: 'en')
    --output-file FILE    Optional file to write results to (in addition to console)
    --show-matched        Show matched keys (those that exist in both code and localization files)
    --verbose             Show detailed information about the process
    --backup              Create backup of original files before making changes
    --remove              Remove unused keys from localization files
    --remove-dry-run      Show what would be removed without making changes
"""
import json
import os
import re
import argparse
import shutil
from pathlib import Path
from datetime import datetime
import copy

# Paths
SRC_DIR = os.path.join("electron", "src")
LOCALIZATION_DIR = os.path.join("electron", "data", "localization")


def find_used_keys_in_code():
    """Find all localization keys used in the source code."""
    used_keys = set()

    # Get all possible filename prefixes from the localization directory
    prefixes = set()
    lang_dir = os.path.join(LOCALIZATION_DIR, "en")
    if os.path.exists(lang_dir):
        prefixes = {os.path.splitext(file)[0] for file in os.listdir(lang_dir)
                   if file.endswith('.json')}

    # Pattern to match localization keys using file prefixes
    prefix_pattern = '|'.join(re.escape(p) for p in prefixes)
    if not prefix_pattern:
        print("No localization files found, cannot determine prefixes")
        return used_keys

    pattern = re.compile(f'({prefix_pattern}):([A-Za-z0-9_/.-]+)')

    # Recursively scan all files in the src directory
    for root, _, files in os.walk(SRC_DIR):
        for file in files:
            # Skip binary files and focus on source files
            if file.endswith(('.jpg', '.png', '.gif', '.svg', '.ttf', '.woff', '.mp3', '.mp4')):
                continue

            if not file.endswith(('.ts', '.tsx', '.js', '.jsx', '.html', '.css')):
                continue

            file_path = os.path.join(root, file)

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Find all localization keys in the file
                matches = pattern.findall(content)

                for prefix, key in matches:
                    # Store the complete key with prefix
                    used_keys.add(f"{prefix}:{key}")

            except Exception as e:
                print(f"Error reading file {file_path}: {str(e)}")

    return used_keys


def load_localization_keys(language='en'):
    """Load all keys from all localization files in the specified language folder."""
    all_keys = set()
    leaf_keys = set()  # Only keys that have actual string values (not parent objects)
    leaf_paths = set()  # Dot-notation paths for leaf keys without prefixes
    localization_data = {}
    parent_keys = set()  # Keys that are parent objects, not leaf values

    lang_dir = os.path.join(LOCALIZATION_DIR, language)
    if not os.path.exists(lang_dir):
        print(f"Error: Localization directory for {language} not found at {lang_dir}")
        return all_keys, leaf_keys, leaf_paths, localization_data, parent_keys

    # Process all JSON files in the localization directory
    for file_name in os.listdir(lang_dir):
        if not file_name.endswith('.json'):
            continue

        file_path = os.path.join(lang_dir, file_name)
        file_prefix = file_name.replace('.json', '')

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                localization_data[file_prefix] = json_data

            def collect_keys(data, prefix="", path=None):
                if isinstance(data, dict):
                    for key, value in data.items():
                        full_key = f"{prefix}{key}" if prefix else key
                        full_path = f"{path}/{key}" if path else key

                        # Add key with dot notation (prefix:parent.child)
                        prefixed_key = f"{file_prefix}:{full_key}"
                        all_keys.add(prefixed_key)

                        # Add key with slash notation (prefix:parent/child)
                        prefixed_path = f"{file_prefix}:{full_path}"
                        all_keys.add(prefixed_path)

                        # Only add to leaf_keys if it's an actual string/number value, not a parent object
                        if not isinstance(value, dict):
                            leaf_keys.add(prefixed_key)
                            leaf_keys.add(prefixed_path)
                            # Also store the path without prefix for easier lookup
                            leaf_paths.add(full_key)
                            leaf_paths.add(full_path)
                        else:
                            # Mark as a parent key - we don't want to remove these directly
                            parent_keys.add(prefixed_key)
                            parent_keys.add(prefixed_path)

                            # Handle pluralization keys
                            for suffix in ['_one', '_other', '_few', '_many']:
                                if full_key.endswith(suffix):
                                    base_key = full_key[:-len(suffix)]
                                    base_key_prefixed = f"{file_prefix}:{base_key}"
                                    all_keys.add(base_key_prefixed)
                                    leaf_keys.add(base_key_prefixed)
                                    leaf_paths.add(base_key)
                                if full_path.endswith(suffix):
                                    base_path = full_path[:-len(suffix)]
                                    base_path_prefixed = f"{file_prefix}:{base_path}"
                                    all_keys.add(base_path_prefixed)
                                    leaf_keys.add(base_path_prefixed)
                                    leaf_paths.add(base_path)

                        if isinstance(value, dict):
                            collect_keys(value, f"{full_key}.", full_path)

            # Collect keys with file prefix
            collect_keys(json_data)

        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

    return all_keys, leaf_keys, leaf_paths, localization_data, parent_keys


def extract_flat_keys(json_obj, prefix, result=None, parent_path=None):
    """
    Extract a flat dictionary of all keys and their values from a nested JSON object.
    Keys are in the format "parent.child" and values are the leaf values.
    """
    if result is None:
        result = {}

    if parent_path is None:
        parent_path = []

    if not isinstance(json_obj, dict):
        return result

    for key, value in json_obj.items():
        current_path = parent_path + [key]
        path_str = '.'.join(current_path)

        if isinstance(value, dict):
            extract_flat_keys(value, prefix, result, current_path)
        else:
            result[path_str] = value

    return result


def rebuild_json_without_unused(flat_keys, unused_leaf_paths, prefix):
    """
    Rebuild a JSON object from flat keys, excluding unused keys.
    flat_keys: Dictionary of flattened keys -> values
    unused_leaf_paths: Set of unused leaf paths without prefix (e.g., "key.path")
    prefix: The file prefix (e.g., "chat")
    """
    result = {}
    removed_count = 0
    removed_paths = set()

    for path_str, value in flat_keys.items():
        # Also check for slash notation equivalent
        path_str_slash = path_str.replace('.', '/')

        # If this path is in our unused list (in either notation), skip it
        if path_str in unused_leaf_paths or path_str_slash in unused_leaf_paths:
            removed_count += 1
            removed_paths.add(path_str)
            continue

        # Skip pluralization keys if their base form is unused
        is_plural = False
        for suffix in ['_one', '_other', '_few', '_many']:
            if path_str.endswith(suffix):
                base_path = path_str[:-len(suffix)]
                base_path_slash = base_path.replace('.', '/')
                if base_path in unused_leaf_paths or base_path_slash in unused_leaf_paths:
                    is_plural = True
                    removed_count += 1
                    removed_paths.add(path_str)
                    break

        if is_plural:
            continue

        # Build nested structure
        parts = path_str.split('.')
        current = result
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # If not a dict, make it a dict (handling conflicts)
                current[part] = {"_value": current[part], "_conflict": True}
            current = current[part]

        # Set the value
        last_part = parts[-1]
        if last_part in current and isinstance(current[last_part], dict):
            # If there's already a dict with this key, add value as a special field
            current[last_part]["_value"] = value
        else:
            current[last_part] = value

    return result, removed_count, removed_paths


def process_localization_files(language, remove, remove_dry_run, backup, verbose, output_fn):
    """Process all localization files for the specified language."""
    lang_dir = os.path.join(LOCALIZATION_DIR, language)
    if not os.path.exists(lang_dir):
        output_fn(f"Error: Localization directory for {language} not found at {lang_dir}")
        return

    # Find all keys used in the code
    used_keys_in_code = find_used_keys_in_code()
    output_fn(f"Found {len(used_keys_in_code)} unique keys used in the codebase")

    # Load all keys from localization files
    all_loc_keys, leaf_keys, leaf_paths, localization_data, parent_keys = load_localization_keys(language)
    output_fn(f"Found {len(all_loc_keys)} keys in the localization files")
    output_fn(f"Found {len(leaf_keys)} leaf keys (actual strings) in the localization files")
    output_fn(f"Found {len(parent_keys)} parent keys (sections/categories) in the localization files")

    # Find matched keys
    matched_keys = used_keys_in_code.intersection(all_loc_keys)

    # Find unused keys in localization files - only consider leaf keys since parent keys aren't directly used
    unused_keys = leaf_keys - used_keys_in_code

    # Find keys in code not in localization files
    missing_in_loc = used_keys_in_code - all_loc_keys

    # Debug: Print some sample used keys
    if verbose and used_keys_in_code:
        sample_keys = list(used_keys_in_code)[:5]
        output_fn("\nSample used keys in code:")
        for key in sample_keys:
            output_fn(f"  - {key}")

    # If requested, show matched keys
    if args.show_matched and matched_keys:
        output_fn("\n========= MATCHED KEYS (IN BOTH CODE AND LOCALIZATION) =========")
        output_fn(f"Found {len(matched_keys)} keys that are used in code and exist in localization files:")
        for key in sorted(matched_keys):
            output_fn(f"  - {key}")

    # Display missing keys (keys in code not in localization)
    if missing_in_loc:
        output_fn("\n========= KEYS IN CODE NOT IN LOCALIZATION =========")
        output_fn(f"Found {len(missing_in_loc)} keys used in code but not in localization files:")
        for key in sorted(missing_in_loc):
            output_fn(f"  - {key}")

    # Display unused keys (keys in localization not used in code)
    if unused_keys:
        output_fn("\n========= KEYS IN LOCALIZATION NOT USED IN CODE =========")
        output_fn(f"Found {len(unused_keys)} actual leaf keys in localization files not used in code:")

        # Group keys by prefix and category for cleaner output
        if verbose:
            grouped_keys = {}
            for key in sorted(unused_keys):
                prefix, path = key.split(':', 1) if ':' in key else ('misc', key)
                if prefix not in grouped_keys:
                    grouped_keys[prefix] = {}

                if '/' in path:
                    category = path.split('/')[0]
                    if category not in grouped_keys[prefix]:
                        grouped_keys[prefix][category] = []
                    grouped_keys[prefix][category].append(key)
                else:
                    path_parts = path.split('.')
                    category = path_parts[0] if path_parts else 'misc'
                    if category not in grouped_keys[prefix]:
                        grouped_keys[prefix][category] = []
                    grouped_keys[prefix][category].append(key)

            # Print keys by prefix and category
            for prefix, categories in sorted(grouped_keys.items()):
                output_fn(f"\n  Prefix: {prefix}")
                for category, keys in sorted(categories.items()):
                    output_fn(f"\n    Category: {category}")
                    for key in sorted(keys):
                        output_fn(f"      - {key}")
        else:
            # In non-verbose mode, just list the first 20 keys
            sample_keys = sorted(list(unused_keys))[:20]
            for key in sample_keys:
                output_fn(f"  - {key}")
            if len(unused_keys) > 20:
                output_fn(f"  ... and {len(unused_keys) - 20} more (use --verbose to see all)")

    # Process each JSON file for removal if requested
    if remove or remove_dry_run:
        total_expected_removed = 0
        total_removed = 0
        output_fn("\n========= REMOVING UNUSED KEYS =========")
        if remove_dry_run:
            output_fn("DRY RUN MODE: No files will be modified")

        for file_prefix, json_obj in localization_data.items():
            file_name = f"{file_prefix}.json"
            file_path = os.path.join(lang_dir, file_name)

            # Extract all unused keys for this file - only consider leaf keys
            file_unused_keys = {key for key in unused_keys if key.startswith(f"{file_prefix}:")}

            if file_unused_keys:
                # Extract the path parts without prefixes for rebuild_json_without_unused
                file_unused_paths = {key.split(':', 1)[1] for key in file_unused_keys if ':' in key}

                # Count original keys (leaf nodes only)
                flat_keys = extract_flat_keys(json_obj, file_prefix)
                original_key_count = len(flat_keys)

                # Create a new JSON object without the unused keys
                new_json, removed_count, removed_paths = rebuild_json_without_unused(flat_keys, file_unused_paths, file_prefix)

                # Count keys after pruning (alternative way to verify)
                pruned_flat_keys = extract_flat_keys(new_json, file_prefix)
                pruned_key_count = len(pruned_flat_keys)
                expected_removed = original_key_count - pruned_key_count
                total_expected_removed += expected_removed
                total_removed += removed_count

                # Use the accurate count from our tracking
                if removed_count > 0:
                    output_fn(f"{file_name}: Would remove {removed_count} keys (out of {original_key_count})")

                    if remove and not remove_dry_run:
                        # Create backup if requested
                        if backup:
                            backup_path = f"{file_path}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            shutil.copy2(file_path, backup_path)
                            output_fn(f"Created backup at {backup_path}")

                        # Write pruned file with pretty formatting
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(new_json, f, indent=2, ensure_ascii=False)
                        output_fn(f"Updated {file_path}")
                else:
                    output_fn(f"{file_name}: No changes needed")
            else:
                output_fn(f"{file_name}: No changes needed")

        if remove_dry_run:
            output_fn(f"\nTotal keys removed across all files: {total_removed}")
            output_fn(f"\nTotal expected keys to be removed: {total_expected_removed}")
            output_fn("\nThis was a dry run. Run with --remove to apply changes.")
        else:
            output_fn(f"\nTotal keys removed across all files: {total_removed}")
            output_fn(f"Total expected keys to be removed: {total_expected_removed}")
            output_fn("\nDone! Files have been updated.")


def main():
    parser = argparse.ArgumentParser(description='Manage localization keys - find unused keys and remove them.')
    parser.add_argument('--language', type=str, default='en', help='Language code to process (default: "en")')
    parser.add_argument('--output-file', type=str, help='File to write results to (in addition to console)')
    parser.add_argument('--show-matched', action='store_true', help='Show matched keys (those that exist in both code and localization files)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed information about the process')
    parser.add_argument('--backup', action='store_true', help='Create backup of original files before making changes')
    parser.add_argument('--remove', action='store_true', help='Remove unused keys from localization files')
    parser.add_argument('--remove-dry-run', action='store_true', help='Show what would be removed without making changes')

    global args
    args = parser.parse_args()

    # Set up output (both console and file if specified)
    output_file = None
    if args.output_file:
        try:
            output_file = open(args.output_file, 'w', encoding='utf-8')
        except Exception as e:
            print(f"Error opening output file: {e}")

    def output(text):
        """Print to console and write to file if specified."""
        print(text)
        if output_file:
            output_file.write(text + '\n')

    output(f"Scanning for localization keys in '{args.language}' files...")

    # Make sure the paths exist
    if not os.path.exists(SRC_DIR):
        output(f"Error: Source directory not found at {SRC_DIR}")
        return

    # Process the localization files
    process_localization_files(
        args.language,
        args.remove,
        args.remove_dry_run,
        args.backup,
        args.verbose,
        output
    )

    if output_file:
        output_file.close()
        print(f"Results also saved to {args.output_file}")


if __name__ == "__main__":
    main()
