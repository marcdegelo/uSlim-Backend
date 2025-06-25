import datetime
import jwt
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import jsonify
from google.oauth2 import id_token
from google.auth.transport import requests as googleReq

from sql import ConnectSQL, SelectSQL, InsertIntoSQL
from app import app

GOOGLE_CLIENT_ID = "393366931388-hutniuobiks7vlhoee4ujho4k7pbb768.apps.googleusercontent.com"

def get_db_connection():
    return ConnectSQL("iSlim")

def update_db(query, values):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()

def generate_token(user_id):
    token_payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(token_payload, app.config["SECRET_KEY"], algorithm="HS256")

def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def verify_google_token(id_token_str):
    try:
        google_info = id_token.verify_oauth2_token(id_token_str, googleReq.Request(), GOOGLE_CLIENT_ID)
        email = google_info.get("email")
        user = get_user_by_email(email)
        if user:
            return user
        
        username = google_info.get("name", email.split("@")[0])
        InsertIntoSQL(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, "google_auth")
        )
        return get_user_by_email(email)
    except ValueError:
        return None

def get_meals_by_ids(meal_ids):
    if not meal_ids:
        return []

    if isinstance(meal_ids, int):
        meal_ids = [meal_ids]

    ids_str = ",".join(str(int(mid)) for mid in meal_ids)

    sql = f"""
        SELECT id, meal_type, title, calories, protein, carbs, fats
        FROM meals
        WHERE id IN ({ids_str})
    """
    rows, _ = SelectSQL(sql, db="iSlim")

    meals = []
    for row in rows:
        meals.append({
            "id": row[0],
            "meal_type": row[1],
            "title": row[2],
            "calories": str(row[3]),
            "protein": str(row[4]),
            "carbs": str(row[5]),
            "fats": str(row[6])
        })
    return meals

def get_workout_by_id(workout_id):
    sql = """
        SELECT id, title, description, level, duration_min, exercises
        FROM workouts
        WHERE id = %s
    """
    rows, _ = SelectSQL(sql, db="iSlim", values=(workout_id,))
    if not rows:
        return None

    return dict(zip(
        ["id", "title", "description", "level", "duration_min", "exercises"],
        rows[0]
    ))

def getUserDuration(user_id):
    if not user_id:
        return 0

    sql = "SELECT created_at FROM users WHERE id = %s"
    rows, _ = SelectSQL(sql, db="iSlim", values=(user_id,))
    
    if not rows:
        return 0

    return rows[0][0] if rows[0][0] is not None else 0

from datetime import datetime, timedelta
import math


def calculate_age_components(user_id):
    created_timestamp = getUserDuration(user_id)
    
    if not isinstance(created_timestamp, datetime):
        if isinstance(created_timestamp, (int, float)):
            created_timestamp = datetime.fromtimestamp(created_timestamp)
        # Add more parsing for string types if needed, e.g.:
        # elif isinstance(created_timestamp, str):
        #     created_timestamp = datetime.strptime(created_timestamp, '%Y-%m-%d %H:%M:%S')
        else:
            print("Warning: created_timestamp is not a datetime object or a recognized format. Returning zeros.")
            return {"years": 0, "months": 0, "weeks": 0, "days": 0, "hours": 0, "minutes": 0, "seconds": 0}

    now = datetime.now()
    
    # Calculate the total difference as a timedelta object
    delta = now - created_timestamp

    # Extract total days and remaining seconds from the timedelta
    total_days_raw = delta.days
    total_seconds_in_fractional_day = delta.seconds # This is seconds within the current day (0 to 86399)

    # --- Calculate components using timedelta properties ---

    # Start with total seconds and convert upwards for precision
    remaining_seconds = total_seconds_in_fractional_day + (total_days_raw * 24 * 3600)

    years = 0
    months = 0

    # For years and months, a direct timedelta conversion is problematic due to varying lengths.
    # We'll use a more iterative approach or approximations if precise calendar-based months/years are needed.
    # For a *breakdown* of time, we can still use average days.

    # Option 1: Iterative (more accurate for calendar months/years)
    # This requires more complex logic, as you have to check month by month,
    # or year by year, to subtract exactly that many days.
    # The `dateutil.relativedelta` library is excellent for this.
    
    # Option 2: Approximate (similar to previous approach, but based on total_seconds for hours/minutes/seconds)
    # This is what we will implement to fit the "weeks, days, hours" pattern more easily.

    # Calculate years (approximate)
    years = math.floor(total_days_raw / 365.25)
    remaining_days_after_years = total_days_raw - (years * 365.25) # Use remaining days from the raw delta.days

    # Calculate months (approximate)
    months = math.floor(remaining_days_after_years / 30.44)
    remaining_days_after_months = remaining_days_after_years - (months * 30.44)

    # Calculate weeks
    weeks = math.floor(remaining_days_after_months / 7)
    remaining_days_after_weeks = remaining_days_after_months - (weeks * 7)

    # Calculate remaining whole days
    days = math.floor(remaining_days_after_weeks)

    # Now, calculate hours, minutes, seconds from the remaining fractional part of the day
    # or directly from total_seconds_in_fractional_day
    
    # The `delta.seconds` gives us seconds within the current day.
    # The `delta.microseconds` can be used for even finer granularity.
    
    # Let's use the total seconds of the delta and work our way down for hours, minutes, seconds
    total_remaining_seconds_from_delta = delta.seconds + (delta.microseconds / 1_000_000)

    hours = math.floor(total_remaining_seconds_from_delta / 3600)
    remaining_seconds_after_hours = total_remaining_seconds_from_delta % 3600

    minutes = math.floor(remaining_seconds_after_hours / 60)
    seconds = math.floor(remaining_seconds_after_hours % 60) # Use floor for integer seconds

    return {
        "years": years,
        "months": months,
        "weeks": weeks,
        "days": days,
        "hours": hours
    }

import re

def process_video_rows(videoRows_initial):
    # Convert the outer container to a list if it's not already
    # This assumes videoRows_initial might be a tuple of tuples, or similar
    mutable_video_rows = []

    for vid_tuple in videoRows_initial: # vid_tuple will be (id, title, description)
        # Convert the current tuple to a list so you can modify it
        vid_list = list(vid_tuple)

        # Access the element you want to modify (index 2 for description)
        text = vid_list[2]

        # Apply your transformations
        text = text.replace(" - Made With Clipchamp", "")
        text = re.sub(r'\s*\(.*?\)', '', text).strip()

        # Assign the modified text back to the list element
        vid_list[2] = text

        # Convert the modified list back to a tuple and add to our new list
        mutable_video_rows.append(tuple(vid_list))

    return mutable_video_rows # The return type will now be a list of tuples

def getYogaVideobyWeek(week=None):
    try:
        sql = "SELECT * FROM video_series WHERE videoSequence = %s and main_category_id = 1"
        rows, _ = SelectSQL(sql, db="iSlim", values=(week,))

        if not rows:
            return None
        
        for row in rows:
            videoDesc = row[3].lower()
            sql = f"SELECT * FROM video_sections WHERE LOWER(section_title) LIKE '%{videoDesc}%'"
            videoRows, _ = SelectSQL(sql, db="iSlim")

            pass

        videoRows = process_video_rows(videoRows)

        return videoRows    

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    
def getYoga(user_id):
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

def getYogaVideosByUser(user_id):
    userDuration = calculate_age_components(user_id)
    videos = getYogaVideobyWeek(userDuration.get("weeks", 0))

    return videos

from ftpHandler import *

def getWorkoutVideosbyUser(user_id):

    userDuration = calculate_age_components(user_id)
    weeks = int(userDuration.get("weeks", -1))

    sql = "SELECT dataKey, dataValue FROM user_data WHERE userId = %s"
    rows, _ = SelectSQL(sql, db="iSlim", values=(user_id,))

    user_data = {row[0]: row[1] for row in rows}
    fitness_level = user_data.get("fitnessLevel", "").lower()
    goal = user_data.get("goal", "").lower()

    if weeks < 0:
        return []

    videos = get_videos_in_folder(level = fitness_level, goal = goal)

    # discordMsg(f"Videos: {len(videos)}", islim = True)

    return videos

def get_filtered_fitness_programs(fitness_level=None, goal=None, weekday=None, user_id=None):
    try:
        sql_programs = "SELECT * FROM fitness_programs"
        programs, _ = SelectSQL(sql_programs, db="iSlim")

        program_list = []
        for p in programs:
            program_id, name, description = p[0], p[1], p[2]

            sql_levels = "SELECT * FROM fitness_levels WHERE program_id = %s"
            levels, _ = SelectSQL(sql_levels, db="iSlim", values=(program_id,))

            level_list = []
            for l in levels:
                level_id, level_name, sessions_per_week = l[0], l[2], l[3]

                if fitness_level and fitness_level not in level_name.lower():
                    continue

                sql_workouts = "SELECT * FROM fitness_workouts WHERE level_id = %s"
                workouts, _ = SelectSQL(sql_workouts, db="iSlim", values=(level_id,))

                workout_list = []
                for w in workouts:
                    workout_id, day_of_week, workout_name, desc = w[0], w[2], w[3], w[4]

                    if goal and goal not in (workout_name.lower() + (desc or "").lower()):
                        continue
                    if weekday and weekday.lower() != day_of_week.lower():
                        continue

                    sql_ex = "SELECT * FROM fitness_exercises WHERE workout_id = %s"
                    exercises, _ = SelectSQL(sql_ex, db="iSlim", values=(workout_id,))

                    exercise_list = [
                        {
                            "id": ex[0],
                            "type": ex[2],
                            "name": ex[3],
                            "sets": ex[4],
                            "reps": ex[5],
                            "durationSeconds": ex[6],
                            "notes": ex[7],
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

                if workout_list:
                    level_list.append({
                        "id": level_id,
                        "name": level_name,
                        "sessionsPerWeek": sessions_per_week,
                        "workouts": workout_list
                    })

            if level_list:
                workoutVideos = getWorkoutVideosbyUser(user_id)
                program_list.append({
                    "id": program_id,
                    "name": name,
                    "description": description,
                    "levels": level_list,
                    "videos": workoutVideos
                })

        return jsonify(program_list), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def send_email_verification(to_email, code):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    smtp_user = "flutschich@gmail.com"
    smtp_password = "rjmr vocv qhgu anec"  # <-- Gmail App Password

    subject = "Your Verification Code"
    html_body = f"""
    <html>
    <body>
        <h2>Your Verification Code</h2>
        <p>Here is your code: <b>{code}</b></p>
        <p>This code will expire in 1 minute.</p>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


if "__main__" == __name__:
    yogaVideos = getYogaVideosByUser(19)
