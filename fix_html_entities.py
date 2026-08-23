
import html
import os

# Directories to scan
directories = [
    "g:/AI/VerdeBeautyClinic__Accounts",
    "g:/AI/VerdeBeautyClinic__Accounts/models",
    "g:/AI/VerdeBeautyClinic__Accounts/controllers"
]

# File extensions to process
extensions = (".py",)

for directory in directories:
    if not os.path.exists(directory):
        continue
    for filename in os.listdir(directory):
        if filename.endswith(extensions):
            file_path = os.path.join(directory, filename)
            print(f"Processing {file_path}...")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Unescape HTML entities
                fixed_content = html.unescape(content)
                
                # Only write if there was a change
                if fixed_content != content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(fixed_content)
                    print(f"Fixed {file_path}")
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

print("Done!")
