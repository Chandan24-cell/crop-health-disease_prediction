import shutil
import random
from pathlib import Path

# Create demo folder
demo_dir = Path('demo_images')
demo_dir.mkdir(exist_ok=True)

# Paths to our test data
test_dir = Path('data/processed/test')

# 1. Pick a Diseased Leaf (Tomato Late Blight)
diseased_imgs = list((test_dir / 'Tomato_Late_blight').glob('*.jpg'))
if diseased_imgs:
    shutil.copy(random.choice(diseased_imgs), demo_dir / '1_diseased_tomato.jpg')
    print("Copied: 1_diseased_tomato.jpg")

# 2. Pick a Healthy Leaf (Maize Healthy)
healthy_imgs = list((test_dir / 'Maize_healthy').glob('*.jpg'))
if healthy_imgs:
    shutil.copy(random.choice(healthy_imgs), demo_dir / '2_healthy_maize.jpg')
    print("Copied: 2_healthy_maize.jpg")

# 3. Pick an Unknown Leaf (e.g., Apple or Grape from PlantVillage)
unknown_imgs = list((test_dir / 'Unknown').glob('*.jpg'))
if unknown_imgs:
    shutil.copy(random.choice(unknown_imgs), demo_dir / '3_unknown_leaf.jpg')
    print("Copied: 3_unknown_leaf.jpg")

# 4. Pick a Not_a_leaf image (CIFAR-10 car/dog/etc.)
not_leaf_imgs = list((test_dir / 'Not_a_leaf').glob('*.jpg'))
if not_leaf_imgs:
    shutil.copy(random.choice(not_leaf_imgs), demo_dir / '4_not_a_leaf.jpg')
    print("Copied: 4_not_a_leaf.jpg")

print("\nDemo images ready! Check the 'demo_images' folder in your project directory.")