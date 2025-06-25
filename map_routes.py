from flask import Blueprint, request, jsonify, current_app
uSlimMapRoutes = Blueprint('uSlimMapRoutess', __name__, url_prefix="/map")

import json
import jwt

from sql import InsertIntoSQL

@uSlimMapRoutes.route('/save_route', methods=['POST'])
def save_route():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        user_id = payload.get("user_id")
        if not user_id:
            return jsonify({"error": "Invalid token"}), 403
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    try:
        data = request.get_json()

        distance = data.get("distance_km")
        duration = data.get("duration_sec")
        calories = data.get("calories")
        path_list = data.get("path", [])

        if None in [distance, duration, calories, path_list]:
            return jsonify({"error": "Missing required fields"}), 400

        path_json = json.dumps(path_list)

        sql = """
            INSERT INTO routes (user_id, distance_km, duration_sec, calories, path)
            VALUES (%s, %s, %s, %s, %s)
        """
        InsertIntoSQL(sql, db="iSlim", values=(user_id, distance, duration, calories, path_json))

        return jsonify({"message": "Route saved successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500