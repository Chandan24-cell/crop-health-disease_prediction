import os
from pathlib import Path


base_out = Path('data/processed')
print(f"{'Class':<25} | {'Train':<6} | {'Val':<6} | {'Test':<6} | {'Total':<6}")
print("-" * 60)

classes = sorted(os.listdir(base_out / 'train'))
for cls in classes:
    counts = {}
    total = 0
    for split in ['train', 'val', 'test']:
        path = base_out / split / cls
        count = len([
            file_name for file_name in os.listdir(path)
            if file_name.lower().endswith(('.jpg', '.jpeg', '.png'))
        ])
        counts[split] = count
        total += count
    print(
        f"{cls:<25} | {counts['train']:<6} | {counts['val']:<6} | "
        f"{counts['test']:<6} | {total:<6}"
    )