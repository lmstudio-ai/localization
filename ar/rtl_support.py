import json
import glob
import os

def add_rtl_marker(data):
    """Recursively prepend \u200F to string values."""
    if isinstance(data, str):
        # Only add the marker if it's not already there.
        return "\u200F" + data if not data.startswith("\u200F") else data
    elif isinstance(data, dict):
        return {key: add_rtl_marker(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [add_rtl_marker(item) for item in data]
    else:
        return data

# Adjust the glob pattern if needed (e.g., to limit to specific files)
for file_path in glob.glob("*.json"):
    with open(file_path, "r", encoding="utf-8") as file:
        try:
            json_data = json.load(file)
        except json.JSONDecodeError as e:
            print(f"Skipping {file_path} due to JSON error: {e}")
            continue

    # Update the JSON data by prepending the RTL marker to every string.
    updated_data = add_rtl_marker(json_data)

    # Write the updated data back to the file
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(updated_data, file, ensure_ascii=False, indent=4)

    print(f"Processed: {os.path.basename(file_path)}")
