from flask import Flask, request, jsonify
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import torch
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
import pickle
from firebase_admin import credentials, initialize_app, firestore
import requests
from dotenv import load_dotenv
from datetime import datetime
import subprocess

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ───── Firebase Initialization ─────
firebase_key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not firebase_key_path or not os.path.exists(firebase_key_path):
    raise RuntimeError("Firebase key not found or invalid path.")

cred = credentials.Certificate(firebase_key_path)
initialize_app(cred)
db = firestore.client()

from budget_insights import bp as budget_bp
app.register_blueprint(budget_bp)
from admin_monitor import bp as admin_bp
app.register_blueprint(admin_bp)

# ───── Category Classifier (DistilBERT) ─────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORY_MAP_PATH = os.path.join(BASE_DIR, "..", "saved_models", "category_map.pkl")
MODEL_PATH = os.path.join(BASE_DIR, "..", "saved_models", "distilbert_model.pth")

with open(CATEGORY_MAP_PATH, "rb") as f:
    category_map = pickle.load(f)
reverse_category_map = {v: k for k, v in category_map.items()}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model = DistilBertForSequenceClassification.from_pretrained(
    "distilbert-base-uncased",
    num_labels=len(category_map)
)
model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
model.to(device)
model.eval()

tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")

@app.route("/categorize_expense", methods=["POST"])
def categorize_expense():
    data = request.json
    expense_text = data.get("expense")
    if not expense_text:
        return jsonify({"error": "Expense text is required"}), 400

    expense_text = expense_text.lower()
    encoding = tokenizer(
        expense_text,
        padding="max_length",
        truncation=True,
        max_length=64,  # match training
        return_tensors="pt"
    )
    encoding = {k: v.to(device) for k, v in encoding.items()}

    with torch.no_grad():
        outputs = model(**encoding)
        probs = torch.nn.functional.softmax(outputs.logits, dim=1)
        predicted_label = torch.argmax(probs).item()
        confidence = probs[0, predicted_label].item()

    category = reverse_category_map.get(predicted_label, "unknown") if confidence >= 0.4 else "unknown"

    return jsonify({
        "expense": expense_text,
        "category": category,
        "confidence": round(confidence, 2)
    })

@app.route("/predict_future_expense", methods=["GET"])
def predict_future_expense():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        response = requests.get(
            "http://127.0.0.1:7860/predict",   # <-- use LAN IP, not localhost
            params={"user_id": user_id},
            timeout=60                           # <-- give more time
        )
        result = response.json()

        if "categoryExpenses" not in result or not result["categoryExpenses"]:
            if result.get("status") == "not_enough_data":
                return jsonify({"status": "not_enough_data"}), 422
            if result.get("status") == "model_pending":
                return jsonify({"status": "model_pending"}), 202
            return jsonify({"status": "unknown_error"}), 500

        return jsonify(result), 200

    except Exception as e:
        print(f"[ERROR] Proxy to /predict failed: {e}")  # <-- log real error
        return jsonify({"error": str(e)}), 500

@app.route("/train_user_models", methods=["POST"])
def train_user_models():
    data = request.json
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        script_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "future_prediction", "train_forcaster.py"
        ))
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # 🔹 Always use venv python
        python_venv_path = r"C:\Users\Abid computers\Desktop\finance_manager_backend\venv\Scripts\python.exe"

        # 1. Run script once synchronously to check retraining status
        check_cmd = [python_venv_path, script_path, user_id]
        result = subprocess.run(check_cmd, cwd=project_root, capture_output=True, text=True)

        if "already up to date" in result.stdout:
            return jsonify({"status": "up_to_date"}), 200

        # 2. Otherwise, spawn training async in background
        subprocess.Popen(
            [python_venv_path, script_path, user_id],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return jsonify({"status": "training started"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/track_goal_progress", methods=["GET"])
def track_goal_progress():
    user_id = request.args.get("user_id")
    goal_id = request.args.get("goal_id")

    if not user_id or not goal_id:
        return jsonify({"error": "User ID and Goal ID are required"}), 400

    goal_ref = db.collection('users').document(user_id).collection('savings_goals').document(goal_id)
    goal = goal_ref.get()

    if not goal.exists:
        return jsonify({"error": "Goal not found"}), 404

    goal_data = goal.to_dict()
    target_amount = goal_data.get("target_amount", 0)
    amount_saved = goal_data.get("amount_saved", 0)
    progress_percentage = (amount_saved / target_amount) * 100 if target_amount else 0

    if progress_percentage >= 100:
        suggestion = "🎉 Congratulations, you've reached your goal!"
    elif progress_percentage >= 75:
        suggestion = "✅ You're almost there! Keep it up!"
    elif progress_percentage >= 50:
        suggestion = "🟡 You're halfway to your goal. Stay on track!"
    else:
        suggestion = "🔵 You can do it! Stay focused and save regularly."

    return jsonify({
        "goal_name": goal_data.get("goal_name"),
        "target_amount": target_amount,
        "amount_saved": amount_saved,
        "progress_percentage": round(progress_percentage, 2),
        "suggestion": suggestion
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
