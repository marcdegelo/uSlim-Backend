from flask import Blueprint, request, jsonify, current_app
uSlimUtilsRoutes = Blueprint('uSlimUtilsRoutess', __name__, url_prefix="/utils")

from sql import InsertIntoSQL, SelectSQL

import os
import json
import base64
import datetime

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@uSlimUtilsRoutes.route('/check-version', methods=['POST'])
def check_version():
    try:
        user_version = request.json.get('version')
        if user_version is None:
            return jsonify({"error": "Missing version in request"}), 400

        sql = "SELECT version FROM version"
        rows, _ = SelectSQL(sql, db="iSlim")

        if not rows:
            return jsonify({"error": "No version information available"}), 500

        curr_version = rows[0][0]
        force_update = user_version != curr_version

        return jsonify({
            "force_update": force_update,
            "latest_version": curr_version
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uSlimUtilsRoutes.route('/xp/award', methods=['POST'])
def award_xp():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        xp_amount = data.get("xp_amount")
        source_id = data.get("source_id")
        source_type = data.get("source_type")
        reason = data.get("reason", "XP Event")

        if not all([user_id, xp_amount, source_id, source_type]):
            return jsonify({"error": "Missing required fields"}), 400

        # Log the XP event safely
        InsertIntoSQL("""
            INSERT INTO xp_events (user_id, xp_amount, reason, source_id, source_type)
            VALUES (%s, %s, %s, %s, %s)
        """, db="iSlim", values=(user_id, xp_amount, reason, source_id, source_type))

        # Update total XP safely
        InsertIntoSQL("""
            INSERT INTO user_xp (user_id, total_xp)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE total_xp = total_xp + VALUES(total_xp)
        """, db="iSlim", values=(user_id, xp_amount))

        return jsonify({"status": "success", "xp_added": xp_amount}), 200

    except Exception as e:
        print(f"XP Award Error: {e}")
        return jsonify({"error": str(e)}), 500
    

@uSlimUtilsRoutes.route('/ping', methods=['GET'])
def ping_islim():
    return {'msg': 'iSlim API works'}


@uSlimUtilsRoutes.route('/version', methods=['GET'])
def get_latest_version():
    return jsonify({
        "versionCode": 2,
        "versionName": "1.1",
        "updateRequired": True,
        "updateUrl": "https://play.google.com/store/apps/details?id=com.flutschi.androidapp"
    })

@uSlimUtilsRoutes.route("/upload-image", methods=["POST"])
def upload_image():
    file = request.files.get('image')
    info = request.form.get('info')

    try:
        info = json.loads(info)
    except:
        return jsonify({"error": "Invalid JSON format for info"}), 400

    if not file or file.filename == '':
        return jsonify({"error": "No image uploaded"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    try:
        with open(file_path, "rb") as img_file:
            img_bytes = img_file.read()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        os.remove(file_path)

        user_id = info.get("userId")

        if "mealId" in info:
            meal_id = info.get("mealId")
            meal = get_meals_by_ids(meal_id)

            systemPrompt = "You are a food recognition AI. You will receive an image of a meal and you will tell me what it is. If you are not sure, simply answer 'YES', 'NO' or 'I DON'T KNOW'."
            userPrompt = f"{systemPrompt}\nIs the picture showing this meal: {meal[0]['title']} ({meal[0]['meal_type']})?"

            gemini_response = generate_reply_with_gemini(
                userPrompt=userPrompt,
                images=[{"mime": file.mimetype, "base64": img_base64}]
            )

            if gemini_response['reply'].upper() in ["I DON'T KNOW", "NO"]:
                return jsonify({
                    "status": "try_again",
                    "message": "Meal not recognized. Please try again.",
                    "result": gemini_response
                }), 200

            # Save meal image optionally
            image_path = os.path.join(UPLOAD_FOLDER, f"{meal_id}.png")
            with open(image_path, "wb") as img_file:
                img_file.write(img_bytes)

            today = datetime.datetime.now().date()

            sql_check = """
                SELECT id FROM meal_completion
                WHERE user_id = %s AND meal_id = %s AND DATE(completed_at) = %s
            """
            existing, _ = SelectSQL(sql_check, db="iSlim", values=(user_id, meal_id, today))

            if not existing:
                sql_insert = """
                    INSERT INTO meal_completion (user_id, meal_id, completed_at)
                    VALUES (%s, %s, NOW())
                """
                InsertIntoSQL(sql_insert, db="iSlim", values=(user_id, meal_id))

            return jsonify({
                "status": "completed",
                "message": "Meal recognized and marked as complete.",
                "result": gemini_response
            }), 200

        elif "workoutId" in info:
            workout_id = info.get("workoutId")
            workout = get_workout_by_id(workout_id)

            systemPrompt = "You are a fitness activity AI. Look at the uploaded image and tell me if the person is working out. Only answer 'WORKOUT ONLY', 'WORKOUT + SWEAT', or 'NO WORKOUT'."
            userPrompt = "Is the person shown in the image working out?"

            gemini_response = generate_reply_with_gemini(
                userPrompt=userPrompt,
                images=[{"mime": file.mimetype, "base64": img_base64}]
            )

            if gemini_response['reply'].upper() in ["NO WORKOUT", "I DON'T KNOW"]:
                return jsonify({
                    "status": "try_again",
                    "message": "Workout not recognized. Please try again.",
                    "result": gemini_response
                }), 200

            now = datetime.datetime.now()
            sql_check = """
                SELECT id FROM workout_completion
                WHERE user_id = %s AND workout_id = %s AND DATE(completed_at) = %s
            """
            existing, _ = SelectSQL(sql_check, db="iSlim", values=(user_id, workout_id, now.date()))

            if not existing:
                sql_insert = """
                    INSERT INTO workout_completion (user_id, workout_id, completed_at, date_only)
                    VALUES (%s, %s, %s, %s)
                """
                InsertIntoSQL(sql_insert, db="iSlim", values=(user_id, workout_id, now, now.date()))

            return jsonify({
                "status": "completed",
                "message": "Workout recognized and marked as complete.",
                "result": gemini_response
            }), 200

        else:
            return jsonify({"error": "Missing mealId or workoutId in info"}), 400

    except Exception as e:
        print(f"Error processing image: {e}")
        return jsonify({"error": str(e)}), 500