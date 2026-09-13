# Plan: Merge Korean translations onto English JSON structure

## Goal
Compare JSON files in `en/` and `ko/` folders, then overlay Korean values from `ko/` on top of the English values in `en/`, writing the merged result to a new `ko_merged/` folder. Both original folders remain untouched.

## Current State
- `en/` and `ko/` each contain 10 JSON files: `sidebar.json`, `shared.json`, `settings.json`, `onboarding.json`, `models.json`, `download.json`, `discover.json`, `developer.json`, `config.json`, `chat.json`
- `en/` is the complete reference (has all current keys, including nested objects up to 4+ levels deep)
- `ko/` has Korean translations for a subset of `en` keys; it is missing many keys and also contains a few `ko`-only keys (e.g., `presets.commitChanges.*` in `config.json`)

## Resolved Decisions
| Decision | Choice |
|---|---|
| Output destination | New `ko_merged/` folder (originals preserved) |
| Fallback for untranslated keys (in `en`, missing from `ko`) | Keep English value from `en` |
| Keys only in `ko` (not in `en`) | Excluded from output |
| Nested object handling | Recursive deep merge |

## Merge Algorithm (recursive)
For each JSON file pair (`en/<file>` + `ko/<file>`):

```
deep_merge(en_obj, ko_obj):
  result = {}
  for key in en_obj:                # iterate en keys in order (preserves en structure)
    if key in ko_obj:
      if both en_obj[key] and ko_obj[key] are dicts:
        result[key] = deep_merge(en_obj[key], ko_obj[key])   # recurse into nested objects
      else:
        result[key] = ko_obj[key]                             # ko value (Korean) overlays en value
    else:
      result[key] = en_obj[key]  # English fallback for untranslated keys
  return result
```

### Type mismatch handling
If a key holds a `dict` in one source and a non-dict in the other, the `ko` value always wins (it is the overlay). This is the expected behavior since `ko` is the more authoritative translation where it exists.

## Implementation Steps

### Step 1: Create the merge script
Create `merge_localization.py` in the workspace root with:
- A `deep_merge(en, ko)` function implementing the algorithm above
- Logic to discover all `.json` files in `en/` (sorted)
- For each file that also exists in `ko/`: read both, deep-merge, write to `ko_merged/<file>`
- For files only in `en/` (not in `ko/`): copy `en/<file>` to `ko_merged/<file>` as-is
- Files only in `ko/` (not in `en/`): skip
- Use `json.dump(..., indent=2, ensure_ascii=False)` to match existing formatting (2-space indent, Korean characters preserved)
- Create `ko_merged/` directory if it doesn't exist

### Step 2: Run the script
```bash
python3 merge_localization.py
```
(If `python3` is unavailable, use `python`; if Python is not installed, a Node.js equivalent using `JSON.parse`/`JSON.stringify` with a custom replacer can be substituted.)

### Step 3: Validate the output
1. Confirm `ko_merged/` contains all 10 expected JSON files
2. For each file, verify all top-level keys from `en/<file>` are present in the merged output
3. Verify that where `ko/` had a Korean translation for a key, the merged output uses the Korean value (spot-check e.g., `sidebar.json` → `chat: "채팅"`)
4. Verify that keys in `en/` but missing from `ko/` retain the English value (spot-check e.g., `shared.json` → `artifacts.organizationVisible: "Organization Visible"`)
5. Verify no `ko`-only keys appear in the output (e.g., `presets.commitChanges.*` should not be in `ko_merged/config.json`)

## Risks & Notes
- **Key ordering:** Python dicts preserve insertion order; iterating `en` keys first ensures `ko_merged/` matches `en/` key ordering. Within nested dicts, `en` ordering is preserved with `ko` values substituted.
- **Whitespace/blank lines:** The source files contain irregular blank lines (e.g., `config.json` has blank lines between sections). `json.load`/`json.dump` normalizes this (no blank lines in output). This is acceptable for machine-consumed localization files but if exact formatting preservation is required, a custom text-based merger would be needed instead.
- **Large files:** `config.json` is ~636 lines in `en` and ~269 in `ko`. Python's `json` module handles this without issue.
