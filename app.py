import streamlit as st
import cv2
import numpy as np
import json
import tensorflow as tf
from PIL import Image
from pathlib import Path
import sys

# Add scripts to path
sys.path.append(str(Path('scripts')))
from severity_estimator import estimate_severity
from build_knowledge_base import get_recommendation


@st.cache_resource
def load_model_and_data():
    model = tf.keras.models.load_model('models/crop_disease_model.keras')
    with open('models/class_names.json', 'r') as class_file:
        class_names = json.load(class_file)
    return model, class_names


def check_image_quality(image_array):
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = np.mean(gray)
    return blur_score < 100.0, brightness < 50.0


def predict_with_safety(image_array, model, class_names, threshold=0.80, demo_mode=False):
    img_resized = cv2.resize(image_array, (224, 224))
    img_batch = np.expand_dims(img_resized, axis=0).astype(np.float32)
    predictions = model.predict(img_batch, verbose=0)[0]

    top_indices = np.argsort(predictions)[-2:][::-1]
    top_index, second_index = top_indices
    top_confidence = float(predictions[top_index])
    second_confidence = float(predictions[second_index])
    top_class = class_names[top_index]
    second_class = class_names[second_index]

    if not demo_mode:
        if top_confidence < threshold:
            return {
                "diagnosis": "Uncertain",
                "confidence": top_confidence,
                "severity_ready": False,
                "message": "Not sure. Please retake the photo or consult an extension officer."
            }

        if top_class in ["Unknown", "Not_a_leaf"]:
            return {
                "diagnosis": "Not a supported leaf",
                "confidence": top_confidence,
                "severity_ready": False,
                "message": "This does not look like a supported Maize, Tomato, or Potato leaf."
            }

    if top_class in ["Maize_healthy", "Potato_healthy", "Tomato_healthy"]:
        return {
            "diagnosis": top_class,
            "confidence": top_confidence,
            "severity_ready": False,
            "message": "This leaf looks healthy. Keep up the good farming practices."
        }

    disease_classes = [
        name for name in class_names
        if name not in ["Unknown", "Not_a_leaf", "Maize_healthy", "Potato_healthy", "Tomato_healthy"]
    ]
    if not demo_mode and (top_confidence - second_confidence) < 0.10 and second_class in disease_classes:
        return {
            "diagnosis": f"Ambiguous ({top_class} or {second_class})",
            "confidence": top_confidence,
            "severity_ready": False,
            "message": "Confidence is split between two diseases. Please consult an extension officer."
        }

    return {
        "diagnosis": top_class,
        "confidence": top_confidence,
        "severity_ready": True,
        "message": f"Detected {top_class.replace('_', ' ')} with {top_confidence:.1%} confidence."
    }


st.set_page_config(page_title="Crop Health AI", layout="wide")

with st.sidebar:
    st.title("Crop Health AI")
    demo_mode = st.checkbox("Developer Demo Mode (Bypass Safety)", value=False)
    if demo_mode:
        st.warning("Safety checks are off. Predictions will be shown for unsupported or low-confidence images.")

    st.markdown("---")
    st.subheader("Scan History")
    if "history" not in st.session_state:
        st.session_state.history = []

    for index, record in enumerate(reversed(st.session_state.history[-5:]), start=1):
        st.write(f"**{index}. {record['diagnosis']}**")
        st.caption(f"{record['severity']} | {record['confidence']:.1%}")
    if not st.session_state.history:
        st.info("No scans yet.")

st.title("AI-Powered Crop Health & Disease Management")
st.markdown("Upload or take a photo of a crop leaf for disease diagnosis, severity estimation, and management advice.")

uploaded_file = st.camera_input("Take a picture")
if uploaded_file is None:
    uploaded_file = st.file_uploader("Or upload an image", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    image_array = np.asarray(image)

    is_blurry, is_dark = check_image_quality(image_array)
    if is_blurry or is_dark:
        st.error("Poor image quality. Please take a clearer, brighter photo.")
        if is_blurry:
            st.warning("The image is too blurry. Hold the camera steady and try again.")
        if is_dark:
            st.warning("The image is too dark. Try again in better lighting.")
        st.stop()

    st.success("Image quality is good.")

    with st.spinner("Loading AI model..."):
        model, class_names = load_model_and_data()

    with st.spinner("Analyzing leaf..."):
        result = predict_with_safety(
            image_array,
            model,
            class_names,
            threshold=0.80,
            demo_mode=demo_mode
        )

    st.markdown("---")
    diagnosis_column, image_column = st.columns([1, 1])
    with diagnosis_column:
        st.subheader("Diagnosis")
        st.write(result["message"])
        st.metric("Confidence", f"{result['confidence']:.1%}")
    with image_column:
        st.image(image, caption="Uploaded image", use_container_width=True)

    if result["severity_ready"]:
        st.markdown("---")
        st.subheader("Severity Estimation")

        temp_path = Path("temp_uploaded_image.jpg")
        cv2.imwrite(str(temp_path), cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR))
        severity_pct, severity_category, overlay_image = estimate_severity(temp_path)

        st.metric("Severity", f"{severity_pct:.1f}%")
        st.info(f"Category: **{severity_category}**")
        if overlay_image is not None:
            st.image(overlay_image, caption="Lesion overlay", use_container_width=True)

        st.markdown("---")
        st.subheader("Management Advice")
        recommendation = get_recommendation(result["diagnosis"], severity_category)

        if "error" in recommendation:
            st.warning(recommendation["error"])
        else:
            st.markdown(f"**Crop:** {recommendation['crop']}")
            st.markdown(f"**Cause:** {recommendation['cause']}")
            st.markdown(f"**Symptoms:** {recommendation['symptoms']}")
            st.markdown(f"**Immediate Actions:** {recommendation['immediate_actions']}")
            st.markdown(f"**Cultural Controls:** {recommendation['cultural_controls']}")
            st.markdown(f"**Prevention:** {recommendation['prevention']}")
            st.markdown(f"**Advice for {severity_category}:** {recommendation['specific_advice']}")
            st.markdown(f"**When to seek an expert:** {recommendation['when_to_seek_expert']}")
            st.warning(f"**Safety Note:** {recommendation['safety_note']}")

        st.session_state.history.append({
            "diagnosis": result["diagnosis"],
            "severity": severity_category,
            "confidence": result["confidence"]
        })