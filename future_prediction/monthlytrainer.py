import os, subprocess, datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase init
if not firebase_admin._apps:
    cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    firebase_admin.initialize_app(cred)
db = firestore.client()

def train_all_users():
    users_ref = db.collection("users").stream()
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "future_prediction", "train_forcaster.py"))
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    python_venv_path = r"C:\Users\Abid computers\Desktop\finance_manager_backend\venv\Scripts\python.exe"

    for doc in users_ref:
        user_id = doc.id
        print(f"Training for user {user_id}")
        subprocess.Popen(
            [python_venv_path, script_path, user_id],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        meta_path = os.path.join("models", user_id, "metadata.json")
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w") as f:
            f.write(json.dumps({"last_trained": datetime.datetime.utcnow().isoformat()}))

if __name__ == "__main__":
    print("Running monthly training job...")
    train_all_users()
