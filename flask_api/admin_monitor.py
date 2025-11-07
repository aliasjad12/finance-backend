# admin_monitor.py
from flask import Blueprint, jsonify, request, current_app
import os, json, subprocess, sys, datetime
from firebase_admin import firestore
import firebase_admin
from dotenv import load_dotenv
load_dotenv()

bp = Blueprint("admin_monitor", __name__, url_prefix="/admin")

# Safe Firebase init (should already be initialized in expense_routes.py)
if not firebase_admin._apps:
    firebase_key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not firebase_key_path or not os.path.exists(firebase_key_path):
        raise RuntimeError("Firebase key not found for admin_monitor.")
    cred_path = firebase_key_path
    cred = firebase_admin.credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

MODELS_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "models"
))


def user_model_dir(user_id: str):
    return os.path.join(MODELS_ROOT, user_id)

def metadata_path(user_id: str):
    return os.path.join(user_model_dir(user_id), "metadata.json")

def safe_read_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"failed to read json: {e}"}



@bp.route("/model_status", methods=["GET"])
def model_status():
    """Return per-user model status and metadata.json if present.
       Query param: user_id
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    meta = safe_read_json(metadata_path(user_id))
    # inspect model files presence
    mdir = user_model_dir(user_id)
    found = {"has_arima": False, "has_lstm": False, "categories": {}}
    if os.path.isdir(mdir):
        arima_dir = os.path.join(mdir, "category_arima")
        lstm_dir = os.path.join(mdir, "category_lstm")
        if os.path.isdir(arima_dir):
            for fn in os.listdir(arima_dir):
                if fn.endswith("_arima.pkl"):
                    cat = fn.replace("_arima.pkl", "")
                    found["categories"].setdefault(cat, {})["arima_exists"] = True
        if os.path.isdir(lstm_dir):
            for fn in os.listdir(lstm_dir):
                if fn.endswith("_lstm.pt"):
                    cat = fn.replace("_lstm.pt", "")
                    found["categories"].setdefault(cat, {})["lstm_exists"] = True

    # training logs (if any)
    logs = {}
    logs_dir = os.path.join(mdir, "logs")
    if os.path.isdir(logs_dir):
        for ln in sorted(os.listdir(logs_dir), reverse=True)[:5]:
            try:
                with open(os.path.join(logs_dir, ln), "r", encoding="utf-8") as f:
                    logs[ln] = f.read(30_000)  # cap length
            except:
                logs[ln] = "unable to read log file"

    return jsonify({
        "user_id": user_id,
        "metadata": meta,
        "files": found,
        "logs": logs
    }), 200

# ... (imports stay same)

@bp.route("/list_users", methods=["GET"])
def list_users():
    try:
        users = []
        users_ref = db.collection("users")
        docs = users_ref.stream()
        for d in docs:
            data = d.to_dict() or {}
            meta = safe_read_json(metadata_path(d.id))
            users.append({
                "user_id": d.id,
                "displayName": data.get("displayName"),
                "email": data.get("email"),
                "last_trained": meta.get("last_trained")
            })
        return jsonify({"users": users}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/retrain_user", methods=["POST"])
def retrain_user():
    data = request.json
    user_id = data.get("user_id")
    background = data.get("background", True)

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    try:
        script_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "future_prediction", "train_forcaster.py"
        ))
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        python_venv_path = r"C:\Users\Abid computers\Desktop\finance_manager_backend\venv\Scripts\python.exe"

        if background:
            subprocess.Popen(
                [python_venv_path, script_path, user_id],
                cwd=project_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # update metadata immediately
            with open(metadata_path(user_id), "w") as f:
                json.dump({"last_trained": datetime.datetime.utcnow().isoformat()}, f)
            return jsonify({"status": "training started (background)"}), 200
        else:
            result = subprocess.run(
                [python_venv_path, script_path, user_id],
                cwd=project_root,
                capture_output=True,
                text=True
            )
            with open(metadata_path(user_id), "w") as f:
                json.dump({"last_trained": datetime.datetime.utcnow().isoformat()}, f)
            return jsonify({
                "status": "finished",
                "stdout": result.stdout,
                "stderr": result.stderr
            }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@bp.route("/read_log", methods=["GET"])
def read_log():
    """Read a specific log file. Query params: user_id and filename (filename only, not path)"""
    user_id = request.args.get("user_id")
    filename = request.args.get("filename")
    if not user_id or not filename:
        return jsonify({"error": "user_id and filename required"}), 400
    path = os.path.join(user_model_dir(user_id), "logs", filename)
    if not os.path.exists(path):
        return jsonify({"error": "log not found"}), 404
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(200_000)  # cap
        return jsonify({"filename": filename, "content": content}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
