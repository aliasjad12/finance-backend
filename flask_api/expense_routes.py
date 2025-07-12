from flask import Flask, request, jsonify
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import torch
from transformers import BertTokenizer, BertForSequenceClassification
import pickle
from firebase_admin import credentials, initialize_app, firestore
import requests
from dotenv import load_dotenv
load_dotenv()
import os


app = Flask(__name__)

# Initialize Firebase
firebase_key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not firebase_key_path or not os.path.exists(firebase_key_path):
    raise RuntimeError("❌ Firebase key not found or invalid path.")

cred = credentials.Certificate(firebase_key_path)

initialize_app(cred)
db = firestore.client()
from budget_insights import bp as budget_bp
app.register_blueprint(budget_bp)
# Load Model and Tokenizer
model_path = "../saved_models/bert_model.pth"
category_map_path = "../saved_models/category_map.pkl"

# Load category map
with open(category_map_path, "rb") as f:
    category_map = pickle.load(f)
reverse_category_map = {v: k for k, v in category_map.items()}

# Load model with correct label size
model = BertForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=len(category_map))
model.load_state_dict(torch.load(model_path, map_location=torch.device("cpu")))
model.eval()
tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")

@app.route("/categorize_expense", methods=["POST"])
def categorize_expense():
    data = request.json
    expense_text = data.get("expense")
    if not expense_text:
        return jsonify({"error": "Expense text is required"}), 400

    encoding = tokenizer(expense_text, padding="max_length", truncation=True, max_length=32, return_tensors="pt")
    with torch.no_grad():
        outputs = model(input_ids=encoding["input_ids"], attention_mask=encoding["attention_mask"])
        probs = torch.nn.functional.softmax(outputs.logits, dim=1)
        predicted_label = torch.argmax(probs).item()
        confidence = probs[0, predicted_label].item()

    # 🚨 Confidence-based invalidation
    if confidence < 0.4:
        category = "unknown"
    else:
        category = reverse_category_map.get(predicted_label, "unknown")

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
            "http://localhost:5001/predict", params={"user_id": user_id}, timeout=5
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/train_user_models", methods=["POST"])
def train_user_models():
    data = request.json
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        from future_prediction.train_forcaster import train_all_categories
        categories = ["Food", "Utilities", "Travel", "Shopping", "Health"]
        train_all_categories(user_id, categories)
        return jsonify({"status": "training started"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/track_goal_progress", methods=["GET"])
def track_goal_progress():
    user_id = request.args.get("user_id")
    goal_id = request.args.get("goal_id")

    if not user_id or not goal_id:
        return jsonify({"error": "User ID and Goal ID are required"}), 400

    # ✅ NEW LOCATION: Global savings_goals collection
    goal_ref = db.collection('users').document(user_id).collection('savings_goals').document(goal_id)
    goal = goal_ref.get()

    if not goal.exists:
        return jsonify({"error": "Goal not found"}), 404

    goal_data = goal.to_dict()

    target_amount = goal_data.get("target_amount", 0)
    amount_saved = goal_data.get("amount_saved", 0)
    progress_percentage = (amount_saved / target_amount) * 100 if target_amount != 0 else 0

    # Generate suggestion based on progress
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
    app.run(host="0.0.0.0", port=5000)
