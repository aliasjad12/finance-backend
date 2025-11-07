from flask import Flask, request, jsonify
import sys, os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from future_prediction.predictor import predict_all_categories
from future_prediction.utils import fetch_category_monthly_series

app = Flask(__name__)

@app.route("/predict", methods=["GET"])
def predict():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    categories = ["Food", "Utilities", "Travel", "Shopping", "Health"]

    # 🔹 Count months of available data
    total_months = 0
    for cat in categories:
        ts = fetch_category_monthly_series(user_id, cat)
        total_months = max(total_months, len(ts))

    # 🔹 Case 1: Enough data (>=12) → prefer trained models, fallback if missing
    if total_months >= 12:
        models_ready = False
        for cat in categories:
            lstm_path = f"./models/{user_id}/category_lstm/{cat}_lstm.pt"
            if os.path.exists(lstm_path):
                models_ready = True
                break
        if not models_ready:
            # ✅ Instead of returning "model_pending", give fallback
            result = predict_all_categories(user_id, categories)
            if result.get("categoryExpenses"):
                return jsonify(result), 200
            return jsonify({"status": "model_pending"}), 202

    # 🔹 Case 2: Less than 12 months → fallback predictions
    result = predict_all_categories(user_id, categories)

    if not result.get("categoryExpenses"):
        return jsonify({"status": "not_enough_data"}), 422

    return jsonify(result), 200


if __name__ == "__main__":
     port = int(os.environ.get("PORT", 5001))
     app.run(host="0.0.0.0", port=port, debug=False)
