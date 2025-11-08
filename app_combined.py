# app_combined.py
from flask import Flask
from flask_cors import CORS

from flask_api.expense_routes import app as expense_app
from future_prediction.predict_api import app as predict_app

app = Flask(__name__)
CORS(app)

# register the blueprints or route functions
app.register_blueprint(expense_app.blueprints[None])  # expense routes
app.register_blueprint(predict_app.blueprints[None])  # predict routes

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
