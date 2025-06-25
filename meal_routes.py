from flask import Blueprint, request, jsonify, current_app
uSlimMealRoutes = Blueprint('uSlimMealRoutess', __name__, url_prefix="/meals")

from sql import SelectSQL, InsertIntoSQL
import datetime

@uSlimMealRoutes.route('/mealplans/complete-meal', methods=['POST'])
def complete_meal():
    try:
        data = request.get_json()
        meal_id = data.get("meal_id")
        user_id = data.get("user_id")
        today = datetime.datetime.now().date()

        if not meal_id or not user_id:
            return jsonify({"error": "meal_id and user_id required"}), 400

        # Check if already completed today
        sql_check = """
            SELECT id FROM meal_completion 
            WHERE user_id = %s AND meal_id = %s AND DATE(completed_at) = %s
        """
        existing, _ = SelectSQL(sql_check, db="iSlim", values=(user_id, meal_id, today))

        if existing:
            return jsonify({"status": "already_completed"}), 200

        # Insert meal completion record
        sql_insert = """
            INSERT INTO meal_completion (user_id, meal_id, completed_at)
            VALUES (%s, %s, NOW())
        """
        InsertIntoSQL(sql_insert, db="iSlim", values=(user_id, meal_id))

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("❌ Error in /mealplans/complete-meal:", e)
        return jsonify({"error": str(e)}), 500

@uSlimMealRoutes.route('/completed-meals/<int:user_id>', methods=['GET'])
def get_completed_meals(user_id):
    try:
        today = datetime.datetime.now().date()
        sql = """
            SELECT meal_id FROM meal_completion
            WHERE user_id = %s AND DATE(completed_at) = %s
        """
        rows, _ = SelectSQL(sql, db="iSlim", values=(user_id, today))
        meal_ids = [row[0] for row in rows]
        return jsonify({"completed_meals": meal_ids}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uSlimMealRoutes.route('/mealplans/<int:plan_id>', methods=['GET'])
def get_meal_plan(plan_id):
    import time

    try:
        sql = """
            SELECT d.day_of_week, m.id, m.meal_type, m.title, m.calories, m.protein, m.carbs, m.fats, m.icons
            FROM meal_days d
            LEFT JOIN meals m ON d.id = m.meal_day_id
            WHERE d.meal_plan_id = %s
            ORDER BY d.day_of_week, m.meal_type
        """
        rows, _ = SelectSQL(sql, db="iSlim", values=(plan_id,))
        
        grouped = {}
        for row in rows:
            day = row[0]
            meal = dict(zip(["id", "meal_type", "title", "calories", "protein", "carbs", "fats", "icons"], row[1:]))

            iconList = []
            if meal['icons'] != "": # Use the temporary key for the raw icon data
                # Ensure it's treated as a string before splitting
                icons_raw = str(meal['icons'])
                icons = icons_raw.split(",")

                for icon in icons:
                    iconList.append({
                        "iconName": icon.strip() # .strip() to remove any whitespace from split
                    })
                    
            meal['icons'] = iconList
            if day not in grouped:
                grouped[day] = []
                # --- THIS IS THE CRUCIAL CHANGE ---
            processed_meal = {}
            for k, v in meal.items():
                if k == "icons":
                    processed_meal[k] = v  # Keep 'icons' as the Python list of dictionaries
                else:
                    processed_meal[k] = str(v) # Convert other values to string

            if processed_meal.get("meal_type"):
                grouped[day].append(processed_meal)
                
        result = {"days": [{"day": d, "meals": m} for d, m in grouped.items()]}
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500