from flask import Blueprint, request, jsonify, current_app
uSlimYogaRoutes = Blueprint('uSlimYogaRoutes', __name__, url_prefix="/yoga")

from sql import SelectSQL
from paRoutes.iSlim.utils import *

@uSlimYogaRoutes.route("/yoga-videos/by-user", methods=["POST"])
def getYogaVideos():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        weekday = data.get("weekday", "").capitalize()

        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        sql = "SELECT dataKey, dataValue FROM user_data WHERE userId = %s"
        rows, _ = SelectSQL(sql, db="iSlim", values=(user_id,))

        user_data = {row[0]: row[1] for row in rows}
        videos = []
        if "yoga" in user_data['activities'].lower():
            videos = getYogaVideosByUser(user_id)

        vidResp = []
        for vid in videos:
            vidResp.append({
                "name": vid[2],
                "link": vid[3].replace("http:///", "https://", 1),
            })

        return jsonify(vidResp)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
