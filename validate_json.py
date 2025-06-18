import json, glob, sys

errors = False
for path in glob.glob("fa/*.json"):
    try:
        with open(path, encoding="utf-8") as f:
            json.load(f)
    except Exception as e:
        print(f"Error in {path}: {e}")
        errors = True

if errors:
    print("❌ فایل(های) JSON دارای خطا بودند.")
    sys.exit(1)
else:
    print("✅ همهٔ فایل‌های JSON معتبرند.")
    sys.exit(0)
