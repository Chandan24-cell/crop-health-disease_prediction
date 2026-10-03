import cv2
import numpy as np
import os
from pathlib import Path


def estimate_severity(image_path):
    """
    Segments leaf from background, then segments lesions inside the leaf.
    Returns severity percentage, category, and an overlay image.
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return 0.0, "Unknown", None

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 1. Segment the LEAF from the background
    # Green leaf range + brown/yellowish leaf range
    lower_green = np.array([25, 20, 20])
    upper_green = np.array([95, 255, 255])

    lower_brown = np.array([10, 20, 20])
    upper_brown = np.array([30, 255, 200])

    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    mask_brown = cv2.inRange(hsv, lower_brown, upper_brown)
    leaf_mask = cv2.bitwise_or(mask_green, mask_brown)

    # Clean up the leaf mask
    kernel = np.ones((5, 5), np.uint8)
    leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_CLOSE, kernel)
    leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_OPEN, kernel)

    # 2. Segment LESIONS (brown, yellow, dark spots) inside the leaf
    lower_lesion = np.array([10, 50, 20])
    upper_lesion = np.array([30, 255, 200])

    lesion_mask = cv2.inRange(hsv, lower_lesion, upper_lesion)

    # Apply the leaf mask so we only count lesions ON the leaf
    lesion_mask = cv2.bitwise_and(lesion_mask, leaf_mask)

    # Clean up lesions mask
    lesion_mask = cv2.morphologyEx(lesion_mask, cv2.MORPH_OPEN, kernel)

    # 3. Calculate Severity
    leaf_pixels = cv2.countNonZero(leaf_mask)
    lesion_pixels = cv2.countNonZero(lesion_mask)

    if leaf_pixels == 0:
        return 0.0, "Unknown", None

    severity_pct = (lesion_pixels / leaf_pixels) * 100.0

    # Categorize based on rules: Mild <10%, Moderate 10-30%, Severe >30%
    if severity_pct < 10:
        category = "Mild"
    elif severity_pct <= 30:
        category = "Moderate"
    else:
        category = "Severe"

    # 4. Create Overlay
    overlay = img_rgb.copy()

    # Draw leaf outline in Green
    leaf_contours, _ = cv2.findContours(leaf_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, leaf_contours, -1, (0, 255, 0), 2)

    # Draw lesions in Red
    lesion_contours, _ = cv2.findContours(lesion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, lesion_contours, -1, (255, 0, 0), -1)

    # Blend with original
    alpha = 0.5
    overlay = cv2.addWeighted(img_rgb, 1 - alpha, overlay, alpha, 0)

    return severity_pct, category, overlay


if __name__ == "__main__":
    # --- Test on 5 sample images ---
    print("Testing Severity Estimator on 5 random diseased images...")

    # Pick a random diseased class
    test_dir = Path('data/processed/test/Tomato_Late_blight')
    if not test_dir.exists():
        test_dir = Path('data/processed/test/Maize_Common_rust')

    images = list(test_dir.glob('*.JPG')) + list(test_dir.glob('*.jpg')) + list(test_dir.glob('*.png'))
    samples = np.random.choice(images, min(5, len(images)), replace=False)

    os.makedirs('test_severity_output', exist_ok=True)

    for i, img_path in enumerate(samples):
        pct, cat, overlay_img = estimate_severity(img_path)
        print(f"Image {i + 1}: {img_path.name} | Severity: {pct:.2f}% | Category: {cat}")

        if overlay_img is not None:
            # Save the overlay to check visually
            out_path = f'test_severity_output/{img_path.stem}_severity.jpg'
            cv2.imwrite(out_path, cv2.cvtColor(overlay_img, cv2.COLOR_RGB2BGR))

    print("\nSeverity test complete. Check the 'test_severity_output' folder for visual overlays.")