from flask import Blueprint, request, jsonify, current_app
uSlimProfileRoutes = Blueprint('uSlimProfileRoutess', __name__, url_prefix="/profile")

import base64
import os

PROFILE_FOLDER = "profile_images"
os.makedirs(PROFILE_FOLDER, exist_ok=True)

@uSlimProfileRoutes.route("/profile/upload-profile-image", methods=["POST"])
def upload_profile_image():
    try:
        data = request.get_json()
        username = data.get("username")
        image_data = data.get("image_data")

        if not username or not image_data:
            return jsonify({"error": "Missing username or image data"}), 400

        image_bytes = base64.b64decode(image_data)
        filename = f"{username}.png"
        image_path = os.path.join(PROFILE_FOLDER, filename)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        image_url = request.host_url.rstrip('/') + f"/static/{image_path}"
        return jsonify({"message": "Profile picture updated!", "image_url": image_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
