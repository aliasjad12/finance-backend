from datetime import datetime
import pandas as pd
from firebase_admin import firestore
import firebase_admin
from firebase_admin import credentials

# Safe Firebase initialization
if not firebase_admin._apps:
    cred = credentials.Certificate(
        "C:/Users/Abid computers/Desktop/finance_manager_backend/finalyear-3b277-firebase-adminsdk-fbsvc-b2c4c69496.json"
    )
    firebase_admin.initialize_app(cred)

db = firestore.client()

def fetch_category_monthly_series(user_id: str, category: str, months_back=None) -> pd.Series:
    """Returns monthly totals for a given category from Firestore"""
    records_ref = db.collection("users").document(user_id).collection("records")
    docs = records_ref.stream()

    rows = []
    for doc in docs:
        data = doc.to_dict()
        month_str = doc.id
        cat_exp = data.get("categoryExpenses", {})
        if category in cat_exp:
            rows.append({
                "month": pd.to_datetime(month_str),
                "amount": float(cat_exp[category])
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.Series([], dtype=float)

    df.set_index("month", inplace=True)
    df = df.sort_index()

    # ✅ Optional filter
    if months_back is not None:
        cutoff = pd.to_datetime(datetime.now()) - pd.DateOffset(months=months_back)
        df = df.loc[df.index >= cutoff]

    return df["amount"]

