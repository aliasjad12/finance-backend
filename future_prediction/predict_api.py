from flask import Flask, request, jsonify
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from future_prediction.predictor import predict_all_categories

app = Flask(__name__)

@app.route("/predict", methods=["GET"])
def predict():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    categories = ["Food", "Utilities", "Travel", "Shopping", "Health"]
    result = predict_all_categories(user_id, categories)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
