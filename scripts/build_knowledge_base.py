import json
from pathlib import Path

# Ensure models directory exists
MODEL_DIR = Path('models')
MODEL_DIR.mkdir(exist_ok=True)

MODEL_DIR = Path('models')
MODEL_DIR.mkdir(exist_ok=True)

# English-only Knowledge Base
KB_DATA = {
    "Maize_Common_rust": {
        "crop": "Maize", "cause": "Fungus (Puccinia sorghi)",
        "symptoms": "Small, circular to elongated reddish-brown pustules on both leaf surfaces.",
        "immediate_actions": "Remove and destroy heavily infected lower leaves.",
        "cultural_controls": "Plant resistant varieties. Practice crop rotation with non-host crops.",
        "prevention": "Ensure balanced soil fertility. Avoid late planting.",
        "when_to_seek_expert": "If pustules spread rapidly to the upper canopy.",
        "safety_note": "ALWAYS wear protective gear when spraying. Keep away from water sources.",
        "severity_advice": {
            "mild": "Monitor closely. No chemical treatment needed yet.",
            "moderate": "Verify pesticide use against the current CIB&RC label; consult your State Agriculture Department or local KVK.",
            "severe": "Do not recommend a pesticide here; verify the current CIB&RC label and consult a local KVK."
        }
    },
    "Maize_Gray_leaf_spot": {
        "crop": "Maize", "cause": "Fungus (Cercospora zeae-maydis)",
        "symptoms": "Rectangular, gray to tan lesions bounded by leaf veins.",
        "immediate_actions": "Clear crop debris after harvest to reduce spore carryover.",
        "cultural_controls": "Use certified disease-free seeds. Plow down infected stubble.",
        "prevention": "Ensure adequate plant spacing for air circulation.",
        "when_to_seek_expert": "If lesions reach the ear leaf before grain fill.",
        "safety_note": "ALWAYS wear protective gear when spraying. Keep away from water sources.",
        "severity_advice": {
            "mild": "Monitor weather. Fungicide only if wet weather persists.",
            "moderate": "Verify pesticide use against the current CIB&RC label; consult your State Agriculture Department or local KVK.",
            "severe": "Do not recommend a pesticide here; verify the current CIB&RC label and consult a local KVK."
        }
    },
    "Maize_Northern_Leaf_Blight": {
        "crop": "Maize", "cause": "Fungus (Exserohilum turcicum)",
        "symptoms": "Long, elliptical or cigar-shaped gray-green lesions.",
        "immediate_actions": "Scout fields weekly during warm, humid weather.",
        "cultural_controls": "Rotate with beans or cowpeas. Use resistant hybrids.",
        "prevention": "Avoid overhead irrigation if possible.",
        "when_to_seek_expert": "If lesions appear on the top 3 leaves during silking.",
        "safety_note": "ALWAYS wear protective gear when spraying. Keep away from water sources.",
        "severity_advice": {
            "mild": "Monitor closely. No chemical treatment needed yet.",
            "moderate": "Verify pesticide use against the current CIB&RC label; consult your State Agriculture Department or local KVK.",
            "severe": "Do not recommend a pesticide here; verify the current CIB&RC label and consult a local KVK."
        }
    },
    "Potato_Early_blight": {
        "crop": "Potato", "cause": "Fungus (Alternaria solani)",
        "symptoms": "Dark brown spots with concentric rings (target board appearance).",
        "immediate_actions": "Remove and destroy infected leaves immediately.",
        "cultural_controls": "Ensure adequate potassium fertilization. Rotate crops for 2-3 years.",
        "prevention": "Use certified seed potatoes. Hill up soil around plants.",
        "when_to_seek_expert": "If stem lesions or tuber rot is observed.",
        "safety_note": "ALWAYS wear protective gear when spraying. Keep away from water sources.",
        "severity_advice": {
            "mild": "Monitor closely. Improve air circulation.",
            "moderate": "Verify pesticide use against the current CIB&RC label; consult your State Agriculture Department or local KVK.",
            "severe": "Do not recommend a pesticide here; verify the current CIB&RC label and consult a local KVK."
        }
    },
    "Potato_Late_blight": {
        "crop": "Potato", "cause": "Oomycete (Phytophthora infestans)",
        "symptoms": "Water-soaked pale green spots that turn purplish-black. White mold under leaves.",
        "immediate_actions": "Destroy all cull piles and volunteer potato plants.",
        "cultural_controls": "Plant resistant varieties. Ensure good drainage.",
        "prevention": "Do not irrigate in the evening. Harvest when tubers are mature.",
        "when_to_seek_expert": "Immediately upon seeing the first water-soaked lesion.",
        "safety_note": "ALWAYS wear protective gear when spraying. Keep away from water sources.",
        "severity_advice": {
            "mild": "Apply protectant fungicide before rain.",
            "moderate": "Verify pesticide use against the current CIB&RC label; consult your State Agriculture Department or local KVK.",
            "severe": "Seek prompt State Agriculture Department or KVK advice; verify pesticide use against current CIB&RC labels."
        }
    },
    "Tomato_Early_blight": {
        "crop": "Tomato", "cause": "Fungus (Alternaria linariae)",
        "symptoms": "Small dark spots with concentric rings on older, lower leaves.",
        "immediate_actions": "Prune and remove infected lower leaves.",
        "cultural_controls": "Stake plants for airflow. Mulch to prevent soil splashing.",
        "prevention": "Rotate with non-solanaceous crops for 3 years.",
        "when_to_seek_expert": "If spots move up the stem or reach the fruit.",
        "safety_note": "ALWAYS wear protective gear when spraying. Keep away from water sources.",
        "severity_advice": {
            "mild": "Prune affected leaves. Improve airflow.",
            "moderate": "Verify pesticide use against the current CIB&RC label; consult your State Agriculture Department or local KVK.",
            "severe": "Do not recommend a pesticide here; verify the current CIB&RC label and consult a local KVK."
        }
    },
    "Tomato_Late_blight": {
        "crop": "Tomato", "cause": "Oomycete (Phytophthora infestans)",
        "symptoms": "Large, irregular, greasy gray-green spots. Rapid plant death.",
        "immediate_actions": "Destroy infected plants immediately. Do not compost.",
        "cultural_controls": "Avoid overhead watering. Space plants widely.",
        "prevention": "Plant in raised beds. Use certified disease-free transplants.",
        "when_to_seek_expert": "Immediately. This disease destroys crops in days.",
        "safety_note": "ALWAYS wear protective gear when spraying. Keep away from water sources.",
        "severity_advice": {
            "mild": "Apply protectant fungicide immediately.",
            "moderate": "Verify pesticide use against the current CIB&RC label; consult your State Agriculture Department or local KVK.",
            "severe": "Seek prompt State Agriculture Department or KVK advice; verify pesticide use against current CIB&RC labels."
        }
    },
    "Tomato_Leaf_Mold": {
        "crop": "Tomato", "cause": "Fungus (Passalora fulva)",
        "symptoms": "Yellow spots on upper leaf surface. Olive-green fuzzy mold underneath.",
        "immediate_actions": "Improve greenhouse ventilation immediately.",
        "cultural_controls": "Use drip irrigation. Avoid working among wet plants.",
        "prevention": "Use resistant tomato varieties. Sanitize tools.",
        "when_to_seek_expert": "If mold covers more than 20% of the leaf area.",
        "safety_note": "ALWAYS wear protective gear when spraying. Keep away from water sources.",
        "severity_advice": {
            "mild": "Reduce humidity. Remove lower infected leaves.",
            "moderate": "Verify pesticide use against the current CIB&RC label; consult your State Agriculture Department or local KVK.",
            "severe": "Do not recommend a pesticide here; verify the current CIB&RC label and consult a local KVK."
        }
    }
}

# Save JSON
json_path = MODEL_DIR / 'knowledge_base.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(KB_DATA, f, indent=2, ensure_ascii=False)
print(f"Knowledge base saved to {json_path}")


def get_recommendation(disease, severity):
    if disease not in KB_DATA:
        return {"error": "Disease not found in knowledge base."}

    data = KB_DATA[disease]
    sev_key = severity.lower()
    if sev_key not in ['mild', 'moderate', 'severe']:
        sev_key = 'mild'

    return {
        "crop": data['crop'],
        "cause": data['cause'],
        "symptoms": data['symptoms'],
        "immediate_actions": data['immediate_actions'],
        "cultural_controls": data['cultural_controls'],
        "prevention": data['prevention'],
        "when_to_seek_expert": data['when_to_seek_expert'],
        "specific_advice": data['severity_advice'][sev_key],
        "safety_note": data['safety_note']
    }


if __name__ == "__main__":
    rec = get_recommendation("Tomato_Late_blight", "severe")
    print("\n--- TEST RECOMMENDATION ---")
    for k, v in rec.items():
        print(f"{k}: {v}")