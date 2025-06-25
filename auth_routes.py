import os
import base64
import datetime
import requests
from flask import Blueprint, request, jsonify, current_app
from google.oauth2 import id_token
from google.auth.transport import requests as googleReq
import jwt

from AI.geminiHandler import *
from paRoutes.iSlim.utils import *

import firebase_admin
from firebase_admin import auth
from firebase_utils import verify_firebase_token

from sql import SelectSQL, InsertIntoSQL
from flask_bcrypt import Bcrypt


bcrypt = Bcrypt()
uSlimAuthRoutes = Blueprint('uSlimAuthRoutess', __name__, url_prefix="/auth")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PROFILE_FOLDER = "profile_images"

CURRENT_VERSION = 1

import os
import base64
import datetime
import requests
from flask import Blueprint, request, jsonify, current_app
from google.oauth2 import id_token
from google.auth.transport import requests as googleReq
import jwt
import logging # Import logging

# Assuming these are correctly defined and accessible
from AI.geminiHandler import *
from paRoutes.iSlim.utils import *

import firebase_admin
from firebase_admin import auth, exceptions as firebase_exceptions # Import auth and exceptions
from firebase_utils import verify_firebase_token # This should be a function that verifies the token using firebase_admin.auth.verify_id_token()

from sql import SelectSQL, InsertIntoSQL # Assuming these are wrappers for your DB operations
from flask_bcrypt import Bcrypt


bcrypt = Bcrypt()
uSlimAuthRoutes = Blueprint('uSlimAuthRoutess', __name__, url_prefix="/auth")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PROFILE_FOLDER = "profile_images"

CURRENT_VERSION = 1

# Configure logging for better debugging (add this at the top level or in app setup)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def getUserbyFirebaseUID(uid):
    return None

@uSlimAuthRoutes.route('/register', methods=['POST'])
def slimRegister():
    data = request.get_json()
    username = data.get("username")
    # We no longer receive a raw password for Firebase registrations
    id_token = data.get("id_token") # Expecting the Firebase ID token from the client

    if not all([username, id_token]): # Email can be derived from the token
        logger.warning("Missing username or Firebase ID token in registration request.")
        return jsonify({"error": "Missing username or Firebase ID token"}), 400

    try:
        # Verify the Firebase ID token using your utility function
        # This function should wrap firebase_admin.auth.verify_id_token()
        decoded_token = verify_firebase_token(id_token, "uSlimApp") # "uSlimApp" might be your app name/audience
        firebase_uid = decoded_token['uid']
        firebase_email = decoded_token.get('email') # Get email from Firebase token claims

        if not firebase_email:
            logger.error(f"Firebase token for UID {firebase_uid} does not contain an email.")
            return jsonify({"error": "Firebase token missing email address. Please ensure user has an email."}), 400

        # Check if a user with this Firebase UID or email already exists in your local database
        # This is crucial to prevent duplicate entries and link accounts.
        user_by_email = get_user_by_email(firebase_email)
        user_by_firebase_uid = getUserbyFirebaseUID(firebase_uid) 

        if user_by_email and user_by_firebase_uid and user_by_email['id'] == user_by_firebase_uid['id']:
            # User exists and is already linked to this Firebase account
            logger.info(f"User with email {firebase_email} and Firebase UID {firebase_uid} already exists and linked. Treating as re-registration/login.")
            user = user_by_email # Use the existing user
            # Update token and return
            token = generate_token(user["id"])
            InsertIntoSQL("UPDATE users SET token = %s WHERE id = %s", (token, user["id"]))
            return jsonify({
                "token": token,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "profile_picture": user.get("profile_picture")
                }
            }), 200 # OK if essentially logging in an existing user

        elif user_by_email and not user_by_firebase_uid:
            # User exists by email but isn't linked to a Firebase UID yet. Link them.
            logger.info(f"Existing user with email {firebase_email} found. Linking with Firebase UID {firebase_uid}.")
            user = user_by_email
            InsertIntoSQL(
                "UPDATE users SET firebase_uid = %s WHERE id = %s",
                (firebase_uid, user["id"])
            )
            # Update token and return
            token = generate_token(user["id"])
            InsertIntoSQL("UPDATE users SET token = %s WHERE id = %s", (token, user["id"]))
            return jsonify({
                "token": token,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "profile_picture": user.get("profile_picture")
                }
            }), 200 # OK if essentially logging in an existing user

        elif user_by_firebase_uid and not user_by_email:
            # This scenario indicates an issue if email is primary key.
            # It means a Firebase UID is present, but not the email provided by Firebase.
            # This should ideally not happen if Firebase ensures unique emails.
            # Handle as a conflict or error.
            logger.error(f"User found by Firebase UID {firebase_uid} but not by email {firebase_email}. Data inconsistency.")
            return jsonify({"error": "Data inconsistency: Firebase UID exists, but email does not match our records."}), 500

        elif not user_by_email and not user_by_firebase_uid:
            # New user: Create a new record in your database.
            logger.info(f"New user registration for {username} ({firebase_email}) with Firebase UID {firebase_uid}.")
            # Note: We are no longer hashing a `password` from the client here.
            # Your `users` table should have a `firebase_uid` column (e.g., VARCHAR(128) UNIQUE).
            # The `password` column might become nullable or optional for Firebase-only users.
            InsertIntoSQL(
                "INSERT INTO users (username, email, firebase_uid) VALUES (%s, %s, %s)",
                (username, firebase_email, firebase_uid)
            )

            # Retrieve the newly created user to get their local ID
            user = get_user_by_email(firebase_email) # Or get_user_by_firebase_uid(firebase_uid)
            if not user:
                logger.error(f"Failed to retrieve newly created user for email {firebase_email}.")
                return jsonify({"error": "Failed to create user record in backend."}), 500

            token = generate_token(user["id"]) # Generate your backend's session token
            InsertIntoSQL(
                "UPDATE users SET token = %s WHERE id = %s",
                (token, user["id"])
            )

            return jsonify({
                "token": token,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "profile_picture": user.get("profile_picture")
                }
            }), 201 # 201 Created for a new resource

        else:
            # This case covers scenarios where user_by_email and user_by_firebase_uid exist
            # but their IDs don't match, indicating a conflict.
            logger.error(f"Conflict: Email {firebase_email} exists (ID: {user_by_email['id']}) but linked to different Firebase UID than {firebase_uid} (linked to: {user_by_firebase_uid.get('firebase_uid')}).")
            return jsonify({"error": "An account with this email already exists but is linked to a different Firebase account."}), 409 # Conflict

    except firebase_exceptions.FirebaseError as e:
        logger.error(f"Firebase authentication error during registration: {e}")
        return jsonify({"error": f"Firebase authentication failed: {e.args[0]}"}), 401 # Unauthorized or Bad Request
    except Exception as e:
        logger.exception("An unexpected error occurred during backend registration.")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    
@uSlimAuthRoutes.route('/login2', methods=['POST'])
def slimLogin():
    data = request.json
    email, password = data.get("email"), data.get("password")
    user = get_user_by_email(email)

    if not user or not bcrypt.check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    image_path = os.path.join(PROFILE_FOLDER, f"{user['username']}.png")
    image_url = f"{request.host_url}{image_path}" if os.path.exists(image_path) else user.get("profile_picture")

    token = generate_token(user["id"])
    InsertIntoSQL("UPDATE users SET token = %s WHERE id = %s", (token, user["id"]))

    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "profile_picture": image_url
        }
    })

@uSlimAuthRoutes.route('/login', methods=['POST'])
def slimGoogleLogin():
    data = request.get_json()
    token = data.get("id_token")

    if not token:
        return jsonify({"error": "Missing ID Token"}), 400

    try:
        decoded_token = verify_firebase_token(token, "uSlimApp")

        if not decoded_token:
            return jsonify({"error": "Invalid Google Token"}), 401
        
        email = decoded_token["email"]
        name = decoded_token["name"]  # Or use "given_name" and "family_name"
        existing_user = get_user_by_email(email)

        if existing_user:
            # User exists in MySQL, log them in
            user_id = existing_user["id"]
        else:
            # User doesn"t exist in MySQL, create them
            hashed_password = bcrypt.generate_password_hash(email).decode("utf-8") # Generate a random password
            update_db(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (name, email, hashed_password)
            )
            user = get_user_by_email(email)
            user_id = user["id"]

        return jsonify({
            "token": token,
            "user": {
                "id": user_id,
                "username": name,
                "email": email,
                "profile_picture": None
            }
        })

    except ValueError as e:
        # Invalid Google ID token
        return jsonify({"error": "Invalid Google Token: " + str(e)}), 401
    except firebase_admin.auth.AuthError as e:
        # Firebase Authentication error
        return jsonify({"error": "Firebase Authentication Error: " + str(e)}), 500

@uSlimAuthRoutes.route('/userdata', methods=['GET'])
def get_user_data():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({'error': 'Missing token'}), 401

    decoded = verify_firebase_token(token, "uSlimApp")
    if not decoded:
        print("invalid token")
        return jsonify({'error': 'Invalid token'}), 403
    email = decoded.get('email')

    try:
        user_row, _ = SelectSQL(f"SELECT * FROM users WHERE email = '{email}'", db="iSlim")
        if not user_row:
            return jsonify({'error': 'Invalid token'}), 403

        user_id = user_row[0][0]
        userName = user_row[0][1]

        rows, _ = SelectSQL(f"SELECT dataKey, dataValue FROM user_data WHERE userId = {user_id}", db="iSlim")
        data = {k: v for k, v in rows}

        xp, _ = SelectSQL(f"SELECT total_xp FROM user_xp WHERE user_id = {user_id}", db="iSlim")

        try:
            xp = int(xp[0][0])
        except:
            xp = 0

        def parse_list(k): return data.get(k, "").split(',') if data.get(k) else []

        retObj = {
            "gender": data.get("gender"),
            "weight": float(data["weight"]) if "weight" in data else None,
            "height": data.get("height"),
            "age": data.get("age"),
            "goal": data.get("goal"),
            "fitnessLevel": data.get("fitnessLevel"),
            "activityTime": data.get("activityTime"),
            "activities": parse_list("activities"),
            "healthConditions": parse_list("healthConditions"),
            "barriers": parse_list("barriers"),
            "dietType": data.get("dietType"),
            "workoutStyle": data.get("workoutStyle"),
            "xp": int(xp),
            "id": user_id,
            "userName": userName,
            "email": email,
            "phoneNumber": data.get("phoneNumber"),
            "hasPass": bool(data.get("hasPass"))
        }

        return jsonify(retObj), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

codes = {}  # Store codes in memory
import random

def update_user_password(email, new_password):
    """Updates the user's password in the MySQL database."""
    hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    
    # Check if user exists
    sql_check = "SELECT id FROM users WHERE email = %s"
    user, _ = SelectSQL(sql_check, db="iSlim", values=(email,))
    if not user:
        raise Exception("User not found")

    sql_update = "UPDATE users SET password = %s WHERE email = %s"
    InsertIntoSQL(sql_update, db="iSlim", values=(hashed_password, email))
    
    return True

@uSlimAuthRoutes.route('/set_new_password', methods=['POST'])
def set_new_password():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('newPassword')  # Get the new password

    if not email or not code or not new_password:
        return jsonify({"error": "Email, code, and new password are required"}), 400

    saved_code_data = codes.get(email)

    if not saved_code_data:
        return jsonify({"error": "No code found for this email"}), 400

    saved_code, expires_at = saved_code_data

    if datetime.now() > expires_at:  # Use timezone.utc
        return jsonify({"error": "Code expired"}), 400

    if code != saved_code:
        return jsonify({"error": "Invalid code"}), 400

    # Now that the code is verified, update the user''s password
    try:
        # Replace this with your actual password update logic
        update_user_password(email, new_password)  # This function needs to be implemented
        del codes[email] # Remove the code after password reset
        return jsonify({"message": "Password reset successfully"}), 200
    except Exception as e:  # Handle potential errors during password update
        return jsonify({"error": "Failed to update password", "details": str(e)}), 500
    
@uSlimAuthRoutes.route('/get_verification_code', methods=['POST'])
def get_verification_code():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Generate 6-digit random code
    code = str(random.randint(100000, 999999))
    expiration_time = datetime.datetime.now() + datetime.timedelta(minutes=1)  # Correct usage

    codes[email] = (code, expiration_time)

    try:
        send_email_verification(email, code)
    except Exception as e:
        return jsonify({"error": "Failed to send email", "details": str(e)}), 500

    return jsonify({"message": "Verification code sent"}), 200

@uSlimAuthRoutes.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    email = data.get('email')
    code = data.get('code')

    if not email or not code:
        return jsonify({"error": "Email and code are required"}), 400

    saved_code_data = codes.get(email)

    if not saved_code_data:
        return jsonify({"error": "No code found for this email"}), 400

    saved_code, expires_at = saved_code_data

    if datetime.utcnow() > expires_at:
        return jsonify({"error": "Code expired"}), 400

    if code != saved_code:
        return jsonify({"error": "Invalid code"}), 400

    return jsonify({"message": "Code verified successfully"}), 200
