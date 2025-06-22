import os
import json
from deep_translator import GoogleTranslator

def translate_value(value, target_lang):
    if isinstance(value, str):
        return GoogleTranslator(source='auto', target=target_lang).translate(value)
    elif isinstance(value, dict):
        return {k: translate_value(v, target_lang) for k, v in value.items()}
    elif isinstance(value, list):
        return [translate_value(v, target_lang) for v in value]
    else:
        return value  # Return unchanged if not a string/dict/list

def translate_json_file(filepath, target_lang='ar'):
    # Load the original JSON
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Translate content recursively
    translated_data = translate_value(data, target_lang)

    # Rename original file
    old_filepath = filepath.replace('.json', '.old.json')
    os.rename(filepath, old_filepath)

    # Save translated file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Translated: {os.path.basename(filepath)}")

def main():
    folder = input("📂 Enter directory path with JSON files: ").strip('"').strip()
    if not os.path.isdir(folder):
        print("❌ Invalid directory.")
        return

    json_files = [f for f in os.listdir(folder) if f.endswith('.json') and not f.endswith('.old.json')]

    if not json_files:
        print("❗ No JSON files to process.")
        return

    for filename in json_files:
        filepath = os.path.join(folder, filename)
        translate_json_file(filepath)

    print("🎉 All files translated to Arabic.")

if __name__ == "__main__":
    main()
