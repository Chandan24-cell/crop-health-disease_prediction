import os
from pathlib import Path

# Check common locations where the data might be
locations = [
    Path('data/raw'),
    Path.home() / '.cache' / 'kagglehub' / 'datasets' / 'abdallahalidev' / 'plantvillage-dataset',
    Path('C:/Users/Saurav Shah/Desktop/4th Sem/AIML/AIML Notes/archive/PlantVillage')
]

print("Searching for dataset folders...\n")
for loc in locations:
    if loc.exists():
        print(f"Checking: {loc}")
        # Walk through directories to find where the actual class folders are
        for root, dirs, files in os.walk(loc):
            # Look for directories that contain '___' (the PlantVillage naming convention)
            target_dirs = [d for d in dirs if '___' in d]
            if target_dirs:
                print(f"  ✅ FOUND TARGET FOLDERS IN: {root}")
                print(f"  Sample folders: {target_dirs[:5]}")
                print(f"  TOTAL folders found here: {len(dirs)}")
                break
        print("-" * 50)