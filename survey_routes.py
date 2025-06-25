
from flask import Blueprint, request, jsonify, current_app
uSlimSurveyRoutes = Blueprint('uSlimSurveyRoutes', __name__, url_prefix="/survey")

from sql import InsertIntoSQL, SelectSQL
from firebase_utils import verify_firebase_token

@uSlimSurveyRoutes.route('/submit_survey', methods=['POST'])
def submit_survey():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    data = request.get_json()

    if not token:
        return jsonify({"error": "Missing token"}), 401

    decoded = verify_firebase_token(token, "uSlimApp")
    if not decoded:
        return jsonify({"error": "Wrong token"}), 401

    email = decoded['email']

    try:
        user_row, _ = SelectSQL(f"SELECT * FROM users WHERE email = '{email}'", db="iSlim")
        if not user_row:
            return jsonify({"error": "Invalid token"}), 403

        user_id = user_row[0][0]
        for key, value in data.items():
            value_str = ",".join(value) if isinstance(value, list) else str(value)
            sql = f"""
                INSERT INTO user_data (userId, dataKey, dataValue)
                VALUES ('{user_id}', '{key}', '{value_str}')
                ON DUPLICATE KEY UPDATE dataValue = VALUES(dataValue)
            """
            InsertIntoSQL(sql, db="iSlim")

        return jsonify({"message": "Data saved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
