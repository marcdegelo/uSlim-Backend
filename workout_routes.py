from flask import Blueprint, request, jsonify, current_app
uSlimWorkoutRoutes = Blueprint('uSlimWorkoutRoutess', __name__, url_prefix="/workout")

from sql import SelectSQL, InsertIntoSQL
import datetime

@uSlimWorkoutRoutes.route("/completed_workouts/<int:user_id>", methods=["GET"])
def get_completed_workouts(user_id):
    try:
        sql = "SELECT workout_id FROM workout_completion WHERE user_id = %s"
        rows, _ = SelectSQL(sql, db="iSlim", values=(user_id,))

        workout_ids = [row[0] for row in rows]
        return jsonify({"completed_workouts": workout_ids}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uSlimWorkoutRoutes.route("/complete_workout", methods=["POST"])
def complete_workout():
    data = request.get_json()
    user_id = data.get("user_id")
    workout_id = data.get("workout_id")

    if not user_id or not workout_id:
        return jsonify({"error": "Missing user_id or workout_id"}), 400

    try:
        now = datetime.datetime.now()
        date_only = now.date()

        sql = """
            INSERT INTO workout_completion (user_id, workout_id, completed_at, date_only)
            VALUES (%s, %s, %s, %s)
        """
        InsertIntoSQL(sql, db="iSlim", values=(user_id, workout_id, now, date_only))

        return jsonify({"message": "Workout marked as completed"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500