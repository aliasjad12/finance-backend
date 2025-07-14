from flask import Blueprint, request, jsonify
from firebase_admin import firestore
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime

bp = Blueprint('budget', __name__)
db = firestore.client()

@bp.route("/generate_budget", methods=["GET"])
def generate_budget():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    user_ref = db.collection("users").document(user_id)
    records_ref = user_ref.collection("records")
    records = list(records_ref.stream())
    if not records:
        return jsonify({"error": "No financial records found"}), 404

    records_data = [r.to_dict() | {"month": r.id} for r in records]
    records_data.sort(key=lambda r: r["month"])
    latest_month = records_data[-1]["month"]
    current_record = records_ref.document(latest_month).get().to_dict()

    income = current_record.get("totalIncome", 0)
    spent = current_record.get("spentAmount", 0)
    category_exp = current_record.get("categoryExpenses", {})

    now = datetime.now()
    monthly_savings_plan = {}
    weighted_goals = []
    goal_names = []

    goals_ref = user_ref.collection("savings_goals")
    goals = list(goals_ref.stream())
    savings_goals = {doc.id: doc.to_dict() for doc in goals}

    for doc_id, goal in savings_goals.items():
        name = goal.get("goal_name", doc_id)
        target = goal.get("target_amount", 0)
        saved = goal.get("amount_saved", 0)
        target_date = goal.get("end_date")

        months_left = 1
        goal_urgent = False

        if target_date:
            try:
                dt = datetime.fromisoformat(target_date)
                delta = (dt.year - now.year) * 12 + (dt.month - now.month)
                months_left = max(1, delta)
                if dt.month == now.month and dt.year == now.year:
                    goal_urgent = True
            except:
                pass

        monthly_needed = max((target - saved) / months_left, 0)
        monthly_savings_plan[name] = round(monthly_needed, 2)
        weighted_goals.append((doc_id, name, monthly_needed, months_left, goal_urgent))
        goal_names.append(name)

    total_monthly_savings = sum(monthly_savings_plan.values())

    cat_hist = {}
    for r in records_data:
        for cat, amt in r.get("categoryExpenses", {}).items():
            cat_hist.setdefault(cat, []).append(amt)

    recommended = {}
    total_forecast = 0
    if category_exp:
        for cat in category_exp:
            history = cat_hist.get(cat, [])
            if len(history) >= 2:
                X = np.arange(len(history)).reshape(-1, 1)
                y = np.array(history)
                model = LinearRegression().fit(X, y)
                predicted = round(max(model.predict([[len(history)]])[0], 0), 2)
            else:
                predicted = round(category_exp.get(cat, 0), 2)
            recommended[cat] = predicted
            total_forecast += predicted

    remaining_for_expenses = max(income - total_monthly_savings, 0)
    if total_forecast > remaining_for_expenses and total_forecast > 0:
        scale = remaining_for_expenses / total_forecast
        for cat in recommended:
            recommended[cat] = round(recommended[cat] * scale, 2)

    suggestions = {}
    income_left = income - spent

    if spent >= income:
        suggestions["⚠️ Overspending Alert"] = (
            f"You’ve already spent ₹{spent:.2f} out of ₹{income:.2f}. "
            "You’ve crossed your income limit this month."
        )
        if total_monthly_savings > 0:
            suggestions["💡 Tip"] = (
                f"Try saving for goals in the next month. Total savings needed: ₹{round(total_monthly_savings, 2)}."
            )
        for cat in sorted(recommended):
            suggestions[f"Next Month: {cat}"] = (
                f"Reduce spending in {cat} next month to support your savings."
            )
    else:
        extra_needed = total_monthly_savings - income_left
        sorted_cats = sorted(recommended.items(), key=lambda x: category_exp.get(x[0], 0), reverse=True)

        if extra_needed > 0:
            adjustable_total = sum(recommended.values())
            if adjustable_total > 0:
                for cat, _ in sorted_cats:
                    cut = round((recommended[cat] / adjustable_total) * extra_needed, 2)
                    recommended[cat] = max(0, round(recommended[cat] - cut, 2))
                    suggestions[cat] = (
                        f"Cut ₹{cut:.2f} from {cat} to help fund savings due soon."
                    )
        else:
            for cat in recommended:
                last = category_exp.get(cat, 0)
                diff = round(recommended[cat] - last, 2)
                if diff < 0:
                    suggestions[cat] = (
                        f"Reduce {cat} by ₹{abs(diff):.2f} to increase your savings."
                    )
                elif diff > 0:
                    suggestions[cat] = (
                        f"You can increase {cat} by ₹{diff:.2f} if savings are on track."
                    )

    # Enhanced goal-specific suggestions with proportional saving
    income_left = income - spent
    allocations = {}

    if total_monthly_savings > 0 and income_left > 0:
        if income_left >= total_monthly_savings:
            allocations = {n: round(m, 2) for n, m in monthly_savings_plan.items()}
        else:
            for n, m in monthly_savings_plan.items():
                share = m / total_monthly_savings
                allocations[n] = round(share * income_left, 2)

    for g_id, name, monthly_needed, months_left, urgent in weighted_goals:
        save_now = allocations.get(name, 0.0)

        goal_data = savings_goals[g_id]
        target = goal_data.get("target_amount", 0)
        saved = goal_data.get("amount_saved", 0)

        remaining_after_now = max(target - saved - save_now, 0)
        months_left_future = max(months_left - 1, 1)
        future_monthly = round(remaining_after_now / months_left_future, 2)

        if urgent:
            if save_now >= remaining_after_now:
                suggestions[f"Goal: {name}"] = (
                    f"This goal ends this month. Put aside ₨{save_now:.0f} now to complete it."
                )
            else:
                suggestions[f"⚠️ Goal: {name}"] = (
                    f"You only have ₨{income_left:.0f} left, which isn’t enough to finish “{name}”. "
                    "Extend the deadline or adjust the target."
                )
        else:
            suggestions[f"Goal: {name}"] = (
                f"Save ₨{save_now:.0f} this month, then about ₨{future_monthly:.0f}/month "
                f"for the next {months_left_future} month(s) to reach “{name}”."
            )

    if income > 0 and income_left / income < 0.10:
        suggestions["⚠️ Income Warning"] = (
            f"Only ₹{income_left:.2f} (less than 10%) of salary remains. Avoid non-essential expenses."
        )

    if not recommended:
        suggestions["Info"] = "No category expense data found. Add expenses to see insights."

    return jsonify({
        "recommended_budget": recommended,
        "suggestions": suggestions,
        "total_income": income,
        "spent": spent,
        "savings_goals": monthly_savings_plan,
        "total_monthly_savings_needed": round(total_monthly_savings, 2),
        "leftover_budget": income - total_monthly_savings,
        "income_left": income_left,
        "savings_possible": round(income_left - sum(recommended.values()), 2)
    })
