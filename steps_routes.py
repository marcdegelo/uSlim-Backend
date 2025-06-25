from flask import Blueprint, request, jsonify, current_app
uSlimStepsRoutes = Blueprint('uSlimStepsRoutess', __name__, url_prefix="/steps")

from sql import InsertIntoSQL, SelectSQL

import datetime

from flask import Blueprint, request, jsonify, current_app
uSlimStepsRoutes = Blueprint('uSlimStepsRoutess', __name__, url_prefix="/steps")

from sql import InsertIntoSQL, SelectSQL

import datetime

def get_user_profile(user_id):
    """
    Fetches user's age, gender, height, and weight from the 'user_data' table.
    """
    try:
        sql = """
            SELECT dataKey, dataValue
            FROM user_data
            WHERE userId = %s AND dataKey IN ('age', 'gender', 'height', 'weight')
        """
        rows, _ = SelectSQL(sql, db="iSlim", values=(user_id,))

        user_profile = {}
        for data_key, data_value in rows:
            user_profile[data_key] = data_value

        # Check if all necessary keys are present
        required_keys = ['age', 'gender', 'height', 'weight']
        if not all(key in user_profile for key in required_keys):
            print(f"❌ Incomplete user profile for user {user_id}: Missing one or more of {required_keys}")
            return None

        # Convert types as they are stored as strings in dataValue
        try:
            profile_data = {
                'age': int(user_profile['age']),
                'gender': user_profile['gender'].lower(), # Ensure lowercase for 'male'/'female' check
                'height_cm': float(user_profile['height']), # Assuming 'height' is in cm
                'weight_kg': float(user_profile['weight'])  # Assuming 'weight' is in kg
            }
            return profile_data
        except ValueError as ve:
            print(f"❌ Type conversion error for user {user_id} profile data: {ve}")
            return None

    except Exception as e:
        print(f"❌ Error fetching user profile for user {user_id}: {e}")
        return None

def fetch_calories_for_user(user_id):
    if not user_id:
        return {"error": "Missing user_id"}, 400

    user_profile = get_user_profile(user_id)
    if not user_profile:
        return {"error": "User profile not found or incomplete. Cannot calculate calories."}, 404

    # Fetch daily steps
    steps_data, steps_status = fetch_steps_for_user(user_id)
    if steps_status != 200:
        return steps_data, steps_status # Propagate error from fetch_steps_for_user

    if not steps_data or not steps_data.get("steps"):
        return {"calories": []}, 200 # No steps data, return empty calories

    calories_data = []

    # Extract user profile details
    weight_kg = user_profile['weight_kg']
    height_cm = user_profile['height_cm']
    age = user_profile['age']
    gender = user_profile['gender']

    # Convert height to meters for stride length calculation
    height_m = height_cm / 100.0

    # --- Calorie Calculation Logic ---
    # 1. Estimate Stride Length (a common approximation for walking)
    # This factor can vary, 0.414 is for average walking, adjust if needed for running.
    stride_length_m = height_m * 0.414

    # 2. Assume an Average Pace (and corresponding MET value)
    # This is the biggest assumption if you don't track time/speed directly.
    # We'll use a moderate brisk walk as a default.
    # A moderate brisk walk (e.g., 3.0 mph / 4.8 km/h) often has a MET value of ~3.5
    # Speed in meters per minute for 4.8 km/h: (4.8 * 1000 meters) / 60 minutes = 80 m/min
    assumed_met = 3.5
    assumed_pace_mps = 4.8 / 3.6 # Convert km/h to m/s: 4.8 km/h * 1000m/km / 3600s/h
    assumed_pace_mpm = assumed_pace_mps * 60 # Convert m/s to m/min

    for entry in steps_data["steps"]:
        total_steps = entry['count']
        day_timestamp = entry['day'] # Keep the original timestamp for the output

        # Calculate total distance
        total_distance_m = total_steps * stride_length_m

        # Estimate time spent active based on assumed pace
        # Avoid division by zero if assumed_pace_mpm is 0 or very small
        estimated_time_minutes = (total_distance_m / assumed_pace_mpm) if assumed_pace_mpm > 0 else 0

        # Calculate calories burned for this activity
        # Formula: Calories = Time (min) * (MET * 3.5 * Weight (kg)) / 200
        if estimated_time_minutes > 0 and weight_kg > 0:
            calories_from_steps = estimated_time_minutes * (assumed_met * 3.5 * weight_kg) / 200
        else:
            calories_from_steps = 0 # No activity or invalid weight

        # You might also want to include Basal Metabolic Rate (BMR) for the full day's estimate.
        # BMR (Mifflin-St Jeor Equation)
        if gender == 'male':
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
        elif gender == 'female':
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
        else:
            bmr = 0 # Handle unknown gender, or raise error

        # For daily totals, you'd typically add BMR to the active calories.
        # However, if your app is showing "calories burned FROM steps,"
        # you might only want to show `calories_from_steps`.
        # Let's provide both: 'active_calories' and 'total_estimated_calories'
        total_estimated_calories = bmr + calories_from_steps # This is a daily total

        calories_data.append({
            'day': day_timestamp,
            'steps': total_steps,
            'count': round(calories_from_steps, 2),
            'estimated_count': round(total_estimated_calories, 2) 
        })

    return {"calories": calories_data}, 200



def fetch_steps_for_user(user_id):
    if not user_id:
        return {"error": "Missing user_id"}, 400

    try:
        sql = """
            SELECT date, steps FROM daily_steps
            WHERE user_id = %s
            ORDER BY date ASC
        """
        rows, _ = SelectSQL(sql, db="iSlim", values=(user_id,))  # Use parameterized SQL

        step_data = []
        for date_obj, steps in rows:
            # Convert date to timestamp
            datetime_obj = datetime.datetime.combine(date_obj, datetime.datetime.min.time())
            timestamp = datetime_obj.timestamp()

            step_data.append({
                'day': timestamp,
                'count': steps
            })

        return {"steps": step_data}, 200

    except Exception as e:
        print(f"❌ Error fetching steps for user {user_id}: {e}")
        return {"error": str(e)}, 500

@uSlimStepsRoutes.route('/get_steps', methods=['GET'])
def get_steps():
    user_id = request.args.get("user_id")
    data, status = fetch_steps_for_user(user_id)
    return jsonify(data), status

@uSlimStepsRoutes.route('/get_calories', methods=['GET'])
def get_calories():
    user_id = request.args.get("user_id")
    data, status = fetch_calories_for_user(user_id)
    return jsonify(data), status


@uSlimStepsRoutes.route('/save_steps', methods=['POST'])
def save_steps():
    data = request.get_json()
    user_id = data.get("user_id")
    steps = data.get("steps")
    today = datetime.date.today().isoformat()

    if not user_id or steps is None:
        return jsonify({"error": "Missing user_id or steps"}), 400

    try:
        sql = """
            INSERT INTO daily_steps (user_id, date, steps)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE steps = %s
        """
        InsertIntoSQL(sql, db="iSlim", values=(user_id, today, steps, steps))

        return jsonify({"message": "Steps saved"}), 200
    except Exception as e:
        print(f"❌ Error saving steps for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500
