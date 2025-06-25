from flask import Blueprint, request, jsonify, current_app
uSlimFitnessRoutes = Blueprint('uSlimFitnessRoutess', __name__, url_prefix="/fitness")

from sql import SelectSQL
from paRoutes.iSlim.utils import get_filtered_fitness_programs


@uSlimFitnessRoutes.route("/fitness_programs", methods=["GET"])
def get_fitness_programs():
    try:
        sql_programs = "SELECT id, name, description FROM fitness_programs"
        programs, _ = SelectSQL(sql_programs, db="iSlim")

        program_list = []
        for program_id, name, description in programs:
            sql_levels = "SELECT id, level_name, sessions_per_week FROM fitness_levels WHERE program_id = %s"
            levels, _ = SelectSQL(sql_levels, db="iSlim", values=(program_id,))

            level_list = []
            for level_id, level_name, sessions_per_week in levels:
                sql_workouts = "SELECT id, day_of_week, workout_name, description FROM fitness_workouts WHERE level_id = %s"
                workouts, _ = SelectSQL(sql_workouts, db="iSlim", values=(level_id,))

                workout_list = []
                for workout_id, day_of_week, workout_name, desc in workouts:
                    sql_exercises = "SELECT id, type, name, sets, reps, duration_seconds, notes FROM fitness_exercises WHERE workout_id = %s"
                    exercises, _ = SelectSQL(sql_exercises, db="iSlim", values=(workout_id,))

                    exercise_list = [
                        {
                            "id": ex[0],
                            "type": ex[1],
                            "name": ex[2],
                            "sets": ex[3],
                            "reps": ex[4],
                            "durationSeconds": ex[5],
                            "notes": ex[6],
                        }
                        for ex in exercises
                    ]

                    workout_list.append({
                        "id": workout_id,
                        "dayOfWeek": day_of_week,
                        "name": workout_name,
                        "description": desc,
                        "exercises": exercise_list
                    })

                level_list.append({
                    "id": level_id,
                    "name": level_name,
                    "sessionsPerWeek": sessions_per_week,
                    "workouts": workout_list
                })

            program_list.append({
                "id": program_id,
                "name": name,
                "description": description,
                "levels": level_list
            })

        return jsonify(program_list), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

def getWorkout(fitness_level, goal, weekday):
    try:
        sql = f"SELECT * from fitness_workouts WHERE day_of_week = %s AND LOWER(name) LIKE '%{goal.lower()}%' AND LOWER(name) LIKE '%{fitness_level.lower()}%';"
        rows, _ = SelectSQL(sql, db="iSlim", values=(weekday,))
        workouts = {row[0]: row[1] for row in rows}

        return workouts

    except Exception as e:
        current_app.logger.error(f"Error fetching workout: {str(e)}")
        return []

@uSlimFitnessRoutes.route("/fitness_programs/by-user", methods=["POST"])
def get_user_fitness_program_by_body():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        weekday = data.get("weekday", "").capitalize()

        user_id = 24

        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        sql = "SELECT dataKey, dataValue FROM user_data WHERE userId = %s"
        rows, _ = SelectSQL(sql, db="iSlim", values=(user_id,))

        user_data = {row[0]: row[1] for row in rows}
        fitness_level = user_data.get("fitnessLevel", "").lower()
        goal = user_data.get("goal", "").lower()

        # discordMsg(f"Weekend: {weekday}", islim=True)

        ret = get_filtered_fitness_programs(fitness_level, goal, weekday, user_id)

        return ret

    except Exception as e:
        return jsonify({"error": str(e)}), 500
