import os
from pathlib import Path


dataset_archive = Path(
    r'C:\Users\Saurav Shah\Desktop\4th Sem\AIML\AIML Notes\archive'
)
folders_to_check = [
    dataset_archive / 'PlantVillage',
    Path('data/raw/PlantVillage'),
    Path('data/raw'),
]

for path in folders_to_check:
    if path.exists():
        print(f"Found folders in {path}:")
        for folder_name in sorted(os.listdir(path)):
            if os.path.isdir(path / folder_name):
                print(f" - {folder_name}")
        break
else:
    print("No dataset folder found in the configured locations.")