import os
import shutil
import random
import cv2
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from tensorflow.keras.datasets import cifar10
import kagglehub

# --- CONFIGURATION ---
OUT_DIR = Path('data/processed')
RANDOM_SEED = 42

# Correct folder names from the complete abdallahalidev/plantvillage-dataset
TARGET_MAPPING = {
    'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot': 'Maize_Gray_leaf_spot',
    'Corn_(maize)___Northern_Leaf_Blight': 'Maize_Northern_Leaf_Blight',
    'Corn_(maize)___Common_rust_': 'Maize_Common_rust',
    'Corn_(maize)___healthy': 'Maize_healthy',
    'Potato___Early_blight': 'Potato_Early_blight',
    'Potato___Late_blight': 'Potato_Late_blight',
    'Potato___healthy': 'Potato_healthy',
    'Tomato___Early_blight': 'Tomato_Early_blight',
    'Tomato___Late_blight': 'Tomato_Late_blight',
    'Tomato___Leaf_Mold': 'Tomato_Leaf_Mold',
    'Tomato___healthy': 'Tomato_healthy'
}


def split_and_copy(src_dir, dest_base, class_name):
    files = [f for f in os.listdir(src_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if not files:
        print(f"  Warning: No images found in {src_dir}")
        return

    train_files, temp_files = train_test_split(files, test_size=0.30, random_state=RANDOM_SEED)
    val_files, test_files = train_test_split(temp_files, test_size=0.50, random_state=RANDOM_SEED)

    for split_name, split_files in zip(['train', 'val', 'test'], [train_files, val_files, test_files]):
        dest_dir = Path(dest_base) / split_name / class_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in split_files:
            shutil.copy(Path(src_dir) / f, dest_dir / f)


if __name__ == "__main__":
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    # 1. Download and locate the COMPLETE dataset
    print("Locating complete PlantVillage dataset...")
    raw_path = Path(kagglehub.dataset_download("abdallahalidev/plantvillage-dataset"))

    # Dynamically find the 'color' folder inside the downloaded path
    RAW_EXTRACT_DIR = None
    for root, dirs, files in os.walk(raw_path):
        if 'color' in dirs:
            RAW_EXTRACT_DIR = Path(root) / 'color'
            break

    # Fallback to the exact path we know works on your machine
    if RAW_EXTRACT_DIR is None or not RAW_EXTRACT_DIR.exists():
        RAW_EXTRACT_DIR = (
            Path.home() / '.cache' / 'kagglehub' / 'datasets' /
            'abdallahalidev' / 'plantvillage-dataset' / 'versions' / '3' /
            'plantvillage dataset' / 'color'
        )

    actual_classes = sorted([d for d in os.listdir(RAW_EXTRACT_DIR) if os.path.isdir(RAW_EXTRACT_DIR / d)])
    print(f"Found {len(actual_classes)} raw classes in: {RAW_EXTRACT_DIR}")

    # 2. Setup output directories
    all_classes = list(TARGET_MAPPING.values()) + ['Unknown', 'Not_a_leaf']
    for split in ['train', 'val', 'test']:
        for class_name in all_classes:
            (OUT_DIR / split / class_name).mkdir(parents=True, exist_ok=True)

    # 3. Process Target Classes
    print("\nProcessing target classes...")
    for pv_name, clean_name in TARGET_MAPPING.items():
        src = RAW_EXTRACT_DIR / pv_name
        if src.exists():
            print(f"  Processing {clean_name}...")
            split_and_copy(src, OUT_DIR, clean_name)
        else:
            print(f"  ERROR: Missing expected class folder: {pv_name}")

    # 4. Process "Unknown" class (unsupported crops)
    print("\nProcessing 'Unknown' class...")
    unknown_files = []
    supported_crops = {'Corn_(maize)', 'Potato', 'Tomato'}
    for folder in actual_classes:
        crop_name = folder.split('___')[0]
        if crop_name not in supported_crops:
            folder_path = RAW_EXTRACT_DIR / folder
            files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            unknown_files.extend([(folder_path, f) for f in files])

    random.shuffle(unknown_files)
    unknown_files = unknown_files[:1200] # Limit to balance dataset

    unk_train, unk_temp = train_test_split(unknown_files, test_size=0.30, random_state=RANDOM_SEED)
    unk_val, unk_test = train_test_split(unk_temp, test_size=0.50, random_state=RANDOM_SEED)

    for split_name, split_data in zip(['train', 'val', 'test'], [unk_train, unk_val, unk_test]):
        dest_dir = OUT_DIR / split_name / 'Unknown'
        for src_dir, fname in split_data:
            shutil.copy(src_dir / fname, dest_dir / fname)

    # 5. Process "Not_a_leaf" class (using CIFAR-10)
    print("\nGenerating 'Not_a_leaf' class...")
    (x_train, _), (x_test, _) = cifar10.load_data()
    all_cifar = np.concatenate([x_train, x_test], axis=0)
    indices = np.random.choice(all_cifar.shape[0], 1200, replace=False)
    not_leaf_images = all_cifar[indices]

    nl_train, nl_temp = train_test_split(not_leaf_images, test_size=0.30, random_state=RANDOM_SEED)
    nl_val, nl_test = train_test_split(nl_temp, test_size=0.50, random_state=RANDOM_SEED)

    for split_name, split_data in zip(['train', 'val', 'test'], [nl_train, nl_val, nl_test]):
        dest_dir = OUT_DIR / split_name / 'Not_a_leaf'
        for i, img in enumerate(split_data):
            img_resized = cv2.resize(img, (224, 224))
            cv2.imwrite(str(dest_dir / f'not_leaf_{i}.jpg'), img_resized)

    print("\nPhase 1 Data Setup Complete!")