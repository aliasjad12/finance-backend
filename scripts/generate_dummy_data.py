import random
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# ─── 1. Firebase Initialization ───────────────────────────────────────
if not firebase_admin._apps:
    cred = credentials.Certificate(
        r"C:/Users/Abid computers/Desktop/finance_manager_backend/finalyear-3b277-firebase-adminsdk-fbsvc-b2c4c69496.json"
    )
    firebase_admin.initialize_app(cred)

db = firestore.client()
USER_ID = "HZD4IGpQp6emDjqGFr3Ph2y8vtn1"
TOTAL_INCOME = float(250_000)
CATEGORIES = ["Food", "Utilities", "Travel", "Shopping", "Health"]

records_ref = db.collection("users").document(USER_ID).collection("records")

# ─── 2. Recursive Delete Function ─────────────────────────────────────
def delete_collection(coll_ref, batch_size=20):
    while True:
        docs = list(coll_ref.limit(batch_size).stream())
        if not docs:
            break
        for doc in docs:
            for subcoll in doc.reference.collections():
                delete_collection(subcoll)
            doc.reference.delete()

def delete_all_records():
    while True:
        docs = list(records_ref.limit(5).stream())
        if not docs:
            break
        for doc in docs:
            for subcoll in doc.reference.collections():
                delete_collection(subcoll)
            doc.reference.delete()

delete_all_records()
print("🧹 All previous records and nested subcollections removed.")

# ─── 3. Month Factor to Simulate Seasonality ─────────────────────────
def month_factor(month, base=1.0):
    if month == 12:
        return base * 1.20
    if month in (6, 7, 8):
        return base * 1.40
    if month in (1, 2):
        return base * 1.15
    if month == 11:
        return base * 1.25
    return base

# ─── 4. Create 36 Months Data: Aug 2022 → Jul 2025 ───────────────────
start = datetime(2025, 8, 1)

for i in range(4):
    month_dt = datetime(start.year, start.month, 1)
    month_str = month_dt.strftime("%Y-%m")
    m_num = month_dt.month
    yr_frac = (3 - i) / 4

    # Generate initial random category values
    food = float(random.uniform(35_000, 45_000) * (1 + 0.04 * yr_frac) * month_factor(m_num))
    util = float(random.uniform(10_000, 14_000) * month_factor(m_num))
    travel = float(random.uniform(7_000, 10_000) * month_factor(m_num))
    shopping = float(random.uniform(12_000, 18_000) * (1 + 0.06 * yr_frac) * month_factor(m_num))
    health = float(TOTAL_INCOME * random.uniform(0.025, 0.055))

    raw_total = food + util + travel + shopping + health
    if raw_total > TOTAL_INCOME:
        scale = TOTAL_INCOME / raw_total
        food *= scale
        util *= scale
        travel *= scale
        shopping *= scale
        health = TOTAL_INCOME - (food + util + travel + shopping)

    # Original totals for expense distribution
    original_cat_map = {
        "Food":      float(round(food, 2)),
        "Utilities": float(round(util, 2)),
        "Travel":    float(round(travel, 2)),
        "Shopping":  float(round(shopping, 2)),
        "Health":    float(round(health, 2))
    }

    # Create month doc reference
    month_doc = records_ref.document(month_str)
    cat_map = {}

    # ─── 5. Add Category-wise Expense Documents ─────────────────────
    for cat, total_amt in original_cat_map.items():
        cat_doc = month_doc.collection("categories").document(cat)
        exp_ref = cat_doc.collection("expenses")

        num_entries = random.randint(3, 6)
        splits = []
        remaining = total_amt
        for j in range(num_entries):
            if j == num_entries - 1:
                amt = remaining
            else:
                max_amt = remaining / (num_entries - j) * 1.2
                amt = round(random.uniform(remaining / (num_entries - j) * 0.8, max_amt), 2)
                remaining -= amt
            splits.append(round(amt, 2))

        for j, amt in enumerate(splits, start=1):
            exp_ref.document(f"exp_{j}").set({
                "amount": float(amt),
                "timestamp": month_dt + timedelta(days=random.randint(0, 27))
            })

        # ✅ Recalculate exact total from saved expenses
        expenses = exp_ref.stream()
        actual_total = 0
        for doc in expenses:
            actual_total += float(doc.to_dict().get('amount', 0))
        cat_map[cat] = round(actual_total, 2)

    # ─── 6. Add Main Monthly Document AFTER expense inserts ──────────
    month_doc.set({
        "totalIncome": float(TOTAL_INCOME),
        "spentAmount": float(round(sum(cat_map.values()), 2)),
        "categoryExpenses": {k: float(v) for k, v in cat_map.items() if v > 0}
    })

    # ─── 7. Add Dummy Notification ─────────────────────────────────
    month_doc.collection("notifications").add({
        "title": "Welcome!",
        "body": f"Generated data for {month_str}",
        "timestamp": datetime.now(),
        "read": False
    })

    # 🔁 Move to previous month
    prev = month_dt.replace(day=1) - timedelta(days=1)
    start = prev.replace(day=1)

print("✅ Dummy data generated for 36 months (Aug 2022 → Jul 2025).")
