import base64
import json
import math
import os
import pickle
import re
import secrets
import socket
import sys
import threading
import time
import warnings
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import requests
from flask import Flask, Response, g, has_request_context, jsonify, request
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "2")
# A wireless IP camera loses packets now and then. FFmpeg prints a line per
# damaged macroblock and recovers by itself, so keep only fatal messages.
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "8")

warnings.filterwarnings(
    "ignore",
    message=".*SymbolDatabase.GetPrototype.*",
)

try:
    import mediapipe as mp
except ImportError:
    mp = None


# =========================
# PATH CONFIG
# =========================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REL_DIR = DATA_DIR / "relatives"

RELATIVES_JSON = DATA_DIR / "relatives.json"
SCHEDULES_JSON = DATA_DIR / "schedules.json"
LOGS_JSON = DATA_DIR / "logs.json"
VITALS_JSON = DATA_DIR / "vitals_log.json"
USERS_JSON = DATA_DIR / "users.json"
SESSIONS_JSON = DATA_DIR / "sessions.json"
CARE_ALERTS_JSON = DATA_DIR / "care_alerts.json"
SPEECH_NOTES_JSON = DATA_DIR / "speech_notes.json"
TELEGRAM_CONFIG_JSON = DATA_DIR / "telegram_config.json"
GEOFENCES_JSON = DATA_DIR / "geofences.json"
PUBLIC_URL_JSON = DATA_DIR / "public_url.json"
TRACK_LOG_JSON = DATA_DIR / "track_log.json"
PKL_PATH = DATA_DIR / "face_db.pkl"
LBPH_PATH = DATA_DIR / "face_lbph.yml"
MODEL_DIR = BASE_DIR / "models"
YUNET_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODEL_DIR / "face_recognition_sface_2021dec_int8.onnx"

DATA_DIR.mkdir(parents=True, exist_ok=True)
REL_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# APP CONFIG
# =========================
app = Flask(__name__)
CORS(app)

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
CAMERA_BACKEND = os.getenv("CAMERA_BACKEND", "auto").lower()
CAMERA_RTSP_URL = os.getenv("CAMERA_RTSP_URL", "").strip()
STREAM_PREFIXES = ("rtsp://", "rtsps://", "http://", "https://")
STREAM_MAX_WIDTH = int(os.getenv("STREAM_MAX_WIDTH", "960"))
GESTURE_ZOOM_FACE_RATIO = float(os.getenv("GESTURE_ZOOM_FACE_RATIO", "0.22"))
GESTURE_ZOOM_SPAN = float(os.getenv("GESTURE_ZOOM_SPAN", "8.0"))
FINGER_STRAIGHT_DEGREES = float(os.getenv("FINGER_STRAIGHT_DEGREES", "145"))
THUMB_STRAIGHT_DEGREES = float(os.getenv("THUMB_STRAIGHT_DEGREES", "150"))
# Help is an emergency, so it has to be held longer than a driving command.
GESTURE_HOLD_PASSES = {"help": 5}
GESTURE_HOLD_DEFAULT = 2
CAMERA_TARGET_FPS = int(os.getenv("CAMERA_TARGET_FPS", "30"))
ANALYSIS_TARGET_FPS = int(os.getenv("ANALYSIS_TARGET_FPS", "15"))

# RTSP over UDP drops packets on Wi-Fi, so ask FFmpeg for TCP with a timeout.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;8000000|max_delay;500000",
)
PATIENT_NAME = os.getenv("PATIENT_NAME", "Patient")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS_RAW = os.getenv("TELEGRAM_CHAT_IDS", os.getenv("TELEGRAM_CHAT_ID", ""))
FIREBASE_API_KEY = os.getenv(
    "FIREBASE_API_KEY",
    "AIzaSyA4IYnykwpovqOJWzfBd7abVdAma_Ig3Q",
)
FIREBASE_DATABASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://diet-planner-3bdf3-default-rtdb.firebaseio.com",
).rstrip("/")
FIREBASE_PATIENT_PATH = os.getenv("FIREBASE_PATIENT_PATH", "ALZHEIMER_PATIENTS").strip("/")
# The live phone position and the caretaker position are kept in their own
# nodes as well, so the hardware can read one small record instead of the whole
# patient node.
FIREBASE_TRACK_PATH = os.getenv("FIREBASE_TRACK_PATH", "PATIENT_TRACKING").strip("/")
FIREBASE_CARETAKER_PATH = os.getenv(
    "FIREBASE_CARETAKER_PATH",
    "CARETAKER_LOCATION",
).strip("/")

# =========================
# TRACKING, GEOFENCE, MOTION
# =========================
# The phone tracker link has to open on the patient's phone, so it points at
# this machine on the LAN rather than at localhost.
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "5173")
# A browser hands out GPS only on a secure origin, and a plain http:// LAN
# address is not one, so the link has to be https as soon as the dev
# certificate exists. FRONTEND_SCHEME overrides the guess.
DEV_CERT_PATH = BASE_DIR.parent / "certs" / "dev-cert.pem"
FRONTEND_SCHEME = os.getenv("FRONTEND_SCHEME", "").strip().lower()

DEFAULT_GEOFENCE_RADIUS = float(os.getenv("GEOFENCE_RADIUS_METERS", "150"))
# A GPS fix jitters by a few metres, so leaving needs a little more than the
# radius and coming back needs a little less. Without it a patient standing on
# the fence line would raise an alert every few seconds.
GEOFENCE_EXIT_BUFFER = float(os.getenv("GEOFENCE_EXIT_BUFFER_METERS", "25"))
GEOFENCE_REPEAT_SECONDS = int(os.getenv("GEOFENCE_REPEAT_SECONDS", "300"))
TRACK_TELEGRAM_SECONDS = int(os.getenv("TRACK_TELEGRAM_SECONDS", "300"))
TRACK_LOG_LIMIT = int(os.getenv("TRACK_LOG_LIMIT", "500"))
# How often the safe zone is re-checked from the last known position, and
# how quiet a phone has to go before that silence is itself worth an alert.
GEOFENCE_WATCHDOG_SECONDS = int(os.getenv("GEOFENCE_WATCHDOG_SECONDS", "30"))
TRACK_STALE_SECONDS = int(os.getenv("TRACK_STALE_SECONDS", "300"))

# MPU6050 readings arrive as raw Ax, Ay, Az numbers whose scale depends on how
# the sketch configured the sensor, so the checks below work on the magnitude
# and on the change between samples. Both are unit independent; only the
# numbers in these variables have to be tuned for a different sketch.
MOTION_IMPACT_LEVEL = float(os.getenv("MOTION_IMPACT_LEVEL", "160"))
MOTION_FREEFALL_LEVEL = float(os.getenv("MOTION_FREEFALL_LEVEL", "15"))
MOTION_JERK_LEVEL = float(os.getenv("MOTION_JERK_LEVEL", "45"))
MOTION_SHAKE_LEVEL = float(os.getenv("MOTION_SHAKE_LEVEL", "28"))
MOTION_STILL_LEVEL = float(os.getenv("MOTION_STILL_LEVEL", "4"))
MOTION_STILL_SECONDS = int(os.getenv("MOTION_STILL_SECONDS", "900"))

# SMS and the voice call are placed by the GSM module that already watches the
# Firebase node. Filling the Twilio variables adds a cloud fallback for when the
# module is offline.
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
ALERT_SMS_NUMBERS = os.getenv("ALERT_SMS_NUMBERS", "").strip()

# Firebase and Telegram both drop idle keep-alive connections, which surface
# as RemoteDisconnected or "connection forcibly closed" on the next write. One
# session with retries reuses a live connection and replays those failures.
http_session = requests.Session()
http_session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.4,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "PATCH", "PUT", "POST"]),
        ),
    ),
)


# =========================
# LIVE STATE
# =========================
state = {
    "bot": {
        "location": "Living Room",
        "currentLocation": None,
        "followMe": False,
        "lastInteraction": "Not started",
        "recognizedPerson": "Unknown",
        "recognizedName": "Unknown",
        "recognizedRelation": "Not saved",
        "emotion": "neutral",
        "emotionConfidence": 0,
        "gesture": "none",
        "gestureConfidence": 0,
        "emotionStatus": "Waiting for camera",
        "gestureStatus": "Waiting for camera",
        "gestureEngine": "MediaPipe" if mp is not None else "OpenCV fallback",
        "emotionEngine": "MediaPipe face mesh" if mp is not None else "OpenCV",
        "cameraStatus": "Stopped",
        "cameraIndex": CAMERA_INDEX,
        "cameraType": "webcam",
        "cameraSource": f"Device {CAMERA_INDEX}",
        "cameraError": "",
        "cameraFps": 0,
        "streamFps": 0,
        "detectionFps": 0,
        "trainedFaceSamples": 0,
        "faceMatchConfidence": 0,
        "analysisMs": 0,
        "runtime": {
            "python": sys.executable,
            "opencv": cv2.__version__,
            "opencvFace": hasattr(cv2, "face"),
            "mediapipe": mp is not None,
        },
    },
    "vitals": {
        "bp": "0/0",
        "heartRate": 76,
        "spo2": 98,
        "temperature": 36.7,
        "obstacle": 0,
        "activity": "normal",
        "direction": "S",
        "ax": 0,
        "ay": 0,
        "az": 0,
        "motion": {"ax": 0, "ay": 0, "az": 0, "magnitude": 0, "status": "no sensor"},
        "source": "local",
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    },
    "alerts": [],
    "camera_running": False,
    "activePatientId": None,
    "tracking": {
        "location": None,
        "source": "none",
        "fence": None,
        "distance": None,
        "inside": None,
        "updatedAt": None,
        "caretakerLocation": None,
    },
}

last_frame = None
last_raw_frame = None
last_frame_lock = threading.Lock()
last_frame_ready = threading.Condition(last_frame_lock)
last_frame_version = 0
last_help_alert_at = 0.0
gesture_zoom_misses = 0
gesture_use_zoom = True
gesture_candidate = "none"
gesture_candidate_count = 0
gesture_miss_count = 0
recognition_candidate = None
recognition_candidate_count = 0
recognition_miss_count = 0
last_announced_identity = None
last_identity_announcement_at = 0.0
mp_hands = None
mp_face_mesh = None
mp_init_lock = threading.Lock()
mp_hands_lock = threading.RLock()
mp_face_lock = threading.RLock()
deepface_available = None
expression_history = deque(maxlen=5)
lbph_recognizer_cache = None
yunet_detector = None
sface_recognizer = None
sface_lock = threading.RLock()
last_movement_at = time.time()
last_temperature_by_patient = {}
distress_help_events = deque(maxlen=10)
automatic_alert_cooldowns = {}
last_firebase_sync_at = 0.0
last_vitals_log_at = 0.0
last_vitals_snapshot = None
last_gesture_direction = ""
last_gesture_direction_at = 0.0
geofence_state_by_patient = {}
last_track_telegram_at = {}
last_motion_reading = {}
last_motion_move_at = {}

DISTRESSED_EMOTIONS = {"sad", "angry", "confused", "fear", "disgust"}
NO_MOVEMENT_SECONDS = int(os.getenv("NO_MOVEMENT_SECONDS", "300"))


# =========================
# HARD CODED CHATBOT Q&A
# =========================
patient_qa = {
    "who am i": f"You are {PATIENT_NAME}. I am your companion care bot.",
    "where am i": "You are at home. You are safe.",
    "medicine": "Take only the medicine shown in your schedule or given by your caregiver. If you are unsure, please ask your caregiver before taking it.",
    "help": "I have notified your caregiver. Please stay calm.",
    "water": "Please drink a glass of water slowly.",
    "family": "I can recognize your saved family members and tell you their relationship.",
    "food": "Your caregiver has added your food routine in the dashboard.",
    "doctor": "Your doctor visit details can be added in the routine schedule.",
    "sleep": "Please take rest. I will remind your caregiver if needed.",
    "confused": "You are safe at home. Take a slow breath, stay where you are, and ask me to contact your caregiver.",
    "scared": "You are not alone. Take a slow breath and sit somewhere comfortable while I help you contact your caregiver.",
    "happy thought": "You are cared for, and your family is thinking about you. A calm moment with familiar music can be a lovely start.",
    "what day": "You can check today's date and your routine with your caregiver on the dashboard.",
    "what time": "Please check the clock on this device. Your scheduled activities are listed in the Schedule section.",
    "exercise": "A short, gentle walk can be helpful when your caregiver says it is safe.",
    "blood pressure": "Your blood pressure is shown on the dashboard from the Firebase BP value.",
    "bp": "Your blood pressure is shown on the dashboard from the Firebase BP value.",
    "oxygen": "Your SpO2 oxygen level is shown on the dashboard. If it is low, I will alert your family.",
    "heart rate": "Your heart rate is shown on the dashboard. If it becomes too high or too low, I will alert your family.",
    "temperature": "Your body temperature is shown on the dashboard. If fever is detected, I will alert your family.",
    "follow me": "Say follow me and I send the F direction to the bot.",
    "stop bot": "Say stop and I send the S direction to the bot.",
    "call family": "I can send a help alert to all saved Telegram chat ids.",
    "emergency": "I have notified your caregiver. Please sit safely and wait for help.",
    "music": "I can play calming music for you. Say play music, and pick a track from the Calming Music player on the dashboard.",
    "play music": "Starting calming music. Sit back and breathe slowly.",
    "sad": "I am sorry you feel low. I will play some calming music, and your caregiver can see how you are doing.",
    "lonely": "You are not alone. I am here with you, and I can play gentle music while we wait for your family.",
    "safe zone": "Your caregiver set a safe area around your home. If you walk out of it, I tell them straight away and send your location.",
    "lost": "Stay where you are. I have your location and I am sending it to your caregiver right now.",
    "where is my caregiver": "Your caregiver's location is shared with the dashboard. I can call them for you.",
    "track my phone": "Open the tracking link your caregiver sent you and keep it open. It shares your location so your family can find you.",
}

family_qa = {
    "vitals": "The dashboard shows heart rate, SpO2, body temperature, and activity status.",
    "add a relative": "Go to the Relatives section, enter name and relationship, capture image, then train the face model.",
    "add relative": "Go to the Relatives section, enter name and relationship, capture image, then train the face model.",
    "telegram": "Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS in backend environment variables. Use commas for family and doctor chat ids.",
    "medicine": "Use the Schedule section to add medicine name, dose, and time.",
    "emergency": "Abnormal vitals, help gesture, missed routine, or low SpO2 can trigger emergency alerts.",
    "face recognition": "Saved relative images are converted into face_db.pkl and used for live camera matching.",
    "emotion": "The camera uses DeepFace when installed. Otherwise, the OpenCV fallback reports happy when it detects a smile, neutral when it sees a face, and unknown while waiting for a face.",
    "gesture": "Hold one hand up facing the camera and show a number of fingers: a closed fist stops the robot, one finger brings it forward, two fingers send it left, three fingers send it right, and four fingers with the thumb tucked in send it backward. An open palm with the thumb out is the help alert, and it has to be held a little longer. On an IP camera stand where your face is visible, because the hand is searched for around the person.",
    "keep the patient calm": "Use a calm voice, short sentences, familiar music, and one instruction at a time. Reduce noise and avoid arguing about mistaken memories.",
    "patient calm": "Use a calm voice, short sentences, familiar music, and one instruction at a time. Reduce noise and avoid arguing about mistaken memories.",
    "reminder": "Add medicines and routines in the Schedule section with a title, dose, and time.",
    "confused": "Reassure the patient that they are safe, use simple orientation cues, and check for pain, hunger, thirst, fatigue, or a sudden medical change.",
    "dashboard offline": "Start the Flask backend on port 5000 and the Vite frontend. During development, Vite proxies all /api requests to Flask.",
    "camera": "Use Start Camera on the dashboard. Pick Laptop / USB webcam for a local device, or IP camera (RTSP) and paste a URL such as rtsp://user:password@192.168.1.57:554/stream. If it fails, check camera permission, the CAMERA_INDEX setting, or the RTSP user name, password and network.",
    "logs": "The Alerts and Event Logs panel records chatbot use, commands, recognition events, schedules, and emergency alerts.",
    "firebase": "The dashboard reads BP, HR, Spo2, Temp, and direction from the ALZHEIMER_PATIENTS Firebase Realtime Database path.",
    "direction": "The joystick writes F, B, L, R, or S into Firebase direction. Saying or typing follow me, go left, go right, go back, or stop in the chat sends the same values, and so do the hand gestures.",
    "joystick": "Use the dashboard joystick to send Forward, Backward, Left, Right, or Stop to Firebase.",
    "doctor": "Put the family and doctor Telegram chat ids in TELEGRAM_CHAT_IDS separated by commas so alerts go to everyone.",
    "high heart rate": "Heart rate above 110 BPM triggers a high heart rate alert.",
    "low heart rate": "Heart rate below 45 BPM triggers a low heart rate alert.",
    "low spo2": "SpO2 below 92% triggers a low oxygen alert.",
    "fever": "Temperature of 38 deg C or higher triggers a fever alert.",
    "geofence": "Open a patient card on the caregiver dashboard, press Use my location or type a latitude and longitude, set the radius in metres, and save. Leaving that circle writes Emergency 1 with the patient location into Firebase and sends Telegram, SMS and a call.",
    "safe zone": "The safe zone is the geofence circle you set for the patient. Distance is measured from its centre, and a small buffer stops GPS jitter from raising repeated alerts.",
    "tracking link": "On the patient dashboard, open Phone Tracking and share the link. The patient opens it on their phone, allows location, and every position goes to Firebase and Telegram.",
    "track": "The tracking link opens a phone page that sends live location to the backend. It appears on the caregiver map and in Firebase under Latitude and Longitude.",
    "sms": "Emergencies write SmsMessage, SmsNumbers, SmsStatus and CallStatus into Firebase for the GSM module. Adding TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER also sends the SMS and places the call from the cloud.",
    "call": "The emergency number saved in the patient profile is called. The GSM module reads CallStatus Pending from Firebase, and Twilio is the cloud fallback.",
    "motion": "Ax, Ay and Az from the MPU6050 are read from Firebase. A large force or a sudden jump raises a fall emergency, a near zero force raises free fall, and a long still period raises a no movement warning.",
    "fall": "A fall is detected when the motion magnitude passes MOTION_IMPACT_LEVEL or jumps by more than MOTION_JERK_LEVEL between two Firebase reads.",
    "caretaker location": "Press Share my location on the caregiver dashboard. It stores CaretakerLatitude and CaretakerLongitude in Firebase and shows the distance to each patient.",
    "music": "The Calming Music player on the patient dashboard has four royalty free tracks. It starts on its own when the camera reports a sad or distressed mood.",
}


# =========================
# JSON FILE DATABASE
# =========================
def ensure_json_file(path, default_value):
    if not path.exists():
        path.write_text(json.dumps(default_value, indent=2), encoding="utf-8")


def init_storage():
    ensure_json_file(RELATIVES_JSON, [])
    ensure_json_file(SCHEDULES_JSON, [])
    ensure_json_file(LOGS_JSON, [])
    ensure_json_file(VITALS_JSON, [])
    ensure_json_file(USERS_JSON, [])
    ensure_json_file(SESSIONS_JSON, [])
    ensure_json_file(CARE_ALERTS_JSON, [])
    ensure_json_file(SPEECH_NOTES_JSON, [])
    ensure_json_file(GEOFENCES_JSON, [])
    ensure_json_file(TRACK_LOG_JSON, [])
    ensure_json_file(TELEGRAM_CONFIG_JSON, {
        "botToken": "",
        "chatIds": [],
    })
    ensure_demo_users()


def ensure_demo_users():
    users = read_json(USERS_JSON, [])
    demo_accounts = [
        {
            "name": "Dr. Priya Sharma",
            "email": "priya.demo@carebot.local",
            "role": "caregiver",
            "profile": {"phone": "90000 10001", "speciality": "Neurology"},
        },
        {
            "name": "Nurse Arun Kumar",
            "email": "arun.demo@carebot.local",
            "role": "caregiver",
            "profile": {"phone": "90000 10002", "speciality": "Home Care"},
        },
        {
            "name": "Meera Nair",
            "email": "meera.demo@carebot.local",
            "role": "caregiver",
            "profile": {"phone": "90000 10003", "speciality": "Family Caregiver"},
        },
        {
            "name": "Ramesh",
            "email": "ramesh.demo@carebot.local",
            "role": "patient",
            "profile": {
                "patientName": "Ramesh",
                "age": "72",
                "disease": "Alzheimer disease",
                "medicalNotes": "Demo patient",
                "emergencyContact": "90000 20001",
            },
        },
        {
            "name": "Lakshmi",
            "email": "lakshmi.demo@carebot.local",
            "role": "patient",
            "profile": {
                "patientName": "Lakshmi",
                "age": "67",
                "disease": "Dementia",
                "medicalNotes": "Demo patient",
                "emergencyContact": "90000 20002",
            },
        },
    ]

    changed = False
    for account in demo_accounts:
        if find_user_by_email(users, account["email"]):
            continue
        user_id = next_id(users)
        user = {
            "id": user_id,
            "name": account["name"],
            "email": account["email"],
            "password_hash": generate_password_hash("demo123"),
            "role": account["role"],
            "profile": account["profile"],
            "demo": True,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        if account["role"] == "caregiver":
            user["patient_ids"] = []
        else:
            user.update({
                "link_code": secrets.token_hex(3).upper(),
                "caregiver_ids": [],
                "requested_caregiver_email": "",
            })
        users.append(user)
        changed = True

    if changed:
        write_json(USERS_JSON, users)


def read_json(path, default_value):
    try:
        ensure_json_file(path, default_value)
        # utf-8-sig, not utf-8: PowerShell writes a byte order mark, and the
        # tunnel script writes one of these files. Plain utf-8 would choke on
        # it and quietly hand back the default.
        with open(path, "r", encoding="utf-8-sig") as file:
            return json.load(file)
    except Exception:
        return default_value


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def next_id(items):
    if not items:
        return 1
    return max(int(item.get("id", 0)) for item in items) + 1


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        if default is None:
            return None
        return float(default)


def normalize_location(location):
    if not isinstance(location, dict):
        return None

    lat = safe_float(location.get("lat", location.get("latitude")), None)
    lng = safe_float(location.get("lng", location.get("longitude")), None)
    if lat is None or lng is None:
        return None
    if not -90 <= lat <= 90 or not -180 <= lng <= 180:
        return None

    return {
        "lat": lat,
        "lng": lng,
        "accuracy": safe_float(location.get("accuracy"), 0),
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }


def google_maps_link(location):
    if not location:
        return ""
    return f"https://www.google.com/maps?q={location['lat']:.6f},{location['lng']:.6f}"


def haversine_meters(first, second):
    """Distance in metres between two {lat, lng} points."""
    if not first or not second:
        return None
    earth_radius = 6371000.0
    lat1, lat2 = math.radians(first["lat"]), math.radians(second["lat"])
    delta_lat = lat2 - lat1
    delta_lng = math.radians(second["lng"] - first["lng"])
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    return 2 * earth_radius * math.asin(min(1.0, math.sqrt(a)))


def lan_ip_address():
    """The address of this machine on the Wi-Fi, for the phone tracker link."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # No packet is sent; connect() only picks the outgoing interface.
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
        finally:
            probe.close()
    except Exception:
        return "127.0.0.1"


def frontend_scheme():
    if FRONTEND_SCHEME in {"http", "https"}:
        return FRONTEND_SCHEME
    return "https" if DEV_CERT_PATH.exists() else "http"


def public_tunnel_origin():
    """The Cloudflare address, when scripts\start-tunnel.ps1 is running.

    A quick tunnel gets a fresh random name every run, so the script writes the
    current one here rather than baking it into a setting. It carries a real
    certificate, which is the only way a phone opens the tracker with no
    warning at all.
    """
    record = read_json(PUBLIC_URL_JSON, {})
    origin = str(record.get("url", "")).strip().rstrip("/")
    return origin if origin.startswith("https://") else ""


def tracker_link(token, host=None):
    """The link the patient opens. Naming a host forces that exact machine."""
    if host:
        origin = f"{frontend_scheme()}://{host}:{FRONTEND_PORT}"
    elif FRONTEND_ORIGIN:
        origin = FRONTEND_ORIGIN
    else:
        # A public tunnel beats the LAN address: it works away from the house
        # and its certificate is already trusted by every phone.
        origin = public_tunnel_origin() or (
            f"{frontend_scheme()}://{lan_ip_address()}:{FRONTEND_PORT}"
        )
    return f"{origin}/?panel=tracker&token={token}"


def ensure_track_token(users, patient):
    """Give the patient a permanent token for the phone tracker link."""
    if not patient.get("track_token"):
        patient["track_token"] = secrets.token_urlsafe(9)
        write_json(USERS_JSON, users)
    return patient["track_token"]


def find_user_by_track_token(token):
    clean_token = str(token or "").strip()
    if not clean_token:
        return None
    users = read_json(USERS_JSON, [])
    return next(
        (
            user
            for user in users
            if user.get("role") == "patient"
            and secrets.compare_digest(str(user.get("track_token", "")), clean_token)
        ),
        None,
    )


# =========================
# GEOFENCE STORAGE
# =========================
def normalize_geofence(fence):
    if not isinstance(fence, dict):
        return None
    center = normalize_location(fence)
    if center is None:
        return None
    radius = safe_float(fence.get("radius"), DEFAULT_GEOFENCE_RADIUS)
    return {
        "lat": center["lat"],
        "lng": center["lng"],
        "radius": max(30.0, min(20000.0, radius)),
        "label": str(fence.get("label", "")).strip() or "Safe zone",
    }


def geofence_for_patient(patient_id):
    if not patient_id:
        return None
    return next(
        (
            item
            for item in read_json(GEOFENCES_JSON, [])
            if int(item.get("patient_id", 0)) == int(patient_id)
        ),
        None,
    )


def save_geofence(patient_id, fence, caregiver=None):
    """Store the safe zone the caretaker drew around the patient."""
    normalized = normalize_geofence(fence)
    if normalized is None:
        return None

    fences = [
        item
        for item in read_json(GEOFENCES_JSON, [])
        if int(item.get("patient_id", 0)) != int(patient_id)
    ]
    record = {
        "patient_id": int(patient_id),
        "caregiver_id": int(caregiver["id"]) if caregiver else None,
        "caregiverName": caregiver.get("name", "") if caregiver else "",
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        **normalized,
    }
    fences.append(record)
    write_json(GEOFENCES_JSON, fences)
    geofence_state_by_patient.pop(int(patient_id), None)
    write_firebase_geofence(record)
    return record


def geofence_status(patient_id, location):
    """Where the patient is relative to the safe zone their caretaker set."""
    fence = geofence_for_patient(patient_id)
    if fence is None or location is None:
        return {"fence": fence, "distance": None, "inside": None, "breached": False}

    distance = haversine_meters(fence, location)
    previous = geofence_state_by_patient.get(int(patient_id), {})
    was_outside = bool(previous.get("outside"))
    # Hysteresis: a GPS fix jitters, so leaving needs radius + buffer while
    # coming back needs the radius alone. Otherwise a patient standing on the
    # fence line would raise an alert every few seconds.
    threshold = fence["radius"] if was_outside else fence["radius"] + GEOFENCE_EXIT_BUFFER
    outside = distance > threshold

    now = time.time()
    breached = outside and (
        not was_outside
        or now - float(previous.get("alertedAt", 0)) >= GEOFENCE_REPEAT_SECONDS
    )
    returned = was_outside and not outside
    geofence_state_by_patient[int(patient_id)] = {
        "outside": outside,
        "alertedAt": now if breached else previous.get("alertedAt", 0),
    }

    return {
        "fence": fence,
        "distance": round(distance, 1),
        "inside": not outside,
        "breached": breached,
        "returned": returned,
    }


# =========================
# FIREBASE LOCATION WRITES
# =========================
def firebase_url(*segments):
    joined = "/".join(
        str(part).strip("/") for part in segments if str(part).strip("/")
    )
    return f"{FIREBASE_DATABASE_URL}/{joined}.json"


def firebase_patch(url, payload, problem_key):
    try:
        response = http_session.patch(url, json=payload, timeout=4)
        response.raise_for_status()
        return True
    except Exception as error:
        log_repeated_problem(
            problem_key,
            f"Firebase write failed ({problem_key}): {error}",
        )
        return False


def write_firebase_location(patient_id, location, source="phone", fence_state=None):
    """Push the live phone position into Firebase for the bot and the hardware."""
    if not location:
        return False

    payload = {
        "Latitude": location["lat"],
        "Longitude": location["lng"],
        "LocationAccuracy": location.get("accuracy", 0),
        "LocationSource": source,
        "LocationUpdatedAt": location.get("updatedAt", ""),
        "MapLink": google_maps_link(location),
    }
    if fence_state and fence_state.get("fence"):
        payload.update({
            "FenceLatitude": fence_state["fence"]["lat"],
            "FenceLongitude": fence_state["fence"]["lng"],
            "FenceRadius": fence_state["fence"]["radius"],
            "FenceLabel": fence_state["fence"]["label"],
            "FenceDistance": fence_state.get("distance", 0),
            "FenceStatus": "inside" if fence_state.get("inside") else "outside",
        })

    written = firebase_patch(firebase_node_url(), payload, "firebase-location")
    if patient_id:
        firebase_patch(
            firebase_url(FIREBASE_TRACK_PATH, patient_id),
            {"PatientId": int(patient_id), **payload},
            "firebase-track",
        )
    return written


def write_firebase_geofence(fence):
    payload = {
        "FenceLatitude": fence["lat"],
        "FenceLongitude": fence["lng"],
        "FenceRadius": fence["radius"],
        "FenceLabel": fence["label"],
        "FenceSetBy": fence.get("caregiverName", ""),
        "FenceUpdatedAt": fence.get("updatedAt", ""),
    }
    firebase_patch(firebase_node_url(), payload, "firebase-geofence")
    firebase_patch(
        firebase_url(FIREBASE_TRACK_PATH, fence["patient_id"]),
        payload,
        "firebase-geofence-track",
    )


def write_firebase_caretaker_location(caregiver, location, patient_ids=()):
    """Store where the caretaker is, next to the patients they look after."""
    payload = {
        "CaretakerId": int(caregiver["id"]),
        "CaretakerName": caregiver.get("name", ""),
        "CaretakerPhone": caregiver.get("profile", {}).get("phone", ""),
        "CaretakerLatitude": location["lat"],
        "CaretakerLongitude": location["lng"],
        "CaretakerAccuracy": location.get("accuracy", 0),
        "CaretakerUpdatedAt": location.get("updatedAt", ""),
        "CaretakerMapLink": google_maps_link(location),
    }
    written = firebase_patch(
        firebase_url(FIREBASE_CARETAKER_PATH, caregiver["id"]),
        payload,
        "firebase-caretaker",
    )
    firebase_patch(firebase_node_url(), payload, "firebase-caretaker-patient")
    for patient_id in patient_ids:
        firebase_patch(
            firebase_url(FIREBASE_TRACK_PATH, patient_id),
            payload,
            "firebase-caretaker-track",
        )
    state["tracking"]["caretakerLocation"] = {
        **location,
        "name": caregiver.get("name", ""),
    }
    return written


def current_patient_profile(patient_id=None):
    patient_id = patient_id or current_patient_id()
    users = read_json(USERS_JSON, [])
    patient = find_user(users, patient_id) if patient_id else None
    if not patient:
        return {}
    return patient.get("profile", {})


def build_sms_text(patient_name, condition, location, emergency_number=""):
    """One short line the GSM module or Twilio can send as an SMS."""
    parts = [f"CareBot emergency: {patient_name}.", str(condition).replace("\n", " ")]
    map_link = google_maps_link(location)
    if map_link:
        parts.append(f"Location: {map_link}")
    if emergency_number:
        parts.append(f"Contact: {emergency_number}")
    return " ".join(part for part in parts if part)[:300]


def write_firebase_emergency(patient_id, condition, location=None, reason=""):
    profile = current_patient_profile(patient_id)
    alert_location = normalize_location(location) or state["bot"].get("currentLocation") or {}
    emergency_number = (
        profile.get("emergencyNumber")
        or profile.get("emergencyContact")
        or ""
    )
    patient_name = profile.get("patientName") or PATIENT_NAME or "Patient"
    location_address = profile.get("locationAddress") or ""
    event_id = f"EMG_{int(time.time() * 1000)}"

    payload = {
        "Emergency": 1,
        "EmergencyEventId": event_id,
        "EmergencyNumber": emergency_number,
        "PatientName": patient_name,
        "PatientCondition": condition,
        "Latitude": alert_location.get("lat", 0),
        "Longitude": alert_location.get("lng", 0),
        "LocationAddress": location_address,
        "MapLink": google_maps_link(alert_location),
        "AlertReason": reason or "manual",
        # The GSM module watches CallStatus and SmsStatus and clears them once
        # the call is placed and the message is sent.
        "CallStatus": "Pending",
        "SmsStatus": "Pending",
        "SmsNumbers": ",".join(alert_sms_numbers(emergency_number)),
        "SmsMessage": build_sms_text(
            patient_name,
            condition,
            alert_location,
            emergency_number,
        ),
        "Handled": False,
    }

    try:
        response = http_session.patch(firebase_node_url(), json=payload, timeout=4)
        response.raise_for_status()
    except Exception as error:
        log_repeated_problem("firebase-emergency", f"Firebase emergency write failed: {error}")
        return None

    return payload


def parse_chat_ids(value):
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value or "").replace(";", ",").replace("\n", ",").split(",")
    return [str(item).strip() for item in raw_items if str(item).strip()]


def telegram_config():
    config = read_json(TELEGRAM_CONFIG_JSON, {})
    token = TELEGRAM_BOT_TOKEN or str(config.get("botToken", "")).strip()
    chat_ids = parse_chat_ids(TELEGRAM_CHAT_IDS_RAW) or parse_chat_ids(
        config.get("chatIds", []),
    )
    return token, chat_ids


def telegram_status():
    token, chat_ids = telegram_config()
    return {
        "hasToken": bool(token),
        "chatCount": len(chat_ids),
        "chatIds": chat_ids,
        "configFile": str(TELEGRAM_CONFIG_JSON),
    }


def firebase_node_url():
    return f"{FIREBASE_DATABASE_URL}/{FIREBASE_PATIENT_PATH}.json"


def infer_activity(vitals_data):
    explicit_activity = str(vitals_data.get("activity", "")).strip()
    if explicit_activity:
        return explicit_activity

    direction = str(vitals_data.get("direction", "S")).upper()[:1]
    direction_activity = {
        "F": "moving forward",
        "B": "moving backward",
        "L": "turning left",
        "R": "turning right",
        "S": "stopped",
    }

    if (
        safe_int(vitals_data.get("heartRate"), 0) <= 0
        and safe_int(vitals_data.get("spo2"), 0) <= 0
        and safe_float(vitals_data.get("temperature"), 0) <= 0
    ):
        return "waiting for sensor data"

    return direction_activity.get(direction, "live from firebase")


def normalize_firebase_vitals(data):
    data = data or {}
    normalized = {
        "bp": str(data.get("BP", data.get("bp", state["vitals"].get("bp", "0/0")))),
        "heartRate": safe_int(
            data.get("HR", data.get("heartRate", data.get("hr"))),
            state["vitals"]["heartRate"],
        ),
        "spo2": safe_int(
            data.get("Spo2", data.get("SpO2", data.get("spo2"))),
            state["vitals"]["spo2"],
        ),
        "temperature": safe_float(
            data.get("Temp", data.get("temperature", data.get("temp"))),
            state["vitals"]["temperature"],
        ),
        "obstacle": safe_int(
            data.get("Obstacle", data.get("obstacle")),
            state["vitals"].get("obstacle", 0),
        ),
        "direction": str(
            data.get("direction", state["vitals"].get("direction", "S"))
        ).upper()[:1] or "S",
        "ax": safe_float(data.get("Ax", data.get("ax")), 0),
        "ay": safe_float(data.get("Ay", data.get("ay")), 0),
        "az": safe_float(data.get("Az", data.get("az")), 0),
    }
    normalized["motion"] = motion_from_vitals(normalized)
    if normalized["obstacle"] == 1:
        normalized["direction"] = "S"
    normalized["activity"] = infer_activity({
        **normalized,
        "activity": data.get("activity", data.get("Activity", "")),
    })
    return normalized


def write_vitals_history(patient_id, vitals_data):
    global last_vitals_log_at
    global last_vitals_snapshot

    snapshot = (
        vitals_data.get("bp"),
        vitals_data.get("heartRate"),
        vitals_data.get("spo2"),
        vitals_data.get("temperature"),
        vitals_data.get("obstacle"),
        vitals_data.get("direction"),
    )
    now = time.time()
    if snapshot == last_vitals_snapshot and now - last_vitals_log_at < 15:
        return

    vitals_log = read_json(VITALS_JSON, [])
    vitals_log.insert(0, {
        "id": next_id(vitals_log),
        "patient_id": int(patient_id),
        "bp": vitals_data.get("bp", "0/0"),
        "heartRate": vitals_data["heartRate"],
        "spo2": vitals_data["spo2"],
        "temperature": vitals_data["temperature"],
        "obstacle": vitals_data.get("obstacle", 0),
        "direction": vitals_data.get("direction", "S"),
        "activity": vitals_data.get("activity", state["vitals"]["activity"]),
        "created_at": vitals_data["updatedAt"],
    })
    write_json(VITALS_JSON, vitals_log[:200])
    last_vitals_snapshot = snapshot
    last_vitals_log_at = now


# =========================
# PHONE TRACKING + GEOFENCE ALERTS
# =========================
def record_track_point(patient, location, source="phone"):
    """Handle one position from the patient's phone.

    Every point is stored, mirrored into Firebase, and measured against the
    safe zone the caretaker chose. Leaving that zone raises a full emergency.
    """
    normalized = normalize_location(location)
    if normalized is None:
        return None

    patient_id = int(patient["id"])
    state["bot"]["currentLocation"] = normalized
    state["bot"]["location"] = google_maps_link(normalized)
    state["activePatientId"] = patient_id

    fence_state = geofence_status(patient_id, normalized)
    write_firebase_location(patient_id, normalized, source, fence_state)

    state["tracking"].update({
        "location": normalized,
        "source": source,
        "fence": fence_state.get("fence"),
        "distance": fence_state.get("distance"),
        "inside": fence_state.get("inside"),
        "updatedAt": normalized["updatedAt"],
    })

    track_log = read_json(TRACK_LOG_JSON, [])
    track_log.insert(0, {
        "id": next_id(track_log),
        "patient_id": patient_id,
        "lat": normalized["lat"],
        "lng": normalized["lng"],
        "accuracy": normalized["accuracy"],
        "source": source,
        "inside": fence_state.get("inside"),
        "distance": fence_state.get("distance"),
        "created_at": normalized["updatedAt"],
    })
    write_json(TRACK_LOG_JSON, track_log[:TRACK_LOG_LIMIT])

    patient_name = patient.get("profile", {}).get("patientName") or patient.get("name", "Patient")
    fence = fence_state.get("fence")

    if fence_state.get("breached"):
        dispatch_emergency(
            patient_id,
            "geofence_breach",
            (
                f"{patient_name} left the safe zone "
                f"\"{fence['label']}\" and is {fence_state['distance']:.0f} m away "
                f"(allowed {fence['radius']:.0f} m)."
            ),
            location=normalized,
            cooldown_seconds=0,
            source="geofence",
        )
    elif fence_state.get("returned"):
        log_event(
            "alert",
            f"{patient_name} is back inside the safe zone \"{fence['label']}\".",
            patient_id=patient_id,
            severity="info",
            source="geofence",
            location=normalized,
        )
    else:
        # A quiet position update for the family chat, well below alert volume.
        now = time.time()
        if now - last_track_telegram_at.get(patient_id, 0) >= TRACK_TELEGRAM_SECONDS:
            last_track_telegram_at[patient_id] = now
            zone = ""
            if fence:
                zone = (
                    f"\nSafe zone {fence['label']}: "
                    f"{'inside' if fence_state['inside'] else 'outside'} "
                    f"({fence_state['distance']:.0f} m from centre)"
                )
            send_telegram(
                f"Companion Care Bot location update\n"
                f"Patient: {patient_name}\n"
                f"Map: {google_maps_link(normalized)}\n"
                f"Accuracy: {normalized['accuracy']:.0f} meters{zone}"
            )

    return {
        "location": normalized,
        "mapUrl": google_maps_link(normalized),
        "fence": fence,
        "distance": fence_state.get("distance"),
        "inside": fence_state.get("inside"),
        "breached": bool(fence_state.get("breached")),
    }


# =========================
# MPU6050 MOTION ALERTS
# =========================
def motion_from_vitals(vitals_data):
    """Turn raw Ax, Ay, Az into a magnitude and a change since the last read.

    The sketch decides the unit of the raw axes, so both numbers below are
    relative: magnitude compares against MOTION_IMPACT_LEVEL and the change
    against MOTION_JERK_LEVEL. Tune those in the environment, not here.
    """
    ax = safe_float(vitals_data.get("ax"), 0)
    ay = safe_float(vitals_data.get("ay"), 0)
    az = safe_float(vitals_data.get("az"), 0)
    return {
        "ax": ax,
        "ay": ay,
        "az": az,
        "magnitude": round(math.sqrt(ax * ax + ay * ay + az * az), 2),
    }


def check_motion_alerts(patient_id, vitals_data):
    motion = vitals_data.get("motion") or {}
    magnitude = safe_float(motion.get("magnitude"), 0)
    if magnitude <= 0:
        return "no sensor"

    patient_id = int(patient_id or 0)
    previous = last_motion_reading.get(patient_id)
    last_motion_reading[patient_id] = magnitude
    change = abs(magnitude - previous) if previous is not None else 0.0
    motion["change"] = round(change, 2)
    now = time.time()

    if magnitude >= MOTION_IMPACT_LEVEL or change >= MOTION_JERK_LEVEL:
        last_motion_move_at[patient_id] = now
        motion["status"] = "possible fall"
        dispatch_emergency(
            patient_id,
            "motion_fall",
            (
                "Possible fall detected by the motion sensor. "
                f"Ax {motion['ax']:.2f}, Ay {motion['ay']:.2f}, Az {motion['az']:.2f} "
                f"(force {magnitude:.1f}, jump {change:.1f})."
            ),
            cooldown_seconds=45,
            source="mpu6050",
        )
        return motion["status"]

    if magnitude <= MOTION_FREEFALL_LEVEL:
        last_motion_move_at[patient_id] = now
        motion["status"] = "free fall"
        dispatch_emergency(
            patient_id,
            "motion_freefall",
            (
                "Free fall detected by the motion sensor. "
                f"Force dropped to {magnitude:.1f}."
            ),
            cooldown_seconds=45,
            source="mpu6050",
        )
        return motion["status"]

    if change >= MOTION_SHAKE_LEVEL:
        last_motion_move_at[patient_id] = now
        motion["status"] = "agitated movement"
        trigger_automatic_alert(
            "motion_shake",
            (
                "Sudden agitated movement detected by the motion sensor "
                f"(jump {change:.1f})."
            ),
            severity="warning",
            cooldown_seconds=120,
        )
        return motion["status"]

    if change >= MOTION_STILL_LEVEL:
        last_motion_move_at[patient_id] = now
        motion["status"] = "moving"
        return motion["status"]

    motion["status"] = "still"
    started = last_motion_move_at.setdefault(patient_id, now)
    if now - started >= MOTION_STILL_SECONDS:
        last_motion_move_at[patient_id] = now
        trigger_automatic_alert(
            "motion_still",
            (
                "No movement from the motion sensor for "
                f"{MOTION_STILL_SECONDS // 60} minutes."
            ),
            severity="warning",
            cooldown_seconds=MOTION_STILL_SECONDS,
        )
    return motion["status"]


def check_vitals_alerts(patient_id, vitals_data):
    previous_temperature = last_temperature_by_patient.get(patient_id)
    if vitals_data.get("obstacle") == 1:
        trigger_automatic_alert(
            "obstacle_detected",
            "Obstacle detected. Bot stopped.",
            cooldown_seconds=10,
        )
    if vitals_data["heartRate"] > 110:
        trigger_automatic_alert(
            "high_heart_rate",
            f"High heart rate detected: {vitals_data['heartRate']} BPM.",
        )
    if vitals_data["heartRate"] < 45:
        trigger_automatic_alert(
            "low_heart_rate",
            f"Low heart rate detected: {vitals_data['heartRate']} BPM.",
        )
    if vitals_data["spo2"] < 92:
        trigger_automatic_alert(
            "low_spo2",
            f"Low SpO2 detected: {vitals_data['spo2']}%.",
        )
    if vitals_data["temperature"] >= 38:
        trigger_automatic_alert(
            "fever",
            f"Fever detected: {vitals_data['temperature']} deg C.",
        )
    if (
        previous_temperature is not None
        and vitals_data["temperature"] - previous_temperature >= 0.8
    ):
        trigger_automatic_alert(
            "temperature_spike",
            (
                "Sudden temperature increase detected: "
                f"{previous_temperature} to {vitals_data['temperature']} deg C."
            ),
        )
    last_temperature_by_patient[patient_id] = vitals_data["temperature"]


def apply_vitals_update(raw_data, patient_id, source="firebase", log_history=True):
    patient_id = int(patient_id)
    raw_data = raw_data or {}
    raw_direction = str(
        raw_data.get("direction", state["vitals"].get("direction", "S"))
    ).upper()[:1] or "S"
    normalized = normalize_firebase_vitals(raw_data)
    normalized.update({
        "activity": infer_activity(normalized),
        "source": source,
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    })
    state["vitals"].update(normalized)
    state["activePatientId"] = patient_id
    if state["vitals"].get("obstacle") == 1 and raw_direction != "S":
        try:
            set_firebase_direction("S", "obstacle")
        except RuntimeError as error:
            state["vitals"]["source"] = f"firebase error: {error}"
    if log_history:
        write_vitals_history(patient_id, state["vitals"])
    check_vitals_alerts(patient_id, state["vitals"])
    check_motion_alerts(patient_id, state["vitals"])
    return state["vitals"]


def sync_firebase_vitals(patient_id=None, force=False):
    global last_firebase_sync_at

    if not FIREBASE_DATABASE_URL or not FIREBASE_PATIENT_PATH:
        return state["vitals"]

    now = time.time()
    if not force and now - last_firebase_sync_at < 1.5:
        return state["vitals"]
    last_firebase_sync_at = now

    try:
        response = http_session.get(firebase_node_url(), timeout=4)
        response.raise_for_status()
        payload = response.json() or {}
    except Exception as error:
        state["vitals"]["source"] = f"firebase error: {error}"
        return state["vitals"]

    target_patient_id = patient_id or current_patient_id()
    if target_patient_id:
        return apply_vitals_update(payload, target_patient_id, "firebase")
    state["vitals"].update(normalize_firebase_vitals(payload))
    state["vitals"]["source"] = "firebase"
    state["vitals"]["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    return state["vitals"]


# Longest and most specific phrases first: "stop following" must not be
# read as "follow", and "turn left" is checked before a bare "left".
DIRECTION_COMMANDS = (
    ("S", (
        "stop following", "stop moving", "stop there", "stop now", "stop",
        "halt", "stand still", "stay there", "stay here", "wait there",
        "do not move", "dont move", "don t move", "follow me off",
    )),
    ("F", (
        "follow me", "start following", "come here", "come to me",
        "come closer", "come forward", "move forward", "go forward",
        "move ahead", "go ahead", "go straight", "straight", "forward",
        "follow",
    )),
    ("B", (
        "go backward", "move backward", "go backwards", "move backwards",
        "step back", "move back", "go back", "back off", "reverse",
        "backward", "backwards",
    )),
    ("L", ("turn left", "go left", "move left", "left side", "left")),
    ("R", ("turn right", "go right", "move right", "right side", "right")),
)

DIRECTION_LABELS = {
    "F": "forward",
    "B": "backward",
    "L": "left",
    "R": "right",
    "S": "stopped",
}

DIRECTION_REPLIES = {
    "F": "Okay, I am moving forward to you.",
    "B": "Okay, I am moving backward.",
    "L": "Okay, I am turning left.",
    "R": "Okay, I am turning right.",
    "S": "Okay, I have stopped and I am waiting here.",
}


def parse_direction_command(question):
    """Read a driving command out of something the patient said or typed."""
    text = re.sub(r"[^a-z0-9 ]+", " ", str(question).lower())
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None, ""

    for direction, phrases in DIRECTION_COMMANDS:
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", text):
                return direction, phrase

    return None, ""


def apply_direction_command(direction, source, spoken_as=""):
    """Send a direction to the robot and say what happened."""
    try:
        set_firebase_direction(direction, source)
    except (RuntimeError, ValueError) as error:
        return f"I could not send that to the robot. {error}", False

    if direction == "F":
        state["bot"]["followMe"] = True
    elif direction == "S":
        state["bot"]["followMe"] = False

    state["bot"]["lastInteraction"] = (
        f"Direction {direction} ({DIRECTION_LABELS[direction]}) from {source}"
    )
    log_event(
        "command",
        f"Direction {direction} ({DIRECTION_LABELS[direction]}) from {source}"
        + (f' after hearing "{spoken_as}"' if spoken_as else ""),
    )
    return DIRECTION_REPLIES[direction], True


_problem_last_logged = {}


def log_repeated_problem(key, message, every_seconds=60):
    """Print a recurring problem once a minute instead of on every attempt."""
    now = time.time()
    if now - _problem_last_logged.get(key, 0) < every_seconds:
        return
    _problem_last_logged[key] = now
    print(message)


def set_firebase_direction(direction, source="dashboard"):
    direction = str(direction or "").upper()[:1]
    if direction not in {"F", "B", "L", "R", "S"}:
        raise ValueError("Direction must be F, B, L, R, or S.")

    try:
        response = http_session.patch(
            firebase_node_url(),
            json={"direction": direction},
            timeout=4,
        )
        response.raise_for_status()
    except Exception as error:
        raise RuntimeError(f"Firebase direction write failed: {error}") from error

    state["vitals"]["direction"] = direction
    state["vitals"]["source"] = source
    state["vitals"]["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    return direction


def public_user(user):
    profile = user.get("profile", {})
    return {
        "id": int(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user.get("name", profile.get("patientName", "")),
        "profile": profile,
        "linkCode": user.get("link_code", "") if user["role"] == "patient" else "",
        "caregiverIds": user.get("caregiver_ids", []),
        "patientIds": user.get("patient_ids", []),
        "demo": bool(user.get("demo", False)),
    }


def find_user(users, user_id):
    return next(
        (user for user in users if int(user.get("id", 0)) == int(user_id)),
        None,
    )


def find_user_by_email(users, email):
    clean_email = str(email).strip().lower()
    return next(
        (
            user
            for user in users
            if str(user.get("email", "")).strip().lower() == clean_email
        ),
        None,
    )


def link_patient_and_caregiver(users, patient, caregiver):
    patient.setdefault("caregiver_ids", [])
    caregiver.setdefault("patient_ids", [])
    if caregiver["id"] not in patient["caregiver_ids"]:
        patient["caregiver_ids"].append(caregiver["id"])
    if patient["id"] not in caregiver["patient_ids"]:
        caregiver["patient_ids"].append(patient["id"])
    patient["requested_caregiver_email"] = ""
    write_json(USERS_JSON, users)


def current_patient_id():
    # Alerts also come from the camera threads, where there is no request.
    if has_request_context() and getattr(g, "current_user", None):
        user = g.current_user
        if user.get("role") == "patient":
            return int(user["id"])
    return state.get("activePatientId")


def create_session(user_id):
    sessions = read_json(SESSIONS_JSON, [])
    token = secrets.token_urlsafe(32)
    sessions.append({
        "token": token,
        "user_id": int(user_id),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    write_json(SESSIONS_JSON, sessions[-100:])
    return token


def remove_session(token):
    if not token:
        return
    sessions = read_json(SESSIONS_JSON, [])
    write_json(
        SESSIONS_JSON,
        [session for session in sessions if session.get("token") != token],
    )


@app.before_request
def authenticate_request():
    if not request.path.startswith("/api/"):
        return None

    public_paths = {
        "/api/health",
        "/api/auth/login",
        "/api/auth/register",
    }
    # The phone tracker page is opened from a link and never signs in, so it
    # carries its own patient token instead of the session cookie.
    public_prefixes = ("/api/track/session", "/api/track/ping", "/api/track/panic")
    if request.path in public_paths or request.path.startswith(public_prefixes):
        return None

    token = request.cookies.get("carebot_session", "")
    session = next(
        (
            item
            for item in read_json(SESSIONS_JSON, [])
            if secrets.compare_digest(item.get("token", ""), token)
        ),
        None,
    )
    users = read_json(USERS_JSON, [])
    user = find_user(users, session["user_id"]) if session else None
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    g.current_user = user
    if user.get("role") == "caregiver":
        caregiver_paths = (
            "/api/auth/",
            "/api/caregiver/",
            "/api/alerts/",
            "/api/caregivers",
            "/api/chat/family",
            "/api/notes",
        )
        if not request.path.startswith(caregiver_paths):
            return jsonify({"error": "Patient access required."}), 403
    return None


# =========================
# TELEGRAM + ALERT LOG
# =========================
def send_telegram(message, detailed=False):
    token, chat_ids = telegram_config()
    details = {
        "ok": False,
        "configured": bool(token and chat_ids),
        "hasToken": bool(token),
        "chatCount": len(chat_ids),
        "results": [],
    }
    if not token or not chat_ids:
        print("Telegram token or chat ids missing.")
        return details if detailed else False

    sent_any = False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for chat_id in chat_ids:
            payload = {
                "chat_id": chat_id,
                "text": message,
            }
            response = http_session.post(url, json=payload, timeout=8)
            sent_any = response.ok or sent_any
            result = {
                "chatId": chat_id,
                "ok": response.ok,
                "statusCode": response.status_code,
            }
            if not response.ok:
                result["error"] = response.text[:300]
                print(f"Telegram Error for chat {chat_id}: {response.text}")
            details["results"].append(result)
        details["ok"] = sent_any
        return details if detailed else sent_any
    except Exception as e:
        print("Telegram Error:", e)
        details["error"] = str(e)
        return details if detailed else False


def alert_sms_numbers(emergency_number=""):
    """Every phone that should receive the emergency SMS and the voice call."""
    numbers = parse_chat_ids(ALERT_SMS_NUMBERS)
    if emergency_number and emergency_number not in numbers:
        numbers.insert(0, emergency_number)
    return numbers


def twilio_configured():
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER)


def send_sms_and_call(numbers, message, detailed=False):
    """Ring and text the emergency phones through Twilio.

    The GSM module wired to the bot already reads CallStatus and SmsStatus out
    of Firebase and places the call itself, so Twilio is only the fallback for
    when that module is powered off. Without Twilio credentials this reports
    that Firebase is carrying the alert on its own.
    """
    result = {
        "configured": twilio_configured(),
        "numbers": numbers,
        "sms": [],
        "calls": [],
    }
    if not numbers:
        result["error"] = "No emergency phone number saved."
        return result if detailed else False
    if not twilio_configured():
        result["error"] = "Twilio is not configured; Firebase is carrying the alert."
        return result if detailed else False

    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    base = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}"
    spoken = message.replace("\n", ". ")[:900]
    twiml = f"<Response><Say voice=\"alice\">{spoken}</Say></Response>"

    for number in numbers:
        try:
            sms_response = http_session.post(
                f"{base}/Messages.json",
                data={"To": number, "From": TWILIO_FROM_NUMBER, "Body": message[:1500]},
                auth=auth,
                timeout=8,
            )
            result["sms"].append({
                "to": number,
                "ok": sms_response.ok,
                "statusCode": sms_response.status_code,
                "error": None if sms_response.ok else sms_response.text[:200],
            })
        except Exception as error:
            result["sms"].append({"to": number, "ok": False, "error": str(error)})

        try:
            call_response = http_session.post(
                f"{base}/Calls.json",
                data={"To": number, "From": TWILIO_FROM_NUMBER, "Twiml": twiml},
                auth=auth,
                timeout=8,
            )
            result["calls"].append({
                "to": number,
                "ok": call_response.ok,
                "statusCode": call_response.status_code,
                "error": None if call_response.ok else call_response.text[:200],
            })
        except Exception as error:
            result["calls"].append({"to": number, "ok": False, "error": str(error)})

    ok = any(item["ok"] for item in result["sms"] + result["calls"])
    result["ok"] = ok
    return result if detailed else ok


def dispatch_emergency(
    patient_id,
    reason,
    message,
    location=None,
    cooldown_seconds=60,
    source="automatic",
):
    """Raise one emergency everywhere: Firebase, Telegram, SMS and a call."""
    now = time.time()
    if cooldown_seconds and now - automatic_alert_cooldowns.get(reason, 0) < cooldown_seconds:
        return None
    automatic_alert_cooldowns[reason] = now

    patient_id = patient_id or state.get("activePatientId")
    alert_location = normalize_location(location) or state["bot"].get("currentLocation")
    log_event(
        "emergency",
        message,
        patient_id=patient_id,
        severity="critical",
        source=source,
        location=alert_location,
        reason=reason,
    )

    profile = current_patient_profile(patient_id)
    emergency_number = (
        profile.get("emergencyNumber") or profile.get("emergencyContact") or ""
    )
    sms_text = build_sms_text(
        profile.get("patientName") or PATIENT_NAME or "Patient",
        message,
        alert_location,
        emergency_number,
    )
    return send_sms_and_call(
        alert_sms_numbers(emergency_number),
        sms_text,
        detailed=True,
    )


def create_care_alert(
    patient_id,
    alert_type,
    message,
    severity="warning",
    source="system",
):
    if not patient_id:
        return None

    alerts = read_json(CARE_ALERTS_JSON, [])
    item = {
        "id": next_id(alerts),
        "patient_id": int(patient_id),
        "type": alert_type,
        "message": message,
        "severity": severity,
        "source": source,
        "acknowledged": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    alerts.insert(0, item)
    write_json(CARE_ALERTS_JSON, alerts[:500])
    return item


def trigger_automatic_alert(
    key,
    message,
    severity="critical",
    cooldown_seconds=60,
):
    now = time.time()
    if now - automatic_alert_cooldowns.get(key, 0) < cooldown_seconds:
        return False
    automatic_alert_cooldowns[key] = now
    log_event(
        "emergency" if severity == "critical" else "alert",
        message,
        patient_id=state.get("activePatientId"),
        severity=severity,
        source="automatic",
    )
    return True


def log_event(
    event_type,
    message,
    patient_id=None,
    severity=None,
    source="system",
    location=None,
    reason="",
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    patient_id = patient_id or state.get("activePatientId")
    normalized_location = normalize_location(location)
    if normalized_location:
        state["bot"]["currentLocation"] = normalized_location
    alert_location = normalized_location or state["bot"].get("currentLocation")
    location_link = google_maps_link(alert_location)
    alert_message = message
    firebase_emergency = None
    if event_type == "emergency":
        firebase_emergency = write_firebase_emergency(
            patient_id,
            message,
            alert_location,
            reason=reason,
        )
    if event_type in ["emergency", "alert", "missed"] and location_link:
        alert_message = (
            f"{message}\n"
            f"Current location: {location_link}"
        )
        if alert_location.get("accuracy"):
            alert_message += f"\nAccuracy: {alert_location['accuracy']:.0f} meters"
    if firebase_emergency:
        alert_message = (
            f"{alert_message}\n"
            f"Patient: {firebase_emergency['PatientName']}\n"
            f"Emergency number: {firebase_emergency['EmergencyNumber']}\n"
            f"Emergency event: {firebase_emergency['EmergencyEventId']}"
        )

    live_item = {
        "type": event_type,
        "message": alert_message,
        "time": now,
        "patient_id": patient_id,
    }

    state["alerts"].insert(0, live_item)
    state["alerts"] = state["alerts"][:50]

    logs = read_json(LOGS_JSON, [])

    log_item = {
        "id": next_id(logs),
        "event_type": event_type,
        "message": alert_message,
        "created_at": now,
        "patient_id": patient_id,
    }

    logs.insert(0, log_item)
    logs = logs[:100]

    write_json(LOGS_JSON, logs)

    if event_type in ["emergency", "alert", "missed"]:
        create_care_alert(
            patient_id,
            event_type,
            alert_message,
            severity or ("critical" if event_type == "emergency" else "warning"),
            source,
        )

    if event_type in ["emergency", "alert", "missed"]:
        send_telegram(f"Companion Care Bot {event_type.upper()}:\n{alert_message}")


def save_speech_note(text, patient_id=None, source="dashboard"):
    clean_text = str(text or "").strip()
    if not clean_text:
        return None

    notes = read_json(SPEECH_NOTES_JSON, [])
    item = {
        "id": next_id(notes),
        "patient_id": int(patient_id or current_patient_id() or 0),
        "text": clean_text,
        "source": source,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    notes.insert(0, item)
    write_json(SPEECH_NOTES_JSON, notes[:200])
    return item


# =========================
# TEXT TO SPEECH
# =========================
speech_lock = threading.Lock()
speech_available = True


def speak_text(text):
    """Say something out loud, one utterance at a time."""
    global speech_available

    if not speech_available or not str(text).strip():
        return

    def worker():
        global speech_available

        # Two engines talking at once garble each other, so utterances queue.
        with speech_lock:
            try:
                import pyttsx3

                engine = pyttsx3.init()
                engine.setProperty("rate", 150)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except ImportError:
                speech_available = False
                print(
                    "Speech is off: pyttsx3 is not installed for this "
                    "interpreter. Run: pip install -r requirements.txt"
                )
            except Exception as error:
                log_repeated_problem("tts", f"TTS error: {error}")

    threading.Thread(target=worker, daemon=True).start()


# =========================
# CHATBOT
# =========================
def best_answer(question, qa):
    q = question.lower().strip()

    if not q:
        return None

    for key, answer in qa.items():
        if key in q:
            return answer

    return "I do not have a saved answer for that question yet. Please ask the caregiver or choose one of the suggested questions."


# =========================
# IMAGE SAVE
# =========================
def decode_data_url(data_url):
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]

    return base64.b64decode(data_url)


def relative_photo_paths(relative):
    paths = relative.get("photo_paths")
    if isinstance(paths, list) and paths:
        return [Path(path) for path in paths]

    legacy_path = relative.get("photo_path")
    return [Path(legacy_path)] if legacy_path else []


def relative_identity_key(relative):
    return int(relative.get("id", 0))


def detect_face_boxes_raw(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    min_size = max(45, min(image.shape[:2]) // 10)
    cascades = [
        "haarcascade_frontalface_default.xml",
        "haarcascade_frontalface_alt2.xml",
    ]
    detected = []

    for cascade_name in cascades:
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + cascade_name)
        faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=8,
            minSize=(min_size, min_size),
        )
        detected.extend(tuple(map(int, face)) for face in faces)

    unique_faces = []
    for face in sorted(detected, key=lambda box: box[2] * box[3], reverse=True):
        x, y, width, height = face
        center = (x + width / 2, y + height / 2)
        if any(
            abs(center[0] - (other[0] + other[2] / 2)) < min(width, other[2]) * 0.35
            and abs(center[1] - (other[1] + other[3] / 2)) < min(height, other[3]) * 0.35
            for other in unique_faces
        ):
            continue
        unique_faces.append(face)

    filtered_faces = []
    for face in unique_faces:
        x, y, width, height = face
        aspect = width / max(height, 1)
        if 0.45 <= aspect <= 1.55:
            filtered_faces.append(face)

    return filtered_faces


def detect_face_boxes(image):
    if image is None:
        return []

    mp_box = detect_face_with_mediapipe(image)
    if mp_box is not None:
        return [mp_box]

    raw_faces = detect_face_boxes_raw(image)
    validated_faces = []
    for face in raw_faces:
        if validate_face_box(image, face):
            validated_faces.append(face)

    return validated_faces


def validate_face_box(image, face_box):
    x, y, width, height = face_box
    crop = image[y : y + height, x : x + width]

    if crop is None or crop.size == 0:
        return False

    if mp is not None:
        mp_box = detect_face_with_mediapipe(crop)
        return mp_box is not None and is_plausible_face_box(mp_box, crop.shape)

    try:
        import face_recognition

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb)
        return len(locations) == 1 and is_plausible_face_box(
            face_box_from_locations(locations[0]), crop.shape
        )
    except Exception:
        faces = detect_face_boxes_raw(crop)
        return len(faces) == 1


def face_box_from_locations(location):
    top, right, bottom, left = location
    width = right - left
    height = bottom - top
    return left, top, width, height


def is_plausible_face_box(face_box, image_shape):
    frame_height, frame_width = image_shape[:2]
    x, y, width, height = face_box
    min_width = max(48, int(frame_width * 0.12))
    min_height = max(48, int(frame_height * 0.12))
    aspect = width / max(height, 1)
    return (
        width >= min_width
        and height >= min_height
        and 0.35 <= aspect <= 1.7
    )


def detect_largest_face(image):
    faces = [
        face
        for face in detect_face_boxes(image)
        if is_plausible_face_box(face, image.shape)
    ]

    if len(faces) == 0:
        return None

    x, y, width, height = max(faces, key=lambda box: box[2] * box[3])
    margin_x = int(width * 0.12)
    margin_y = int(height * 0.12)
    x1 = max(0, x - margin_x)
    y1 = max(0, y - margin_y)
    x2 = min(image.shape[1], x + width + margin_x)
    y2 = min(image.shape[0], y + height + margin_y)
    return image[y1:y2, x1:x2]


def opencv_face_feature(image):
    face = detect_largest_face(image)
    if face is None or face.size == 0:
        return None

    return opencv_face_feature_from_crop(face)


def opencv_face_feature_from_crop(face):
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    gray = cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(gray.astype(np.float32) / 255.0)[:24, :24].flatten()[1:]
    return dct / (np.linalg.norm(dct) + 1e-8)


def prepare_lbph_face(face):
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.resize(gray, (128, 128), interpolation=cv2.INTER_CUBIC)


def load_lbph_recognizer():
    global lbph_recognizer_cache

    if lbph_recognizer_cache is not None:
        return lbph_recognizer_cache
    if not hasattr(cv2, "face") or not LBPH_PATH.exists():
        return None

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(LBPH_PATH))
    lbph_recognizer_cache = recognizer
    return recognizer


def get_sface_models():
    global yunet_detector, sface_recognizer

    if not YUNET_PATH.exists() or not SFACE_PATH.exists():
        return None, None

    with sface_lock:
        if yunet_detector is None:
            yunet_detector = cv2.FaceDetectorYN.create(
                str(YUNET_PATH),
                "",
                (320, 320),
                0.55,
                0.3,
                5000,
            )
        if sface_recognizer is None:
            sface_recognizer = cv2.FaceRecognizerSF.create(
                str(SFACE_PATH),
                "",
            )
    return yunet_detector, sface_recognizer


def sface_feature(image):
    if image is None or image.size == 0:
        return None

    detector, recognizer = get_sface_models()
    if detector is None or recognizer is None:
        return None

    with sface_lock:
        detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = detector.detect(image)
        if faces is None or len(faces) != 1:
            return None
        face = max(faces, key=lambda item: float(item[2] * item[3]))
        aligned = recognizer.alignCrop(image, face)
        feature = recognizer.feature(aligned).flatten().astype(np.float32)

    return feature / (np.linalg.norm(feature) + 1e-8)


def has_single_clear_face_image(image):
    if image is None or image.size == 0:
        return False

    mp_box = detect_face_with_mediapipe(image)
    if mp_box is not None:
        return is_plausible_face_box(mp_box, image.shape)

    try:
        import face_recognition

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb)
        return len(locations) == 1 and is_plausible_face_box(
            face_box_from_locations(locations[0]), image.shape
        )
    except Exception:
        faces = detect_face_boxes_raw(image)
        return len(faces) == 1 and is_plausible_face_box(faces[0], image.shape)


def save_relative_images(relative_id, safe_name, images):
    saved_paths = []

    try:
        for index, image in enumerate(images[:5], start=1):
            filename = (
                f"{safe_name}_{relative_id}_{int(time.time() * 1000)}_{index}.jpg"
            )
            path = REL_DIR / filename
            path.write_bytes(decode_data_url(image))
            saved_paths.append(path)

            decoded = cv2.imread(str(path))
            if decoded is None or not has_single_clear_face_image(decoded):
                raise ValueError(
                    f"Photo {index} does not contain a clear single face. Retake it."
                )
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise

    return saved_paths


def delete_relative_images(relative):
    relative_root = REL_DIR.resolve()
    for path in relative_photo_paths(relative):
        try:
            resolved_path = path.resolve()
            if resolved_path.parent == relative_root:
                resolved_path.unlink(missing_ok=True)
        except OSError:
            continue


def face_features_from_paths(photo_paths):
    features = []
    for photo_path in photo_paths:
        image = cv2.imread(str(photo_path))
        if image is None:
            continue
        face_crop = detect_largest_face(image)
        if face_crop is None:
            continue
        feature = opencv_face_feature_from_crop(face_crop)
        if feature is not None:
            features.append(feature)
    return features


def find_duplicate_relative(photo_paths, relatives, exclude_id=None):
    new_features = face_features_from_paths(photo_paths)
    if not new_features:
        return None

    new_centroid = np.mean(new_features, axis=0)
    new_centroid /= np.linalg.norm(new_centroid) + 1e-8

    for relative in relatives:
        if int(relative.get("id", 0)) == int(exclude_id or -1):
            continue
        saved_features = face_features_from_paths(relative_photo_paths(relative))
        if not saved_features:
            continue
        saved_centroid = np.mean(saved_features, axis=0)
        saved_centroid /= np.linalg.norm(saved_centroid) + 1e-8
        if float(np.dot(new_centroid, saved_centroid)) >= 0.985:
            return relative

    return None


# =========================
# FACE DATABASE
# =========================
def load_face_db():
    if PKL_PATH.exists():
        try:
            with open(PKL_PATH, "rb") as file:
                face_db = pickle.load(file)
            if isinstance(face_db, dict):
                face_db.setdefault("relative_ids", [])
                face_db.setdefault("names", [])
                face_db.setdefault("relationships", [])
                face_db.setdefault("encodings", [])
                return face_db
        except (OSError, pickle.PickleError, EOFError):
            pass

    return {
        "version": 3,
        "engine": "unknown",
        "relative_ids": [],
        "names": [],
        "relationships": [],
        "encodings": [],
        "ambiguous_relative_ids": [],
    }


def train_face_db():
    global lbph_recognizer_cache

    relatives = read_json(RELATIVES_JSON, [])
    active_patient_id = state.get("activePatientId")
    if active_patient_id:
        relatives = [
            row
            for row in relatives
            if int(row.get("patient_id", active_patient_id))
            == int(active_patient_id)
        ]

    face_db = {
        "version": 3,
        "engine": "opencv_sface",
        "relative_ids": [],
        "names": [],
        "relationships": [],
        "encodings": [],
        "ambiguous_relative_ids": [],
    }

    if get_sface_models() != (None, None):
        for row in relatives:
            for photo_path in relative_photo_paths(row):
                if not photo_path.exists():
                    continue

                image = cv2.imread(str(photo_path))
                feature = sface_feature(image)
                if feature is not None:
                    face_db["relative_ids"].append(int(row["id"]))
                    face_db["names"].append(row["name"])
                    face_db["relationships"].append(row["relationship"])
                    face_db["encodings"].append(feature)
    else:
        print("SFace models unavailable. Using OpenCV fallback.")
        face_db = {
            "version": 3,
            "engine": "opencv_lbph" if hasattr(cv2, "face") else "opencv_dct",
            "relative_ids": [],
            "names": [],
            "relationships": [],
            "encodings": [],
            "labels": {},
            "ambiguous_relative_ids": [],
        }
        lbph_faces = []
        lbph_labels = []
        label_by_relative_id = {}

        for row in relatives:
            relative_id = int(row["id"])
            label = label_by_relative_id.setdefault(
                relative_id,
                len(label_by_relative_id),
            )
            face_db["labels"][str(label)] = {
                "id": relative_id,
                "name": row["name"],
                "relationship": row["relationship"],
            }
            for photo_path in relative_photo_paths(row):
                if not photo_path.exists():
                    continue

                image = cv2.imread(str(photo_path))
                if image is None:
                    continue

                face_crop = detect_largest_face(image)
                if face_crop is None:
                    continue

                feature = opencv_face_feature_from_crop(face_crop)
                if feature is None:
                    continue

                face_db["relative_ids"].append(relative_id)
                face_db["names"].append(row["name"])
                face_db["relationships"].append(row["relationship"])
                face_db["encodings"].append(feature)
                lbph_faces.append(prepare_lbph_face(face_crop))
                lbph_labels.append(label)

        if face_db["engine"] == "opencv_lbph" and lbph_faces:
            recognizer = cv2.face.LBPHFaceRecognizer_create(
                radius=1,
                neighbors=8,
                grid_x=8,
                grid_y=8,
            )
            recognizer.train(lbph_faces, np.asarray(lbph_labels, dtype=np.int32))
            recognizer.write(str(LBPH_PATH))
            lbph_recognizer_cache = recognizer
        elif face_db["engine"] == "opencv_lbph":
            LBPH_PATH.unlink(missing_ok=True)
            lbph_recognizer_cache = None

    features_by_id = {}
    for relative_id, encoding in zip(
        face_db.get("relative_ids", []),
        face_db.get("encodings", []),
    ):
        features_by_id.setdefault(int(relative_id), []).append(encoding)

    centroids = {}
    for relative_id, features in features_by_id.items():
        centroid = np.mean(features, axis=0)
        centroids[relative_id] = centroid / (np.linalg.norm(centroid) + 1e-8)

    ambiguous_ids = set()
    centroid_items = list(centroids.items())
    for index, (first_id, first_centroid) in enumerate(centroid_items):
        for second_id, second_centroid in centroid_items[index + 1:]:
            if float(np.dot(first_centroid, second_centroid)) >= 0.985:
                ambiguous_ids.update((first_id, second_id))
    face_db["ambiguous_relative_ids"] = sorted(ambiguous_ids)

    with open(PKL_PATH, "wb") as file:
        pickle.dump(face_db, file)

    state["bot"]["trainedFaceSamples"] = len(face_db["names"])
    log_event("info", f"Face model trained with {len(face_db['names'])} relative photo(s).")

    return len(face_db["names"])


def recognize_face(frame, face_boxes=None):
    face_db = load_face_db()
    state["bot"]["trainedFaceSamples"] = len(face_db.get("encodings", []))

    if not face_db["encodings"]:
        return "Unknown", "No trained faces"

    if face_db.get("engine") == "opencv_sface":
        feature = sface_feature(frame)
        if feature is None:
            state["bot"]["faceMatchConfidence"] = 0
            return "Unknown", "No face"

        identity_scores = {}
        for relative_id, name, relationship, encoding in zip(
            face_db.get("relative_ids", []),
            face_db.get("names", []),
            face_db.get("relationships", []),
            face_db.get("encodings", []),
        ):
            similarity = float(np.dot(feature, encoding))
            identity_scores.setdefault(
                (int(relative_id), name, relationship),
                [],
            ).append(similarity)

        ranked = sorted(
            (
                (
                    float(np.mean(sorted(scores, reverse=True)[:3])),
                    max(scores),
                    identity,
                )
                for identity, scores in identity_scores.items()
            ),
            reverse=True,
        )
        if not ranked:
            return "Unknown", "No trained faces"

        best_mean, best_max, identity = ranked[0]
        second_mean = ranked[1][0] if len(ranked) > 1 else -1.0
        confidence = int(np.clip((best_mean - 0.20) / 0.65 * 100, 0, 100))
        state["bot"]["faceMatchConfidence"] = confidence

        relative_id, name, relationship = identity
        if relative_id in face_db.get("ambiguous_relative_ids", []):
            state["bot"]["faceMatchConfidence"] = 0
            return "Unknown", "Duplicate training photos"

        minimum_similarity = 0.40 if len(ranked) == 1 else 0.43
        required_gap = 0.0 if len(ranked) == 1 else 0.045
        if (
            best_mean >= minimum_similarity
            and best_max >= minimum_similarity + 0.03
            and best_mean - second_mean >= required_gap
        ):
            return name, relationship
        return "Unknown", "Unknown"

    mp_face_box = detect_face_with_mediapipe(frame)
    if mp_face_box is not None:
        face_boxes = [mp_face_box]

    try:
        import face_recognition

        if face_boxes is None or len(face_boxes) == 0:
            return "Unknown", "No face"

        face_x, face_y, face_width, face_height = max(
            face_boxes,
            key=lambda box: box[2] * box[3],
        )
        frame_area = frame.shape[0] * frame.shape[1]
        if face_width * face_height < frame_area * 0.05:
            return "Unknown", "No face"
        margin_x = int(face_width * 0.12)
        margin_y = int(face_height * 0.12)
        x1 = max(0, face_x - margin_x)
        y1 = max(0, face_y - margin_y)
        x2 = min(frame.shape[1], face_x + face_width + margin_x)
        y2 = min(frame.shape[0], face_y + face_height + margin_y)
        cropped = frame[y1:y2, x1:x2]

        if cropped.size == 0:
            return "Unknown", "No face"

        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, locations)

        if not encodings:
            return "Unknown", "No face"

        distances = face_recognition.face_distance(face_db["encodings"], encodings[0])
        matches = face_recognition.compare_faces(
            face_db["encodings"],
            encodings[0],
            tolerance=0.32,
        )
        state["bot"]["faceMatchConfidence"] = max(
            0,
            min(100, int((1 - float(np.min(distances))) * 100)),
        )

        identity_scores = {}
        relative_ids = face_db.get("relative_ids", [])
        if len(relative_ids) != len(face_db["names"]):
            relative_ids = list(range(len(face_db["names"])))
        for relative_id, name, relationship, distance, matched in zip(
            relative_ids,
            face_db["names"],
            face_db["relationships"],
            distances,
            matches,
        ):
            identity = (relative_id, name, relationship)
            record = identity_scores.setdefault(identity, {
                "distances": [],
                "match_count": 0,
            })
            record["distances"].append(float(distance))
            if matched:
                record["match_count"] += 1

        candidates = []
        for identity, record in identity_scores.items():
            distances_array = np.array(record["distances"], dtype=float)
            candidates.append(
                {
                    "identity": identity,
                    "min_distance": float(np.min(distances_array)),
                    "mean_distance": float(np.mean(distances_array)),
                    "match_count": record["match_count"],
                    "total": len(distances_array),
                }
            )

        if not candidates:
            return "Unknown", "Unknown"

        candidates.sort(key=lambda item: (item["min_distance"], -item["match_count"]))
        best = candidates[0]
        second_best = candidates[1] if len(candidates) > 1 else None
        min_distance = best["min_distance"]
        mean_distance = best["mean_distance"]
        match_fraction = best["match_count"] / max(best["total"], 1)
        required_matches = max(2, int(round(best["total"] * 0.6)))
        distance_gap = (
            second_best["min_distance"] - min_distance
            if second_best is not None
            else 0.22
        )

        is_single_identity = len(candidates) == 1
        if is_single_identity:
            strict_matches = max(4, int(round(best["total"] * 0.7)))
            if (
                best["match_count"] >= strict_matches
                and match_fraction >= 0.75
                and min_distance < 0.24
                and mean_distance < 0.26
                and distance_gap > 0.18
                and state["bot"]["faceMatchConfidence"] >= 70
            ):
                _, name, relationship = best["identity"]
                return name, relationship

            return "Unknown", "Unknown"

        if (
            best["match_count"] >= required_matches
            and match_fraction >= 0.72
            and min_distance < 0.26
            and mean_distance < 0.28
            and distance_gap > 0.12
            and state["bot"]["faceMatchConfidence"] >= 66
        ):
            _, name, relationship = best["identity"]
            return name, relationship

        return "Unknown", "Unknown"

    except Exception:
        face_crop = None
        if face_boxes:
            face_x, face_y, face_width, face_height = max(
                face_boxes,
                key=lambda box: box[2] * box[3],
            )
            margin_x = int(face_width * 0.12)
            margin_y = int(face_height * 0.12)
            x1 = max(0, face_x - margin_x)
            y1 = max(0, face_y - margin_y)
            x2 = min(frame.shape[1], face_x + face_width + margin_x)
            y2 = min(frame.shape[0], face_y + face_height + margin_y)
            face_crop = frame[y1:y2, x1:x2]
        else:
            return "Unknown", "No face"

        if face_crop is None or face_crop.size == 0:
            state["bot"]["faceMatchConfidence"] = 0
            return "Unknown", "No face"

        if face_db.get("engine") == "opencv_lbph":
            recognizer = load_lbph_recognizer()
            labels = face_db.get("labels", {})
            if recognizer is None:
                return "Unknown", "Retrain faces"

            label, distance = recognizer.predict(prepare_lbph_face(face_crop))
            identity = labels.get(str(label))
            acceptance_distance = 62.0
            match_confidence = max(0, min(100, int(100 - distance)))
            state["bot"]["faceMatchConfidence"] = match_confidence

            if (
                identity
                and int(identity.get("id", -1))
                not in face_db.get("ambiguous_relative_ids", [])
                and distance <= acceptance_distance
            ):
                return identity["name"], identity["relationship"]

            if identity and int(identity.get("id", -1)) in face_db.get(
                "ambiguous_relative_ids",
                [],
            ):
                state["bot"]["faceMatchConfidence"] = 0
                return "Unknown", "Duplicate training photos"
            return "Unknown", "Unknown"

        if face_db.get("engine") != "opencv_dct":
            return "Unknown", "Retrain faces"

        feature = opencv_face_feature_from_crop(face_crop)
        identity_scores = {}
        relative_ids = face_db.get("relative_ids", [])
        if len(relative_ids) != len(face_db["names"]):
            relative_ids = list(range(len(face_db["names"])))
        for relative_id, name, relationship, encoding in zip(
            relative_ids,
            face_db["names"],
            face_db["relationships"],
            face_db["encodings"],
        ):
            score = float(np.dot(feature, encoding))
            identity_scores.setdefault(
                (relative_id, name, relationship),
                [],
            ).append(score)

        ranked = sorted(
            (
                (
                    max(scores),
                    float(np.mean(sorted(scores, reverse=True)[:3])),
                    identity,
                )
                for identity, scores in identity_scores.items()
            ),
            reverse=True,
        )

        if ranked:
            best_max, best_mean, identity = ranked[0]
            state["bot"]["faceMatchConfidence"] = max(
                0,
                min(100, int(best_mean * 100)),
            )
            second_mean = ranked[1][1] if len(ranked) > 1 else -1.0
            if (
                best_max > 0.88
                and best_mean > 0.82
                and best_mean - second_mean > 0.10
            ):
                return identity[1], identity[2]

        return "Unknown", "Please label"


# =========================
# EMOTION RECOGNITION
# =========================
def get_mediapipe_models():
    global mp_hands, mp_face_mesh

    if mp is None:
        return None, None

    with mp_init_lock:
        if mp_hands is None:
            mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=1,
                min_detection_confidence=0.4,
                min_tracking_confidence=0.4,
            )

        if mp_face_mesh is None:
            mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=False,
                min_detection_confidence=0.45,
                min_tracking_confidence=0.45,
            )

    return mp_hands, mp_face_mesh


def warmup_mediapipe_models():
    hands, face_mesh = get_mediapipe_models()
    sample = np.zeros((240, 320, 3), dtype=np.uint8)
    if face_mesh is not None:
        face_mesh.process(sample)
    if hands is not None:
        hands.process(sample)


def landmark_distance(landmarks, first, second):
    point_a = landmarks[first]
    point_b = landmarks[second]
    return float(np.hypot(point_a.x - point_b.x, point_a.y - point_b.y))


def face_box_from_landmarks(face_landmarks, frame_width, frame_height):
    points = face_landmarks.landmark
    x_values = [point.x for point in points]
    y_values = [point.y for point in points]
    x1 = max(0, int(min(x_values) * frame_width))
    y1 = max(0, int(min(y_values) * frame_height))
    x2 = min(frame_width, int(max(x_values) * frame_width))
    y2 = min(frame_height, int(max(y_values) * frame_height))

    if x2 <= x1 or y2 <= y1:
        return None

    return x1, y1, x2 - x1, y2 - y1


def detect_face_with_mediapipe(frame):
    if mp is None:
        return None

    _, face_mesh = get_mediapipe_models()
    if face_mesh is None:
        return None

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    with mp_face_lock:
        results = face_mesh.process(rgb)
    if not results.multi_face_landmarks:
        return None

    face_landmarks = results.multi_face_landmarks[0]
    return face_box_from_landmarks(face_landmarks, frame.shape[1], frame.shape[0])


def mediapipe_expression(frame):
    _, face_mesh = get_mediapipe_models()
    if face_mesh is None:
        return None, None, None, 0

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    with mp_face_lock:
        results = face_mesh.process(rgb)
    if not results.multi_face_landmarks:
        return "unknown", "MediaPipe is waiting for a clear face", None, 0

    face_landmarks = results.multi_face_landmarks[0]
    landmarks = face_landmarks.landmark
    face_width = max(landmark_distance(landmarks, 234, 454), 1e-6)
    face_height = max(landmark_distance(landmarks, 10, 152), 1e-6)
    mouth_width = landmark_distance(landmarks, 61, 291) / face_width
    mouth_open = landmark_distance(landmarks, 13, 14) / face_height
    left_eye_open = landmark_distance(landmarks, 159, 145) / face_height
    right_eye_open = landmark_distance(landmarks, 386, 374) / face_height
    eye_open = (left_eye_open + right_eye_open) / 2
    left_brow_gap = landmark_distance(landmarks, 105, 159) / face_height
    right_brow_gap = landmark_distance(landmarks, 334, 386) / face_height
    brow_asymmetry = abs(left_brow_gap - right_brow_gap)
    brow_gap = (left_brow_gap + right_brow_gap) / 2
    mouth_center_y = (landmarks[13].y + landmarks[14].y) / 2
    mouth_corner_lift = mouth_center_y - (
        landmarks[61].y + landmarks[291].y
    ) / 2
    smile_score = (
        max(0.0, mouth_width - 0.36) * 3.5
        + max(0.0, mouth_corner_lift - 0.002) * 12
        - max(0.0, mouth_open - 0.09) * 2
    )
    surprise_score = max(0.0, mouth_open - 0.055) * 8 + max(
        0.0,
        eye_open - 0.025,
    ) * 8
    tired_score = max(0.0, 0.019 - eye_open) * 30
    sad_score = max(0.0, -mouth_corner_lift - 0.003) * 12
    angry_score = (
        max(0.0, 0.095 - brow_gap) * 9
        + max(0.0, 0.018 - mouth_open) * 5
    )
    confused_score = max(0.0, brow_asymmetry - 0.008) * 18

    metrics = {
        "mouthWidth": round(mouth_width, 3),
        "mouthOpen": round(mouth_open, 3),
        "eyeOpen": round(eye_open, 3),
        "smile": round(smile_score, 3),
        "sad": round(sad_score, 3),
        "angry": round(angry_score, 3),
        "confused": round(confused_score, 3),
    }

    if surprise_score > 0.30:
        expression = "surprised"
        confidence = min(0.98, 0.55 + surprise_score)
    elif smile_score > 0.38:
        expression = "happy"
        confidence = min(0.98, 0.60 + smile_score)
    elif angry_score > 0.25:
        expression = "angry"
        confidence = min(0.92, 0.55 + angry_score)
    elif confused_score > 0.22:
        expression = "confused"
        confidence = min(0.88, 0.52 + confused_score)
    elif sad_score > 0.10:
        expression = "sad"
        confidence = min(0.90, 0.55 + sad_score)
    elif tired_score > 0.16:
        expression = "tired"
        confidence = min(0.92, 0.55 + tired_score)
    else:
        expression = "neutral"
        confidence = 0.60

    return (
        expression,
        (
            "Face landmarks: "
            f"smile {metrics['smile']}, mouth {metrics['mouthOpen']}, "
            f"eyes {metrics['eyeOpen']}, angry {metrics['angry']}, "
            f"confused {metrics['confused']}"
        ),
        face_landmarks,
        int(confidence * 100),
    )


def detect_emotion(frame):
    global deepface_available

    if deepface_available is not False:
        try:
            from deepface import DeepFace

            deepface_available = True
        except ImportError:
            deepface_available = False

    if deepface_available:
        try:
            result = DeepFace.analyze(
                frame,
                actions=["emotion"],
                enforce_detection=False,
                silent=True,
            )

            if isinstance(result, list):
                result = result[0]

            emotions = result.get("emotion", {})
            dominant = result.get("dominant_emotion", "neutral")
            return (
                dominant,
                "DeepFace analysis",
                None,
                int(emotions.get(dominant, 0)),
            )
        except Exception:
            deepface_available = False

    expression, status, landmarks, confidence = mediapipe_expression(frame)
    if expression is not None:
        return expression, status, landmarks, confidence

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    smile_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_smile.xml"
    )
    faces = detect_face_boxes(frame)

    if len(faces) == 0:
        return "unknown", "Waiting for a visible face", None, 0

    x, y, width, height = max(faces, key=lambda box: box[2] * box[3])
    face_gray = gray[y:y + height, x:x + width]
    smiles = smile_cascade.detectMultiScale(
        face_gray,
        scaleFactor=1.7,
        minNeighbors=20,
        minSize=(25, 25),
    )

    if len(smiles) > 0:
        return "happy", "Smile detected with OpenCV", None, 70

    return "neutral", "Face detected with OpenCV", None, 55


# =========================
# GESTURE RECOGNITION
# =========================
def hand_search_region(frame, face_boxes):
    """Area around the person to zoom into before looking for a hand.

    An IP camera watches a room, so a raised hand can be a few percent of
    the frame - too small for the palm model to find. Cropping to the
    person and scaling that up puts the hand back at a size it can see.
    """
    if not face_boxes:
        return None

    height, width = frame.shape[:2]
    face_x, face_y, face_width, face_height = max(
        face_boxes,
        key=lambda box: box[2] * box[3],
    )

    if face_width >= width * GESTURE_ZOOM_FACE_RATIO:
        return None

    # Wide enough for an outstretched arm, and centred below the face where
    # hands are held. The frame's shape is kept so the finger geometry below
    # measures the same as it does on a full frame.
    region_width = min(
        float(width),
        max(face_width * GESTURE_ZOOM_SPAN, width * 0.25),
    )
    region_height = min(float(height), region_width * height / width)
    center_x = face_x + face_width / 2
    center_y = face_y + face_height * 1.8

    x1 = int(min(max(center_x - region_width / 2, 0), width - region_width))
    y1 = int(min(max(center_y - region_height / 2, 0), height - region_height))
    x2 = int(x1 + region_width)
    y2 = int(y1 + region_height)

    if x2 - x1 < 64 or y2 - y1 < 64:
        return None
    return x1, y1, x2, y2


def run_hand_model(hands, frame, region):
    if region is None:
        source = frame
    else:
        x1, y1, x2, y2 = region
        source = frame[y1:y2, x1:x2]

    rgb = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
    with mp_hands_lock:
        return hands.process(rgb)


def remap_landmarks_to_frame(hand_landmarks, region, width, height):
    """Put zoomed landmarks back into full frame space for drawing."""
    x1, y1, x2, y2 = region
    region_width = x2 - x1
    region_height = y2 - y1
    for landmark in hand_landmarks.landmark:
        landmark.x = (x1 + landmark.x * region_width) / width
        landmark.y = (y1 + landmark.y * region_height) / height


# (mcp, pip, tip) for each finger; the angle at the middle joint says
# whether the finger is straight.
FINGER_JOINTS = (
    ("index", 5, 6, 8),
    ("middle", 9, 10, 12),
    ("ring", 13, 14, 16),
    ("pinky", 17, 18, 20),
)


def joint_angle(point_a, point_b, point_c, width, height):
    """Angle at point_b in degrees, measured in picture pixels."""
    ax = (point_a.x - point_b.x) * width
    ay = (point_a.y - point_b.y) * height
    cx = (point_c.x - point_b.x) * width
    cy = (point_c.y - point_b.y) * height

    a_length = float(np.hypot(ax, ay))
    c_length = float(np.hypot(cx, cy))
    if a_length < 1e-6 or c_length < 1e-6:
        return 180.0

    cosine = (ax * cx + ay * cy) / (a_length * c_length)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def count_raised_fingers(landmarks, width, height):
    """How many fingers are held straight, whichever way the hand is turned.

    Joint angles do not change when the hand rotates, so a hand held
    sideways reads the same as one held upright. Measuring by distance from
    the wrist instead, as this used to, read every turned hand as an open
    palm and raised a help alert.
    """
    raised = [
        joint_angle(
            landmarks[mcp],
            landmarks[pip],
            landmarks[tip],
            width,
            height,
        ) >= FINGER_STRAIGHT_DEGREES
        for _name, mcp, pip, tip in FINGER_JOINTS
    ]

    # A tucked thumb bends at its own joint and folds in over the palm, so
    # it has to be both straight and reaching away from the little finger.
    thumb_straight = joint_angle(
        landmarks[2],
        landmarks[3],
        landmarks[4],
        width,
        height,
    ) >= THUMB_STRAIGHT_DEGREES

    def spread(point):
        return float(
            np.hypot(
                (point.x - landmarks[17].x) * width,
                (point.y - landmarks[17].y) * height,
            )
        )

    thumb_out = spread(landmarks[4]) > spread(landmarks[2]) * 1.15

    return raised, bool(thumb_straight and thumb_out)


def detect_gesture(frame, face_boxes=None):
    global gesture_zoom_misses
    global gesture_use_zoom

    hands, _ = get_mediapipe_models()
    if hands is None:
        return "none", "MediaPipe hand model is not available", None, 0

    height, width = frame.shape[:2]
    region = hand_search_region(frame, face_boxes) if gesture_use_zoom else None
    results = run_hand_model(hands, frame, region)

    if not results.multi_hand_landmarks:
        # Whichever way of looking works has to stick: a gesture only counts
        # after two passes in a row see it, so swapping every pass would
        # never let one settle. Swap only after a few empty passes.
        gesture_zoom_misses += 1
        if gesture_zoom_misses >= 3:
            gesture_zoom_misses = 0
            gesture_use_zoom = not gesture_use_zoom
        return "none", "Waiting for a visible hand", None, 0

    gesture_zoom_misses = 0
    hand_landmarks = results.multi_hand_landmarks[0]
    landmarks = hand_landmarks.landmark
    handedness = "Right"
    confidence = 0.0
    if results.multi_handedness:
        classification = results.multi_handedness[0].classification[0]
        handedness = classification.label
        confidence = float(classification.score)

    raised, thumb_raised = count_raised_fingers(landmarks, width, height)
    finger_count = sum(raised)

    # Just hold up fingers facing the camera. Counting cannot be confused by
    # which way the hand is turned, and every count is a different command.
    if finger_count >= 4:
        gesture = "help" if thumb_raised else "backward"
        label = "Open palm" if thumb_raised else "Four fingers"
    elif finger_count == 3:
        gesture = "right"
        label = "Three fingers"
    elif finger_count == 2:
        gesture = "left"
        label = "Two fingers"
    elif finger_count == 1:
        gesture = "follow"
        label = "One finger"
    else:
        gesture = "stop"
        label = "Closed fist"

    if region is not None:
        remap_landmarks_to_frame(hand_landmarks, region, width, height)

    status = (
        f"{label} ({finger_count} up, thumb "
        f"{'out' if thumb_raised else 'in'}); MediaPipe "
        f"{handedness.lower()} hand confidence {confidence:.0%}"
        f"{' (zoomed)' if region is not None else ''}"
    )
    return gesture, status, hand_landmarks, int(confidence * 100)


# =========================
# CAMERA LOOP
# =========================
def is_stream_source(camera_source):
    return isinstance(camera_source, str)


def mask_stream_url(url):
    """Hide the RTSP password before the URL is shown on the dashboard."""
    if "@" not in url or "//" not in url:
        return url

    scheme, _, rest = url.partition("//")
    credentials, _, host = rest.rpartition("@")
    if ":" in credentials:
        user, _, _password = credentials.partition(":")
        credentials = f"{user}:****"
    return f"{scheme}//{credentials}@{host}"


def describe_camera_source(camera_source):
    if is_stream_source(camera_source):
        return mask_stream_url(camera_source)
    return f"Device {camera_source}"


def open_stream_camera(stream_url):
    backends = [("FFmpeg", cv2.CAP_FFMPEG), ("Default", cv2.CAP_ANY)]

    errors = []
    for backend_name, backend in backends:
        cap = cv2.VideoCapture(stream_url, backend)
        if not cap.isOpened():
            cap.release()
            errors.append(f"{backend_name}: could not connect")
            continue

        # Keep only the newest frame so the analysis does not fall behind.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        for _ in range(50):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size:
                return cap, frame, backend_name
            time.sleep(0.1)

        cap.release()
        errors.append(f"{backend_name}: connected but returned no frames")

    return None, None, "; ".join(errors)


def scale_stream_frame(frame):
    """IP cameras often send 1080p, which is heavier than the loop needs."""
    height, width = frame.shape[:2]
    if width <= STREAM_MAX_WIDTH:
        return frame

    scale = STREAM_MAX_WIDTH / width
    return cv2.resize(
        frame,
        (STREAM_MAX_WIDTH, int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )


def reconnect_stream(cap, stream_url):
    """Network cameras drop out, so try to pick the stream back up."""
    if cap is not None:
        cap.release()

    for attempt in range(1, 4):
        if not state["camera_running"]:
            return None, None

        state["bot"]["cameraStatus"] = "Reconnecting"
        state["bot"]["cameraError"] = (
            f"Lost the IP camera stream. Reconnect attempt {attempt} of 3."
        )
        time.sleep(2)

        new_cap, frame, _backend_name = open_stream_camera(stream_url)
        if new_cap is not None:
            state["bot"]["cameraStatus"] = "Running"
            state["bot"]["cameraError"] = ""
            return new_cap, frame

    return None, None


def open_camera(camera_source):
    if is_stream_source(camera_source):
        return open_stream_camera(camera_source)

    camera_index = camera_source
    backends = []
    if CAMERA_BACKEND in {"auto", "dshow"} and os.name == "nt":
        backends.append(("DirectShow", cv2.CAP_DSHOW))
    if CAMERA_BACKEND in {"auto", "msmf"} and os.name == "nt":
        backends.append(("Media Foundation", cv2.CAP_MSMF))
    backends.append(("Default", cv2.CAP_ANY))

    errors = []
    for backend_name, backend in backends:
        cap = cv2.VideoCapture(camera_index, backend)
        if not cap.isOpened():
            cap.release()
            errors.append(f"{backend_name}: could not open")
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 24)

        for _ in range(12):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size:
                return cap, frame, backend_name
            time.sleep(0.05)

        cap.release()
        errors.append(f"{backend_name}: opened but returned no frames")

    return None, None, "; ".join(errors)


def stabilize_gesture(detected_gesture, detected_status):
    global gesture_candidate, gesture_candidate_count, gesture_miss_count

    if detected_gesture == "none":
        gesture_miss_count += 1
        if gesture_candidate_count >= GESTURE_HOLD_DEFAULT and gesture_miss_count <= 5:
            return gesture_candidate, "Gesture held through a brief tracking miss"
        if gesture_miss_count > 5:
            gesture_candidate = "none"
            gesture_candidate_count = 0
        return "none", detected_status

    gesture_miss_count = 0
    if detected_gesture == gesture_candidate:
        gesture_candidate_count += 1
    else:
        gesture_candidate = detected_gesture
        gesture_candidate_count = 1

    needed = GESTURE_HOLD_PASSES.get(detected_gesture, GESTURE_HOLD_DEFAULT)
    if gesture_candidate_count < needed:
        return "none", (
            f"Possible {detected_gesture}; hold steady "
            f"({gesture_candidate_count}/{needed})"
        )

    return detected_gesture, detected_status


def stabilize_recognition(name, relationship):
    global recognition_candidate
    global recognition_candidate_count
    global recognition_miss_count

    if name == "Unknown":
        recognition_miss_count += 1
        if recognition_candidate_count >= 2 and recognition_miss_count <= 8:
            return recognition_candidate
        if recognition_miss_count > 8:
            recognition_candidate = None
            recognition_candidate_count = 0
        return "Unknown", "Unknown"

    recognition_miss_count = 0
    identity = (name, relationship)
    if identity == recognition_candidate:
        recognition_candidate_count += 1
    else:
        recognition_candidate = identity
        recognition_candidate_count = 1

    if recognition_candidate_count < 2:
        return "Unknown", "Confirming face"

    if state["bot"]["faceMatchConfidence"] < 55:
        return "Unknown", "Low confidence"

    return identity


def stabilize_expression(expression, confidence):
    if expression == "unknown":
        expression_history.clear()
        return expression, confidence

    expression_history.append((expression, confidence))
    counts = Counter(item[0] for item in expression_history)
    stable_expression = counts.most_common(1)[0][0]
    stable_confidences = [
        item_confidence
        for item_expression, item_confidence in expression_history
        if item_expression == stable_expression
    ]
    return stable_expression, int(np.mean(stable_confidences))


def measure_fps(samples):
    """Frames per second across a rolling window of timestamps."""
    if len(samples) < 2:
        return 0
    span = samples[-1] - samples[0]
    if span <= 0:
        return 0
    return round((len(samples) - 1) / span, 1)


class CameraStream:
    """Reads frames in its own thread so the newest one is always ready.

    Detection is far slower than the camera, so a single read-analyse-draw
    loop makes an RTSP stream fall further behind on every pass. Reading
    here and dropping anything the readers did not pick up keeps the live
    view at the camera's own frame rate.
    """

    def __init__(self, cap, camera_source, source_label):
        self.cap = cap
        self.camera_source = camera_source
        self.source_label = source_label
        self.is_stream = is_stream_source(camera_source)
        self.condition = threading.Condition()
        self.frame = None
        self.raw_frame = None
        self.version = 0
        self.stopped = False
        self.thread = None

    def publish(self, raw_frame):
        frame = scale_stream_frame(raw_frame) if self.is_stream else raw_frame
        with self.condition:
            self.raw_frame = raw_frame
            self.frame = frame
            self.version += 1
            self.condition.notify_all()

    def start(self, first_frame):
        self.publish(first_frame)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self._read_frames()
        finally:
            self.cap.release()
            self._close()

    def _read_frames(self):
        read_times = deque(maxlen=40)

        while state["camera_running"] and not self.stopped:
            ok, frame = self.cap.read()

            if not ok or frame is None:
                if self.is_stream:
                    new_cap, frame = reconnect_stream(
                        self.cap,
                        self.camera_source,
                    )
                    if new_cap is None:
                        self._fail(
                            f"Lost the IP camera stream at "
                            f"{self.source_label} and could not reconnect."
                        )
                        return
                    self.cap = new_cap
                    read_times.clear()
                else:
                    self._fail("Camera stopped returning frames.")
                    return

            read_times.append(time.perf_counter())
            state["bot"]["cameraFps"] = measure_fps(read_times)
            self.publish(frame)

    def _fail(self, message):
        state["bot"]["cameraStatus"] = "Camera Error"
        state["bot"]["cameraError"] = message
        state["camera_running"] = False

    def _close(self):
        with self.condition:
            self.stopped = True
            self.condition.notify_all()

    def wait_for_frame(self, seen_version, timeout=1.0):
        """Block until a frame newer than seen_version is ready."""
        with self.condition:
            self.condition.wait_for(
                lambda: self.stopped or self.version != seen_version,
                timeout=timeout,
            )
            return self.frame, self.version

    def stop(self):
        self._close()
        if self.thread is not None:
            # An RTSP read blocks until the FFmpeg socket timeout, so give
            # the reader time to finish before the capture is released.
            self.thread.join(timeout=12)


def publish_display_frame(display_frame):
    global last_frame
    global last_frame_version

    ok, jpg = cv2.imencode(
        ".jpg",
        display_frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), 82],
    )
    if not ok:
        return

    with last_frame_ready:
        last_frame = jpg.tobytes()
        last_frame_version += 1
        last_frame_ready.notify_all()


def draw_overlay(display_frame, overlay):
    for face_x, face_y, face_width, face_height in overlay["face_boxes"]:
        cv2.rectangle(
            display_frame,
            (face_x, face_y),
            (face_x + face_width, face_y + face_height),
            (0, 255, 0),
            2,
        )

    hand_landmarks = overlay["hand_landmarks"]
    if mp is not None and hand_landmarks is not None:
        mp.solutions.drawing_utils.draw_landmarks(
            display_frame,
            hand_landmarks,
            mp.solutions.hands.HAND_CONNECTIONS,
            mp.solutions.drawing_styles.get_default_hand_landmarks_style(),
            mp.solutions.drawing_styles.get_default_hand_connections_style(),
        )

    cv2.putText(
        display_frame,
        state["bot"]["recognizedPerson"],
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
    )

    cv2.putText(
        display_frame,
        f"Emotion: {state['bot']['emotion']}",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 0),
        2,
    )

    cv2.putText(
        display_frame,
        f"Gesture: {state['bot']['gesture']}",
        (20, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 180, 0),
        2,
    )


def analysis_loop(stream, overlay):
    """Recognition, emotion and gesture work, off the display path."""
    global last_raw_frame
    global last_help_alert_at
    global last_announced_identity
    global last_identity_announcement_at
    global gesture_candidate
    global gesture_candidate_count
    global gesture_miss_count
    global recognition_candidate
    global recognition_candidate_count
    global recognition_miss_count
    global last_movement_at
    global last_gesture_direction
    global last_gesture_direction_at

    seen_version = 0
    detection_times = deque(maxlen=20)
    # Recognition, emotion and gesture are gated to at most ~10 passes a
    # second each, so running faster than this only starves the live view.
    min_pass_gap = 1 / max(ANALYSIS_TARGET_FPS, 1)
    last_pass_at = 0.0
    face_landmarks = None
    hand_landmarks = None
    face_boxes = []
    last_face_box_check = 0.0
    last_face_landmark_at = 0.0
    last_identity_check = 0.0
    last_expression_check = 0.0
    last_gesture_check = 0.0
    last_motion_check = 0.0
    previous_motion_gray = None
    remembered_face_boxes = []
    remembered_face_at = 0.0

    while state["camera_running"] and not stream.stopped:
        # Pace before picking a frame up, so detection always works on the
        # newest one rather than something held through the wait.
        ahead = min_pass_gap - (time.perf_counter() - last_pass_at)
        if ahead > 0:
            time.sleep(ahead)
        last_pass_at = time.perf_counter()

        frame, seen_version = stream.wait_for_frame(seen_version)
        if frame is None:
            continue

        with stream.condition:
            raw_frame = stream.raw_frame
        with last_frame_lock:
            last_raw_frame = raw_frame

        try:
            loop_started_at = time.perf_counter()
            now = time.monotonic()

            if now - last_motion_check >= 1.0:
                motion_gray = cv2.resize(
                    cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                    (160, 120),
                )
                if previous_motion_gray is not None:
                    motion_score = float(
                        np.mean(cv2.absdiff(motion_gray, previous_motion_gray))
                    )
                    if motion_score >= 2.2:
                        last_movement_at = time.time()
                        if state["vitals"]["activity"] == "no movement":
                            state["vitals"]["activity"] = "normal"
                    elif (
                        face_boxes
                        and time.time() - last_movement_at >= NO_MOVEMENT_SECONDS
                    ):
                        state["vitals"]["activity"] = "no movement"
                        trigger_automatic_alert(
                            "no_movement",
                            (
                                "No meaningful movement detected for "
                                f"{NO_MOVEMENT_SECONDS // 60} minute(s). "
                                "Please check the patient."
                            ),
                            cooldown_seconds=NO_MOVEMENT_SECONDS,
                        )
                previous_motion_gray = motion_gray
                last_motion_check = now

            if (
                now - last_face_landmark_at > 0.6
                and now - last_face_box_check >= 0.8
            ):
                mp_box = detect_face_with_mediapipe(frame)
                if mp_box is not None:
                    face_boxes = [mp_box]
                else:
                    face_boxes = detect_face_boxes(frame)
                last_face_box_check = now

            if now - last_identity_check >= 0.25:
                raw_name, raw_relation = recognize_face(frame, face_boxes)
                name, relation = stabilize_recognition(raw_name, raw_relation)
                state["bot"]["recognizedName"] = name
                state["bot"]["recognizedRelation"] = relation
                state["bot"]["recognizedPerson"] = (
                    "Unknown"
                    if name == "Unknown"
                    else f"{name} ({relation})"
                )
                last_identity_check = now

                identity = (name, relation)
                if (
                    name != "Unknown"
                    and (
                        identity != last_announced_identity
                        or time.time() - last_identity_announcement_at > 30
                    )
                ):
                    last_announced_identity = identity
                    last_identity_announcement_at = time.time()
                    message = f"This is your {relation}, {name}."
                    log_event("recognition", message)
                    speak_text(message)

            if now - last_expression_check >= 0.12:
                (
                    raw_emotion,
                    emotion_status,
                    face_landmarks,
                    emotion_confidence,
                ) = detect_emotion(frame)
                emotion, emotion_confidence = stabilize_expression(
                    raw_emotion,
                    emotion_confidence,
                )
                state["bot"]["emotion"] = emotion
                state["bot"]["emotionConfidence"] = emotion_confidence
                state["bot"]["emotionStatus"] = emotion_status
                if face_landmarks is not None:
                    landmark_box = face_box_from_landmarks(
                        face_landmarks,
                        frame.shape[1],
                        frame.shape[0],
                    )
                    if landmark_box is not None:
                        face_boxes = [landmark_box]
                        last_face_landmark_at = now
                elif raw_emotion == "unknown":
                    face_boxes = []
                last_expression_check = now

            if face_boxes:
                remembered_face_boxes = face_boxes
                remembered_face_at = now

            if now - last_gesture_check >= 0.10:
                # A distant face drops in and out of the mesh. Keep the last
                # position briefly so the hand search stays zoomed on the
                # person instead of falling back to the whole room.
                gesture_face_boxes = face_boxes
                if not gesture_face_boxes and now - remembered_face_at <= 3.0:
                    gesture_face_boxes = remembered_face_boxes

                (
                    raw_gesture,
                    raw_gesture_status,
                    hand_landmarks,
                    gesture_confidence,
                ) = detect_gesture(frame, gesture_face_boxes)
                gesture, gesture_status = stabilize_gesture(
                    raw_gesture,
                    raw_gesture_status,
                )
                state["bot"]["gesture"] = gesture
                state["bot"]["gestureConfidence"] = gesture_confidence
                state["bot"]["gestureStatus"] = gesture_status
                last_gesture_check = now

                if gesture == "help" and time.time() - last_help_alert_at > 15:
                    last_help_alert_at = time.time()
                    log_event("emergency", "Help gesture detected from patient.")

                gesture_direction = {
                    "follow": "F",
                    "backward": "B",
                    "left": "L",
                    "right": "R",
                    "stop": "S",
                }.get(gesture)
                if (
                    gesture_direction
                    and (
                        gesture_direction != last_gesture_direction
                        or time.time() - last_gesture_direction_at > 3
                    )
                ):
                    try:
                        set_firebase_direction(gesture_direction, f"gesture:{gesture}")
                        last_gesture_direction = gesture_direction
                        last_gesture_direction_at = time.time()
                        if gesture == "follow":
                            state["bot"]["followMe"] = True
                        elif gesture == "stop":
                            state["bot"]["followMe"] = False
                    except RuntimeError as error:
                        state["bot"]["gestureStatus"] = str(error)

                if gesture == "help":
                    if (
                        not distress_help_events
                        or time.time() - distress_help_events[-1] >= 3
                    ):
                        distress_help_events.append(time.time())
                    recent_help = [
                        event_time
                        for event_time in distress_help_events
                        if time.time() - event_time <= 30
                    ]
                    if (
                        state["bot"]["emotion"] in DISTRESSED_EMOTIONS
                        and len(recent_help) >= 2
                    ):
                        trigger_automatic_alert(
                            "distress_help",
                            (
                                "Distressed emotion "
                                f"({state['bot']['emotion']}) with repeated help "
                                "gestures detected."
                            ),
                            cooldown_seconds=60,
                        )

            state["bot"]["lastInteraction"] = datetime.now().strftime("%H:%M:%S")
            state["bot"]["analysisMs"] = round(
                (time.perf_counter() - loop_started_at) * 1000,
                1,
            )

            overlay["face_boxes"] = face_boxes
            overlay["hand_landmarks"] = hand_landmarks

        except Exception as error:  # noqa: BLE001
            state["bot"]["gestureStatus"] = f"Detection error: {error}"
            log_event("alert", f"Detection pass failed: {error}")
            time.sleep(0.5)

        detection_times.append(time.perf_counter())
        state["bot"]["detectionFps"] = measure_fps(detection_times)

    state["bot"]["detectionFps"] = 0


def camera_loop(camera_source):
    is_stream = is_stream_source(camera_source)
    source_label = describe_camera_source(camera_source)

    cap, frame, backend_name = open_camera(camera_source)

    if cap is None:
        if is_stream:
            message = (
                f"IP camera {source_label} failed. Check the RTSP URL, the "
                f"user name and password, and that the camera is on the same "
                f"network. {backend_name}"
            )
        else:
            message = (
                f"Camera {camera_source} failed. Close Windows Camera/Studio "
                f"apps and try another index. {backend_name}"
            )
        log_event("alert", message)
        state["camera_running"] = False
        state["bot"]["cameraStatus"] = "Camera Error"
        state["bot"]["cameraError"] = message
        return

    state["bot"]["cameraStatus"] = "Running"
    state["bot"]["cameraType"] = "ip" if is_stream else "webcam"
    state["bot"]["cameraSource"] = source_label
    if not is_stream:
        state["bot"]["cameraIndex"] = camera_source
    state["bot"]["cameraError"] = ""
    state["bot"]["lastInteraction"] = f"{source_label} via {backend_name}"
    state["bot"]["emotionStatus"] = "Looking for a face"
    state["bot"]["gestureStatus"] = "Looking for a hand"

    global last_movement_at
    global gesture_candidate
    global gesture_candidate_count
    global gesture_miss_count
    global recognition_candidate
    global recognition_candidate_count
    global recognition_miss_count

    last_movement_at = time.time()
    gesture_candidate = "none"
    gesture_candidate_count = 0
    gesture_miss_count = 0
    recognition_candidate = None
    recognition_candidate_count = 0
    recognition_miss_count = 0
    expression_history.clear()

    stream = CameraStream(cap, camera_source, source_label)
    stream.start(frame)

    overlay = {"face_boxes": [], "hand_landmarks": None}
    analysis_thread = threading.Thread(
        target=analysis_loop,
        args=(stream, overlay),
        daemon=True,
    )
    analysis_thread.start()

    seen_version = 0
    display_times = deque(maxlen=40)
    min_frame_gap = 1 / max(CAMERA_TARGET_FPS, 1)
    last_published_at = 0.0

    while state["camera_running"] and not stream.stopped:
        frame, seen_version = stream.wait_for_frame(seen_version)
        if frame is None:
            continue

        # Wait out the target frame gap rather than dropping the frame:
        # RTSP delivery is jittery, so skipping anything that arrives early
        # throws away frames the camera did send.
        ahead = min_frame_gap - (time.perf_counter() - last_published_at)
        if ahead > 0:
            time.sleep(ahead)
        last_published_at = time.perf_counter()

        display_frame = frame.copy()
        draw_overlay(display_frame, overlay)
        publish_display_frame(display_frame)

        display_times.append(last_published_at)
        state["bot"]["streamFps"] = measure_fps(display_times)

    state["camera_running"] = False
    if state["bot"]["cameraStatus"] != "Camera Error":
        state["bot"]["cameraStatus"] = "Stopping"
    analysis_thread.join(timeout=4)
    stream.stop()

    state["bot"]["cameraFps"] = 0
    state["bot"]["streamFps"] = 0
    state["bot"]["detectionFps"] = 0
    if state["bot"]["cameraStatus"] != "Camera Error":
        state["bot"]["cameraStatus"] = "Stopped"
    state["bot"]["emotionStatus"] = "Waiting for camera"
    state["bot"]["gestureStatus"] = "Waiting for camera"


# =========================
# API ROUTES
# =========================
@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.json or {}
    role = str(data.get("role", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    name = str(data.get("name", "")).strip()

    if role not in {"patient", "caregiver"}:
        return jsonify({"error": "Choose patient or caregiver."}), 400
    if not name or "@" not in email or len(password) < 6:
        return jsonify({
            "error": "Name, valid email, and a password of at least 6 characters are required.",
        }), 400

    users = read_json(USERS_JSON, [])
    if find_user_by_email(users, email):
        return jsonify({"error": "An account already exists for this email."}), 409

    user_id = next_id(users)
    user = {
        "id": user_id,
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": role,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    if role == "patient":
        patient_name = str(data.get("patientName", name)).strip() or name
        user.update({
            "link_code": secrets.token_hex(3).upper(),
            "caregiver_ids": [],
            "requested_caregiver_email": str(
                data.get("caregiverEmail", "")
            ).strip().lower(),
            "profile": {
                "patientName": patient_name,
                "age": str(data.get("age", "")).strip(),
                "disease": str(data.get("disease", "")).strip(),
                "medicalNotes": str(data.get("medicalNotes", "")).strip(),
                "emergencyNumber": str(
                    data.get("emergencyNumber", data.get("emergencyContact", ""))
                ).strip(),
                "emergencyContact": str(
                    data.get("emergencyContact", "")
                ).strip(),
                "locationAddress": str(data.get("locationAddress", "")).strip(),
            },
        })
    else:
        user["patient_ids"] = []
        user["profile"] = {
            "phone": str(data.get("phone", "")).strip(),
        }

    users.append(user)
    write_json(USERS_JSON, users)

    if role == "patient" and user.get("requested_caregiver_email"):
        caregiver = find_user_by_email(
            users,
            user["requested_caregiver_email"],
        )
        if caregiver and caregiver.get("role") == "caregiver":
            link_patient_and_caregiver(users, user, caregiver)
    elif role == "caregiver":
        changed = False
        for patient in users:
            if (
                patient.get("role") == "patient"
                and patient.get("requested_caregiver_email") == email
            ):
                patient.setdefault("caregiver_ids", []).append(user_id)
                user.setdefault("patient_ids", []).append(patient["id"])
                patient["requested_caregiver_email"] = ""
                changed = True
        if changed:
            write_json(USERS_JSON, users)

    token = create_session(user_id)
    if role == "patient":
        state["activePatientId"] = user_id
    response = jsonify({"ok": True, "user": public_user(user)})
    response.set_cookie(
        "carebot_session",
        token,
        httponly=True,
        samesite="Lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.json or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    users = read_json(USERS_JSON, [])
    user = find_user_by_email(users, email)

    if user is None or not check_password_hash(
        user.get("password_hash", ""),
        password,
    ):
        return jsonify({"error": "Incorrect email or password."}), 401

    if user.get("role") == "patient":
        state["activePatientId"] = int(user["id"])

    token = create_session(user["id"])
    response = jsonify({"ok": True, "user": public_user(user)})
    response.set_cookie(
        "carebot_session",
        token,
        httponly=True,
        samesite="Lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.route("/api/auth/me")
def auth_me():
    return jsonify({"user": public_user(g.current_user)})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    remove_session(request.cookies.get("carebot_session", ""))
    response = jsonify({"ok": True})
    response.delete_cookie("carebot_session")
    return response


@app.route("/api/caregivers")
def caregivers_list():
    patient_caregiver_ids = set(g.current_user.get("caregiver_ids", []))
    caregivers = [
        {
            "id": user["id"],
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("profile", {}).get("phone", ""),
            "speciality": user.get("profile", {}).get("speciality", ""),
            "demo": bool(user.get("demo", False)),
            "selected": int(user["id"]) in {
                int(value) for value in patient_caregiver_ids
            },
        }
        for user in read_json(USERS_JSON, [])
        if user.get("role") == "caregiver"
    ]
    return jsonify(caregivers)


@app.route("/api/patient/profile", methods=["GET", "PUT"])
def patient_profile():
    if g.current_user.get("role") != "patient":
        return jsonify({"error": "Patient access required."}), 403

    users = read_json(USERS_JSON, [])
    patient = find_user(users, g.current_user["id"])
    if request.method == "PUT":
        data = request.json or {}
        profile = patient.setdefault("profile", {})
        for field in [
            "patientName",
            "age",
            "disease",
            "medicalNotes",
            "emergencyNumber",
            "emergencyContact",
            "locationAddress",
        ]:
            if field in data:
                profile[field] = str(data[field]).strip()

        caregiver_id = data.get("caregiverId")
        caregiver_email = str(data.get("caregiverEmail", "")).strip().lower()
        caregiver = (
            find_user(users, caregiver_id)
            if caregiver_id is not None
            else find_user_by_email(users, caregiver_email)
            if caregiver_email
            else None
        )
        if caregiver_id is not None or caregiver_email:
            if caregiver is None or caregiver.get("role") != "caregiver":
                if caregiver_email:
                    patient["requested_caregiver_email"] = caregiver_email
                else:
                    return jsonify({"error": "Caregiver not found."}), 404
            else:
                link_patient_and_caregiver(users, patient, caregiver)
        write_json(USERS_JSON, users)

    return jsonify({"user": public_user(patient)})


@app.route("/api/caregiver/link", methods=["POST"])
def caregiver_link():
    if g.current_user.get("role") != "caregiver":
        return jsonify({"error": "Caregiver access required."}), 403

    link_code = str((request.json or {}).get("linkCode", "")).strip().upper()
    users = read_json(USERS_JSON, [])
    caregiver = find_user(users, g.current_user["id"])
    patient = next(
        (
            user
            for user in users
            if user.get("role") == "patient"
            and user.get("link_code", "").upper() == link_code
        ),
        None,
    )
    if patient is None:
        return jsonify({"error": "Patient link code was not found."}), 404

    link_patient_and_caregiver(users, patient, caregiver)
    return jsonify({"ok": True, "patient": public_user(patient)})


def alerts_for_patient_ids(patient_ids):
    allowed = {int(patient_id) for patient_id in patient_ids}
    return [
        alert
        for alert in read_json(CARE_ALERTS_JSON, [])
        if safe_int(alert.get("patient_id")) in allowed
    ]


def caregiver_can_access_patient(caregiver, patient_id):
    return int(patient_id) in {
        safe_int(value) for value in caregiver.get("patient_ids", [])
    }


def schedule_for_api(item):
    copied = dict(item)
    copied.setdefault("status", "pending")
    copied.setdefault("status_date", "")
    copied.setdefault("last_alert_date", "")
    return copied


def evaluate_missed_schedules(patient_id, schedules_data):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    changed = False

    for item in schedules_data:
        if safe_int(item.get("patient_id"), patient_id) != int(patient_id):
            continue
        if not item.get("enabled", 1) or item.get("type") != "medicine":
            continue
        if item.get("status_date") == today:
            continue

        try:
            due = datetime.strptime(
                f"{today} {item.get('time', '09:00')}",
                "%Y-%m-%d %H:%M",
            )
        except ValueError:
            continue

        if (now - due).total_seconds() < 30 * 60:
            continue

        item["status"] = "missed"
        item["status_date"] = today
        changed = True
        if item.get("last_alert_date") != today:
            item["last_alert_date"] = today
            log_event(
                "missed",
                (
                    f"Missed medicine: {item.get('title', 'Medicine')} "
                    f"({item.get('dose', 'dose not entered')}) scheduled at "
                    f"{item.get('time', '')}."
                ),
                patient_id=patient_id,
                severity="warning",
                source="schedule",
            )

    return changed


@app.route("/api/caregiver/patients")
def caregiver_patients():
    if g.current_user.get("role") != "caregiver":
        return jsonify({"error": "Caregiver access required."}), 403

    users = read_json(USERS_JSON, [])
    caregiver = find_user(users, g.current_user["id"])
    patient_ids = caregiver.get("patient_ids", [])
    schedules_data = read_json(SCHEDULES_JSON, [])
    schedules_changed = False
    for patient_id in patient_ids:
        schedules_changed = (
            evaluate_missed_schedules(patient_id, schedules_data)
            or schedules_changed
        )
    if schedules_changed:
        write_json(SCHEDULES_JSON, schedules_data)
    alerts = alerts_for_patient_ids(patient_ids)
    patients = []
    if patient_ids:
        sync_firebase_vitals(state.get("activePatientId") or patient_ids[0])
    for patient_id in patient_ids:
        patient = find_user(users, patient_id)
        if patient is None:
            continue
        patient_alerts = [
            alert for alert in alerts if int(alert["patient_id"]) == int(patient_id)
        ]
        live = int(state.get("activePatientId") or 0) == int(patient_id)
        patients.append({
            "user": public_user(patient),
            "vitals": state["vitals"] if live else None,
            "bot": state["bot"] if live else None,
            "active": live,
            "unacknowledgedAlerts": sum(
                not alert.get("acknowledged", False)
                for alert in patient_alerts
            ),
            "latestAlert": patient_alerts[0] if patient_alerts else None,
            "schedules": [
                schedule_for_api(item)
                for item in schedules_data
                if safe_int(item.get("patient_id"), patient_id)
                == int(patient_id)
            ],
            "tracking": patient_tracking_summary(patient_id),
        })
    demo_patients = [
        public_user(user)
        for user in users
        if user.get("role") == "patient"
        and user.get("demo")
        and int(user["id"]) not in {int(value) for value in patient_ids}
    ]
    return jsonify({
        "patients": patients,
        "alerts": alerts,
        "demoPatients": demo_patients,
        "caretakerLocation": caregiver.get("profile", {}).get("location"),
    })


@app.route(
    "/api/caregiver/patients/<int:patient_id>/schedules",
    methods=["GET", "POST"],
)
def caregiver_patient_schedules(patient_id):
    if g.current_user.get("role") != "caregiver":
        return jsonify({"error": "Caregiver access required."}), 403

    users = read_json(USERS_JSON, [])
    caregiver = find_user(users, g.current_user["id"])
    patient = find_user(users, patient_id)
    if (
        patient is None
        or patient.get("role") != "patient"
        or not caregiver_can_access_patient(caregiver, patient_id)
    ):
        return jsonify({"error": "Linked patient not found."}), 404

    schedules_data = read_json(SCHEDULES_JSON, [])
    if request.method == "POST":
        data = request.json or {}
        title = str(data.get("title", "")).strip()
        schedule_time = str(data.get("time", "")).strip()
        if not title or not schedule_time:
            return jsonify({"error": "Schedule title and time are required."}), 400

        item = {
            "id": next_id(schedules_data),
            "patient_id": patient_id,
            "created_by": int(g.current_user["id"]),
            "type": str(data.get("type", "medicine")).strip(),
            "title": title,
            "dose": str(data.get("dose", "")).strip(),
            "time": schedule_time,
            "enabled": 1,
            "status": "pending",
            "status_date": "",
            "last_alert_date": "",
        }
        schedules_data.append(item)
        write_json(SCHEDULES_JSON, schedules_data)
        log_event(
            "info",
            f"Caregiver scheduled {title} at {schedule_time}.",
            patient_id=patient_id,
        )

    if evaluate_missed_schedules(patient_id, schedules_data):
        write_json(SCHEDULES_JSON, schedules_data)

    return jsonify([
        schedule_for_api(item)
        for item in schedules_data
        if safe_int(item.get("patient_id"), patient_id) == patient_id
    ])


def last_track_point(patient_id):
    return next(
        (
            item
            for item in read_json(TRACK_LOG_JSON, [])
            if int(item.get("patient_id", 0)) == int(patient_id)
        ),
        None,
    )


def patient_tracking_summary(patient_id):
    """Fence, last position and distance, for one card on the caretaker page."""
    fence = geofence_for_patient(patient_id)
    point = last_track_point(patient_id)
    location = (
        {
            "lat": point["lat"],
            "lng": point["lng"],
            "accuracy": point.get("accuracy", 0),
            "updatedAt": point.get("created_at", ""),
        }
        if point
        else None
    )
    distance = haversine_meters(fence, location) if fence and location else None
    return {
        "fence": fence,
        "location": location,
        "mapUrl": google_maps_link(location) if location else "",
        "distance": round(distance, 1) if distance is not None else None,
        "inside": (distance <= fence["radius"]) if distance is not None else None,
        "source": point.get("source", "") if point else "",
    }


def last_known_location(patient_id):
    """The most recent position stored for a patient, fence checks aside."""
    point = last_track_point(patient_id)
    if not point:
        return None
    return {
        "lat": safe_float(point.get("lat"), 0),
        "lng": safe_float(point.get("lng"), 0),
        "accuracy": safe_float(point.get("accuracy"), 0),
        "updatedAt": point.get("created_at", ""),
    }


def track_point_age_seconds(point):
    try:
        stamp = datetime.fromisoformat(str(point.get("created_at", "")))
    except ValueError:
        return None
    return max(0.0, (datetime.now() - stamp).total_seconds())


def evaluate_geofence_now(patient_id, source="watchdog"):
    """Re-check the last known position against the safe zone.

    record_track_point only runs when the phone sends something, so a zone
    saved after the patient already wandered, or a phone that locks, runs flat
    or loses signal outside the zone, would never raise anything. This works
    from the position already on file, which covers both.
    """
    patient_id = int(patient_id)
    point = last_track_point(patient_id)
    location = last_known_location(patient_id)
    if location is None:
        return None

    fence_state = geofence_status(patient_id, location)
    fence = fence_state.get("fence")
    if fence is None:
        return fence_state

    users = read_json(USERS_JSON, [])
    patient = find_user(users, patient_id)
    if patient is None:
        return fence_state

    patient_name = (
        patient.get("profile", {}).get("patientName") or patient.get("name", "Patient")
    )
    age = track_point_age_seconds(point)
    age_note = ""
    if age is not None and age >= TRACK_STALE_SECONDS:
        age_note = (
            f" The phone last reported {int(age // 60)} minutes ago, "
            "so this may be out of date."
        )

    if fence_state.get("breached"):
        dispatch_emergency(
            patient_id,
            "geofence_breach",
            (
                f"{patient_name} is outside the safe zone "
                f"\"{fence['label']}\" at {fence_state['distance']:.0f} m "
                f"(allowed {fence['radius']:.0f} m).{age_note}"
            ),
            location=location,
            cooldown_seconds=0,
            source=source,
        )
    elif fence_state.get("returned"):
        log_event(
            "alert",
            f"{patient_name} is back inside the safe zone \"{fence['label']}\".",
            patient_id=patient_id,
            severity="info",
            source=source,
            location=location,
        )

    return fence_state


def geofence_watchdog():
    """Keep checking the safe zone even when the phone has gone quiet."""
    while True:
        time.sleep(GEOFENCE_WATCHDOG_SECONDS)
        try:
            for fence in read_json(GEOFENCES_JSON, []):
                evaluate_geofence_now(fence.get("patient_id"))
        except Exception as error:
            log_repeated_problem("geofence-watchdog", f"Geofence watchdog failed: {error}")


@app.route(
    "/api/caregiver/patients/<int:patient_id>/geofence",
    methods=["GET", "POST", "DELETE"],
)
def caregiver_patient_geofence(patient_id):
    """The caretaker draws the safe zone that the patient is measured against."""
    if g.current_user.get("role") != "caregiver":
        return jsonify({"error": "Caregiver access required."}), 403

    users = read_json(USERS_JSON, [])
    caregiver = find_user(users, g.current_user["id"])
    if not caregiver_can_access_patient(caregiver, patient_id):
        return jsonify({"error": "This patient is not linked to you."}), 403

    if request.method == "DELETE":
        write_json(
            GEOFENCES_JSON,
            [
                item
                for item in read_json(GEOFENCES_JSON, [])
                if int(item.get("patient_id", 0)) != int(patient_id)
            ],
        )
        geofence_state_by_patient.pop(int(patient_id), None)
        return jsonify({"ok": True, "fence": None})

    if request.method == "POST":
        saved = save_geofence(patient_id, request.json or {}, caregiver)
        if saved is None:
            return jsonify({
                "error": "A safe zone needs a valid latitude, longitude and radius.",
            }), 400
        log_event(
            "command",
            (
                f"{caregiver.get('name', 'Caregiver')} set the safe zone "
                f"\"{saved['label']}\" to {saved['radius']:.0f} m."
            ),
            patient_id=patient_id,
            source="caregiver",
        )
        # Judge the position already on file, so a zone drawn around a patient
        # who has already wandered alerts at once instead of waiting for the
        # next ping from a phone that may never send one.
        fence_state = evaluate_geofence_now(patient_id, source="caregiver")
        return jsonify({
            "ok": True,
            "fence": saved,
            "tracking": patient_tracking_summary(patient_id),
            "breached": bool(fence_state and fence_state.get("breached")),
        })

    return jsonify(patient_tracking_summary(patient_id))


@app.route("/api/caregiver/patients/<int:patient_id>/track")
def caregiver_patient_track(patient_id):
    if g.current_user.get("role") != "caregiver":
        return jsonify({"error": "Caregiver access required."}), 403

    users = read_json(USERS_JSON, [])
    caregiver = find_user(users, g.current_user["id"])
    if not caregiver_can_access_patient(caregiver, patient_id):
        return jsonify({"error": "This patient is not linked to you."}), 403

    points = [
        item
        for item in read_json(TRACK_LOG_JSON, [])
        if int(item.get("patient_id", 0)) == int(patient_id)
    ]
    return jsonify({**patient_tracking_summary(patient_id), "points": points[:100]})


@app.route("/api/caregiver/location", methods=["POST"])
def caregiver_location():
    """Store where the caretaker is, in Firebase and in the caretaker record."""
    if g.current_user.get("role") != "caregiver":
        return jsonify({"error": "Caregiver access required."}), 403

    location = normalize_location((request.json or {}).get("location"))
    if location is None:
        return jsonify({"error": "Valid latitude and longitude are required."}), 400

    users = read_json(USERS_JSON, [])
    caregiver = find_user(users, g.current_user["id"])
    caregiver.setdefault("profile", {})["location"] = location
    write_json(USERS_JSON, users)

    patient_ids = caregiver.get("patient_ids", [])
    written = write_firebase_caretaker_location(caregiver, location, patient_ids)

    nearest = {}
    for patient_id in patient_ids:
        summary = patient_tracking_summary(patient_id)
        if summary["location"]:
            nearest[str(patient_id)] = round(
                haversine_meters(location, summary["location"]),
                1,
            )

    return jsonify({
        "ok": True,
        "firebase": written,
        "location": location,
        "mapUrl": google_maps_link(location),
        "distanceToPatients": nearest,
    })


@app.route("/api/alerts/<int:alert_id>/acknowledge", methods=["POST"])
def acknowledge_alert(alert_id):
    user = g.current_user
    allowed_patient_ids = (
        user.get("patient_ids", [])
        if user.get("role") == "caregiver"
        else [user["id"]]
    )
    alerts = read_json(CARE_ALERTS_JSON, [])
    alert = next(
        (
            item
            for item in alerts
            if int(item.get("id", 0)) == alert_id
            and int(item.get("patient_id", 0))
            in {int(value) for value in allowed_patient_ids}
        ),
        None,
    )
    if alert is None:
        return jsonify({"error": "Alert not found."}), 404
    alert["acknowledged"] = True
    alert["acknowledged_at"] = datetime.now().isoformat(timespec="seconds")
    write_json(CARE_ALERTS_JSON, alerts)
    return jsonify({"ok": True})


@app.route("/api/health")
def health():
    return jsonify({
        "ok": True,
        "time": datetime.now().isoformat(timespec="seconds"),
        "python": sys.executable,
        "opencv": cv2.__version__,
        "opencvFace": hasattr(cv2, "face"),
        "mediapipe": mp is not None,
    })


@app.route("/api/status")
def status():
    patient_id = current_patient_id()
    sync_firebase_vitals(patient_id)
    fence = geofence_for_patient(patient_id)
    state["tracking"]["fence"] = fence
    if fence and state["tracking"].get("location"):
        state["tracking"]["distance"] = round(
            haversine_meters(fence, state["tracking"]["location"]),
            1,
        )
        state["tracking"]["inside"] = (
            state["tracking"]["distance"] <= fence["radius"] + GEOFENCE_EXIT_BUFFER
        )
    return jsonify(state)


@app.route("/detections")
@app.route("/api/detections")
def detections():
    bot_state = state["bot"]
    return jsonify({
        "cameraStatus": bot_state["cameraStatus"],
        "cameraType": bot_state["cameraType"],
        "cameraSource": bot_state["cameraSource"],
        "cameraFps": bot_state["cameraFps"],
        "streamFps": bot_state["streamFps"],
        "detectionFps": bot_state["detectionFps"],
        "recognizedPerson": bot_state["recognizedPerson"],
        "faceMatchConfidence": bot_state["faceMatchConfidence"],
        "emotion": bot_state["emotion"],
        "emotionConfidence": bot_state["emotionConfidence"],
        "emotionStatus": bot_state["emotionStatus"],
        "gesture": bot_state["gesture"],
        "gestureConfidence": bot_state["gestureConfidence"],
        "gestureStatus": bot_state["gestureStatus"],
        "gestureEngine": bot_state["gestureEngine"],
        "followMe": bot_state["followMe"],
        "direction": state["vitals"].get("direction", "S"),
        "emotionEngine": bot_state["emotionEngine"],
        "updatedAt": bot_state["lastInteraction"],
        "analysisMs": bot_state["analysisMs"],
    })


@app.route("/api/location", methods=["POST"])
def update_location():
    location = normalize_location((request.json or {}).get("location"))
    if not location:
        return jsonify({"error": "Valid latitude and longitude are required."}), 400

    # The dashboard shares the tracker pipeline, so a patient watching the
    # browser tab is geofenced exactly like one carrying the phone link.
    if g.current_user.get("role") == "patient":
        summary = record_track_point(g.current_user, location, "dashboard")
        return jsonify({"ok": True, "mapUrl": google_maps_link(location), **summary})

    state["bot"]["currentLocation"] = location
    state["bot"]["location"] = google_maps_link(location)
    state["activePatientId"] = current_patient_id()

    return jsonify({
        "ok": True,
        "location": location,
        "mapUrl": google_maps_link(location),
    })


# =========================
# PHONE TRACKER LINK
# =========================
@app.route("/api/track/link", methods=["GET", "POST"])
def track_link():
    """The link the patient opens on their phone to share live location."""
    if g.current_user.get("role") != "patient":
        return jsonify({"error": "Patient access required."}), 403

    users = read_json(USERS_JSON, [])
    patient = find_user(users, g.current_user["id"])
    if request.method == "POST" and (request.json or {}).get("reset"):
        patient["track_token"] = ""
    token = ensure_track_token(users, patient)

    return jsonify({
        "token": token,
        "url": tracker_link(token),
        "localUrl": tracker_link(token, "localhost"),
        "lanIp": lan_ip_address(),
        "secureLink": tracker_link(token).startswith("https://"),
        "publicUrl": public_tunnel_origin(),
        "lanUrl": (
            f"{frontend_scheme()}://{lan_ip_address()}:{FRONTEND_PORT}"
            f"/?panel=tracker&token={token}"
        ),
        "fence": geofence_for_patient(patient["id"]),
        "location": state["tracking"].get("location"),
    })


@app.route("/api/track/session")
def track_session():
    """Everything the phone page needs before it starts sending positions."""
    patient = find_user_by_track_token(request.args.get("token", ""))
    if patient is None:
        return jsonify({"error": "This tracking link is no longer valid."}), 404

    fence = geofence_for_patient(patient["id"])
    caregivers = [
        {
            "name": user.get("name", ""),
            "phone": user.get("profile", {}).get("phone", ""),
        }
        for user in read_json(USERS_JSON, [])
        if int(user.get("id", 0)) in {
            int(value) for value in patient.get("caregiver_ids", [])
        }
    ]
    return jsonify({
        "patientName": patient.get("profile", {}).get("patientName")
        or patient.get("name", "Patient"),
        "emergencyNumber": patient.get("profile", {}).get("emergencyNumber", ""),
        "fence": fence,
        "caregivers": caregivers,
        "location": state["tracking"].get("location"),
    })


@app.route("/api/track/ping", methods=["POST"])
def track_ping():
    data = request.json or {}
    patient = find_user_by_track_token(data.get("token", ""))
    if patient is None:
        return jsonify({"error": "This tracking link is no longer valid."}), 404

    summary = record_track_point(
        patient,
        data.get("location") or data,
        str(data.get("source", "phone")).strip() or "phone",
    )
    if summary is None:
        return jsonify({"error": "Valid latitude and longitude are required."}), 400

    return jsonify({"ok": True, **summary})


@app.route("/api/track/panic", methods=["POST"])
def track_panic():
    """The big help button on the phone page."""
    data = request.json or {}
    patient = find_user_by_track_token(data.get("token", ""))
    if patient is None:
        return jsonify({"error": "This tracking link is no longer valid."}), 404

    location = normalize_location(data.get("location"))
    patient_name = (
        patient.get("profile", {}).get("patientName") or patient.get("name", "Patient")
    )
    delivery = dispatch_emergency(
        patient["id"],
        "phone_panic",
        f"{patient_name} pressed the help button on the tracking phone.",
        location=location,
        cooldown_seconds=20,
        source="phone",
    )
    return jsonify({"ok": True, "delivery": delivery})


@app.route("/api/track/history")
def track_history():
    if g.current_user.get("role") == "caregiver":
        return jsonify({"error": "Use the caregiver tracking route."}), 403

    patient_id = int(g.current_user["id"])
    points = [
        item
        for item in read_json(TRACK_LOG_JSON, [])
        if int(item.get("patient_id", patient_id)) == patient_id
    ]
    return jsonify(points[:100])


# =========================
# GEOFENCE
# =========================
@app.route("/api/geofence", methods=["GET", "PUT", "DELETE"])
def patient_geofence():
    if g.current_user.get("role") != "patient":
        return jsonify({"error": "Patient access required."}), 403

    patient_id = int(g.current_user["id"])
    if request.method == "DELETE":
        write_json(
            GEOFENCES_JSON,
            [
                item
                for item in read_json(GEOFENCES_JSON, [])
                if int(item.get("patient_id", 0)) != patient_id
            ],
        )
        geofence_state_by_patient.pop(patient_id, None)
        return jsonify({"ok": True, "fence": None})

    if request.method == "PUT":
        saved = save_geofence(patient_id, request.json or {})
        if saved is None:
            return jsonify({
                "error": "A safe zone needs a valid latitude, longitude and radius.",
            }), 400
        log_event(
            "command",
            f"Safe zone \"{saved['label']}\" set to {saved['radius']:.0f} m.",
            patient_id=patient_id,
        )
        fence_state = evaluate_geofence_now(patient_id, source="patient")
        return jsonify({
            "ok": True,
            "fence": saved,
            "breached": bool(fence_state and fence_state.get("breached")),
        })

    return jsonify({
        "fence": geofence_for_patient(patient_id),
        "tracking": state["tracking"],
    })


@app.route("/api/emergency/reset", methods=["POST"])
def emergency_reset():
    """Clear the Firebase emergency flags once the caretaker has responded."""
    patient_id = current_patient_id()
    payload = {
        "Emergency": 0,
        "CallStatus": "Cleared",
        "SmsStatus": "Cleared",
        "Handled": True,
        "EmergencyResetAt": int(time.time() * 1000),
    }
    written = firebase_patch(firebase_node_url(), payload, "firebase-emergency-reset")
    if not written:
        return jsonify({"error": "Firebase did not accept the reset."}), 502

    geofence_state_by_patient.pop(int(patient_id or 0), None)
    log_event("command", "Emergency flags cleared in Firebase.", patient_id=patient_id)
    return jsonify({"ok": True, **payload})


@app.route("/api/emergency/test", methods=["POST"])
def emergency_test():
    """Check that the SMS and the voice call reach the emergency phone."""
    profile = current_patient_profile(current_patient_id())
    emergency_number = (
        profile.get("emergencyNumber") or profile.get("emergencyContact") or ""
    )
    numbers = alert_sms_numbers(emergency_number)
    location = normalize_location((request.json or {}).get("location"))
    message = build_sms_text(
        profile.get("patientName") or PATIENT_NAME or "Patient",
        "This is a test of the emergency SMS and call.",
        location or state["bot"].get("currentLocation"),
        emergency_number,
    )
    result = send_sms_and_call(numbers, message, detailed=True)
    result["firebaseOnly"] = not twilio_configured()
    return jsonify(result)


@app.route("/api/chat/<bot>", methods=["POST"])
def chat(bot):
    if bot not in {"patient", "family"}:
        return jsonify({
            "error": "Unknown chatbot. Use patient or family.",
        }), 404

    data = request.json or {}
    question = str(data.get("message", "")).strip()

    if not question:
        return jsonify({
            "error": "A message is required.",
        }), 400

    # A driving command beats the saved answers: "go left" should move the
    # robot, not look for a question about the word left.
    direction, phrase = parse_direction_command(question)
    sent_direction = None

    if direction:
        answer, ok = apply_direction_command(
            direction,
            f"chat:{bot}",
            spoken_as=phrase,
        )
        if ok:
            sent_direction = direction
    else:
        qa = patient_qa if bot == "patient" else family_qa
        answer = best_answer(question, qa)

    if data.get("speak", True):
        speak_text(answer)

    log_event("chat", f"{bot}: {question}")

    return jsonify({
        "answer": answer,
        "direction": sent_direction,
    })


@app.route("/api/speak", methods=["POST"])
def speak():
    data = request.json or {}
    text = data.get("text", "")
    saved_note = None

    if text:
        if data.get("save", False):
            saved_note = save_speech_note(text, source="speech")
        speak_text(text)
        log_event("voice", text)

    return jsonify({"ok": True, "note": saved_note})


@app.route("/api/notes", methods=["GET", "POST"])
def notes():
    patient_id = int(g.current_user["id"])
    notes_data = [
        item
        for item in read_json(SPEECH_NOTES_JSON, [])
        if safe_int(item.get("patient_id"), patient_id) == patient_id
    ]

    if request.method == "POST":
        data = request.json or {}
        item = save_speech_note(data.get("text", ""), patient_id, "manual")
        if item is None:
            return jsonify({"error": "Note text is required."}), 400
        log_event("note", "Saved caregiver speech note.", patient_id=patient_id)
        return jsonify({"ok": True, "note": item})

    return jsonify(notes_data[:25])


@app.route("/api/telegram/status")
def telegram_status_route():
    return jsonify(telegram_status())


@app.route("/api/telegram/test", methods=["POST"])
def telegram_test():
    data = request.json or {}
    message = data.get("message", "Test alert from Companion Care Bot")
    location = normalize_location(data.get("location"))
    if location:
        state["bot"]["currentLocation"] = location
    alert_location = location or state["bot"].get("currentLocation")
    location_link = google_maps_link(alert_location)
    if location_link:
        message = f"{message}\nCurrent location: {location_link}"
        if alert_location.get("accuracy"):
            message += f"\nAccuracy: {alert_location['accuracy']:.0f} meters"

    result = send_telegram(message, detailed=True)

    return jsonify(result)


@app.route("/api/direction", methods=["POST"])
def direction():
    data = request.json or {}
    direction_value = data.get("direction", "")

    try:
        saved_direction = set_firebase_direction(direction_value, "dashboard")
    except (ValueError, RuntimeError) as error:
        return jsonify({"error": str(error)}), 400

    log_event("command", f"Direction {saved_direction} sent to Firebase.")

    return jsonify({
        "ok": True,
        "direction": saved_direction,
    })


@app.route("/api/vitals", methods=["GET", "POST"])
def vitals():
    patient_id = int(g.current_user["id"])
    if request.method == "POST":
        data = request.json or {}
        apply_vitals_update(data, patient_id, "api")
    else:
        sync_firebase_vitals(patient_id, force=True)

    return jsonify(state["vitals"])


@app.route("/api/vitals/history")
def vitals_history():
    patient_id = int(g.current_user["id"])
    sync_firebase_vitals(patient_id)
    vitals_log = read_json(VITALS_JSON, [])
    vitals_log = [
        item
        for item in vitals_log
        if int(item.get("patient_id", patient_id)) == patient_id
    ]

    latest_30 = vitals_log[:30]

    return jsonify(latest_30[::-1])


@app.route("/api/relatives", methods=["GET", "POST"])
def relatives():
    patient_id = int(g.current_user["id"])
    state["activePatientId"] = patient_id

    if request.method == "POST":
        data = request.json or {}

        name = str(data.get("name", "")).strip()
        relationship = str(data.get("relationship", "")).strip()
        images = data.get("images", [])

        if not name or not relationship or not isinstance(images, list):
            return jsonify({
                "error": "name, relationship and five images are required",
            }), 400

        if len(images) != 5:
            return jsonify({
                "error": "Capture exactly five clear face photos.",
            }), 400

        relatives_data = read_json(RELATIVES_JSON, [])
        relative_id = next_id(relatives_data)
        safe_name = "".join(c for c in name if c.isalnum() or c in "_- ").strip()
        safe_name = safe_name.replace(" ", "_") or f"relative_{relative_id}"

        try:
            saved_paths = save_relative_images(relative_id, safe_name, images)
        except (ValueError, TypeError, base64.binascii.Error) as error:
            return jsonify({"error": str(error)}), 400

        duplicate = find_duplicate_relative(saved_paths, relatives_data)
        if duplicate is not None:
            for path in saved_paths:
                path.unlink(missing_ok=True)
            return jsonify({
                "error": (
                    "These photos match the already saved person "
                    f"{duplicate.get('name', 'Unknown')}. Capture a different person."
                ),
            }), 409

        item = {
            "id": relative_id,
            "patient_id": patient_id,
            "name": name,
            "relationship": relationship,
            "photo_paths": [str(path) for path in saved_paths],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

        relatives_data.insert(0, item)

        write_json(RELATIVES_JSON, relatives_data)
        trained = train_face_db()
        log_event(
            "info",
            f"Added relative {name} as {relationship} with five face photos.",
        )

        return jsonify({
            "ok": True,
            "trained": trained,
            "relative": relative_to_api(item),
        })

    relatives_data = [
        item
        for item in read_json(RELATIVES_JSON, [])
        if int(item.get("patient_id", patient_id)) == patient_id
    ]

    data = []

    for item in relatives_data:
        data.append(relative_to_api(item))

    return jsonify(data)


def relative_to_api(item):
    copied = dict(item)
    copied.pop("photo_path", None)
    copied.pop("photo_paths", None)
    photo_count = len(relative_photo_paths(item))
    copied["photoCount"] = photo_count
    copied["photoUrl"] = (
        f"/api/relatives/{copied['id']}/photos/0" if photo_count else ""
    )
    copied["photoUrls"] = [
        f"/api/relatives/{copied['id']}/photos/{index}"
        for index in range(photo_count)
    ]
    return copied


def find_relative(relatives_data, relative_id):
    return next(
        (
            item
            for item in relatives_data
            if int(item.get("id", 0)) == int(relative_id)
        ),
        None,
    )


@app.route("/api/relatives/<int:rid>", methods=["PUT", "DELETE"])
def relative_detail(rid):
    relatives_data = read_json(RELATIVES_JSON, [])
    found = find_relative(relatives_data, rid)

    if (
        not found
        or int(found.get("patient_id", g.current_user["id"]))
        != int(g.current_user["id"])
    ):
        return jsonify({"error": "Relative not found."}), 404

    if request.method == "DELETE":
        delete_relative_images(found)
        relatives_data = [
            item for item in relatives_data if int(item.get("id", 0)) != rid
        ]
        write_json(RELATIVES_JSON, relatives_data)
        trained = train_face_db()
        log_event("info", f"Deleted relative {found.get('name', rid)}.")
        return jsonify({"ok": True, "trained": trained})

    data = request.json or {}
    name = str(data.get("name", found.get("name", ""))).strip()
    relationship = str(
        data.get("relationship", found.get("relationship", ""))
    ).strip()
    images = data.get("images")

    if not name or not relationship:
        return jsonify({"error": "Name and relationship are required."}), 400

    replacement_paths = None
    if images is not None:
        if not isinstance(images, list) or len(images) != 5:
            return jsonify({
                "error": "Capture exactly five photos to replace face training.",
            }), 400

        safe_name = "".join(
            character
            for character in name
            if character.isalnum() or character in "_- "
        ).strip()
        safe_name = safe_name.replace(" ", "_") or f"relative_{rid}"

        try:
            replacement_paths = save_relative_images(rid, safe_name, images)
        except (ValueError, TypeError, base64.binascii.Error) as error:
            return jsonify({"error": str(error)}), 400

        duplicate = find_duplicate_relative(
            replacement_paths,
            relatives_data,
            exclude_id=rid,
        )
        if duplicate is not None:
            for path in replacement_paths:
                path.unlink(missing_ok=True)
            return jsonify({
                "error": (
                    "These photos match the already saved person "
                    f"{duplicate.get('name', 'Unknown')}."
                ),
            }), 409

    if replacement_paths is not None:
        delete_relative_images(found)
        found.pop("photo_path", None)
        found["photo_paths"] = [str(path) for path in replacement_paths]

    found["name"] = name
    found["relationship"] = relationship
    found["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_json(RELATIVES_JSON, relatives_data)
    trained = train_face_db()
    log_event("info", f"Updated relative {name} as {relationship}.")

    return jsonify({
        "ok": True,
        "trained": trained,
        "relative": relative_to_api(found),
    })


@app.route("/api/relatives/<int:rid>/photo")
def relative_photo_legacy(rid):
    return relative_photo(rid, 0)


@app.route("/api/relatives/<int:rid>/photos/<int:photo_index>")
def relative_photo(rid, photo_index):
    relatives_data = read_json(RELATIVES_JSON, [])
    found = find_relative(relatives_data, rid)

    if (
        not found
        or int(found.get("patient_id", g.current_user["id"]))
        != int(g.current_user["id"])
    ):
        return "Not found", 404

    photo_paths = relative_photo_paths(found)
    if photo_index < 0 or photo_index >= len(photo_paths):
        return "Photo not found", 404

    photo_path = photo_paths[photo_index]

    if not photo_path.exists():
        return "Photo not found", 404

    return Response(photo_path.read_bytes(), mimetype="image/jpeg")


@app.route("/api/train-faces", methods=["POST"])
def train_faces():
    state["activePatientId"] = int(g.current_user["id"])
    count = train_face_db()

    return jsonify({
        "ok": True,
        "trained": count,
        "pkl": str(PKL_PATH),
    })


@app.route("/api/camera/start", methods=["POST"])
def camera_start():
    data = request.json or {}
    state["activePatientId"] = int(g.current_user["id"])
    camera_type = str(data.get("cameraType", "webcam")).strip().lower()

    if camera_type not in {"webcam", "ip"}:
        return jsonify({"error": "Camera type must be webcam or ip."}), 400

    if state["bot"]["cameraStatus"] == "Stopping":
        return jsonify({
            "error": "The previous camera is still closing. Try again in a "
                     "few seconds.",
        }), 409

    camera_index = CAMERA_INDEX
    if camera_type == "ip":
        stream_url = str(data.get("rtspUrl") or CAMERA_RTSP_URL).strip()
        if not stream_url:
            return jsonify({
                "error": "Enter the IP camera URL, for example "
                         "rtsp://user:password@192.168.1.57:554/stream.",
            }), 400
        if not stream_url.lower().startswith(STREAM_PREFIXES):
            return jsonify({
                "error": "The IP camera URL must start with rtsp://, rtsps://, "
                         "http:// or https://.",
            }), 400
        camera_source = stream_url
        starting_message = (
            "Connecting to the IP camera. This can take 5-10 seconds."
        )
    else:
        try:
            camera_index = int(data.get("cameraIndex", CAMERA_INDEX))
        except (TypeError, ValueError):
            return jsonify({"error": "Camera index must be a number."}), 400

        if camera_index < 0 or camera_index > 9:
            return jsonify({
                "error": "Camera index must be between 0 and 9.",
            }), 400
        camera_source = camera_index
        starting_message = (
            "Opening the Windows camera. This can take 5-8 seconds."
        )

    if not state["camera_running"]:
        state["camera_running"] = True
        state["bot"]["cameraStatus"] = "Starting"
        state["bot"]["cameraType"] = camera_type
        state["bot"]["cameraSource"] = describe_camera_source(camera_source)
        state["bot"]["cameraError"] = starting_message
        threading.Thread(
            target=camera_loop,
            args=(camera_source,),
            daemon=True,
        ).start()

    return jsonify({
        "ok": True,
        "cameraType": camera_type,
        "cameraIndex": camera_index,
        "cameraSource": state["bot"]["cameraSource"],
    })


@app.route("/api/camera/stop", methods=["POST"])
def camera_stop():
    state["camera_running"] = False

    return jsonify({
        "ok": True,
    })


@app.route("/api/camera/snapshot")
def camera_snapshot():
    with last_frame_lock:
        image = last_raw_frame

    if image is None:
        return jsonify({
            "error": "No camera frame is available. Start the camera first.",
        }), 409

    # The full size frame is kept as-is and only encoded when a photo is
    # actually taken, so the live loop never pays for it.
    encoded_ok, raw_jpg = cv2.imencode(
        ".jpg",
        image,
        [int(cv2.IMWRITE_JPEG_QUALITY), 92],
    )
    if not encoded_ok:
        return jsonify({
            "error": "Could not read a photo from the camera frame.",
        }), 409

    frame = raw_jpg.tobytes()
    mp_box = detect_face_with_mediapipe(image)
    faces = [mp_box] if mp_box is not None else detect_face_boxes_raw(image)
    if len(faces) != 1:
        message = (
            "No clear face detected. Face the camera with good lighting."
            if not faces
            else "More than one face detected. Keep only one person in frame."
        )
        return jsonify({"error": message, "faces": len(faces)}), 422

    encoded = base64.b64encode(frame).decode("ascii")
    return jsonify({
        "ok": True,
        "image": f"data:image/jpeg;base64,{encoded}",
        "faces": 1,
    })


@app.route("/api/face-model/status")
def face_model_status():
    face_db = load_face_db()
    relative_ids = face_db.get("relative_ids", [])
    return jsonify({
        "engine": face_db.get("engine", "unknown"),
        "trainedSamples": len(face_db.get("encodings", [])),
        "identities": len(set(relative_ids)),
        "ambiguousIdentities": len(
            face_db.get("ambiguous_relative_ids", [])
        ),
        "recommendedSamplesPerIdentity": 5,
    })


@app.route("/api/video-feed")
def video_feed():
    def generate():
        seen_version = -1

        while True:
            with last_frame_ready:
                # Push each new frame as soon as the renderer publishes it
                # instead of polling on a fixed sleep.
                last_frame_ready.wait_for(
                    lambda: last_frame_version != seen_version,
                    timeout=1.0,
                )
                frame = last_frame
                seen_version = last_frame_version

            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/api/schedules", methods=["GET", "POST"])
def schedules():
    patient_id = int(g.current_user["id"])
    schedules_data = read_json(SCHEDULES_JSON, [])

    legacy_changed = False
    for item in schedules_data:
        if item.get("patient_id") is None:
            item["patient_id"] = patient_id
            legacy_changed = True

    if request.method == "POST":
        data = request.json or {}

        item = {
            "id": next_id(schedules_data),
            "patient_id": patient_id,
            "created_by": patient_id,
            "type": data.get("type", "medicine"),
            "title": data.get("title", "Medicine"),
            "dose": data.get("dose", ""),
            "time": data.get("time", "09:00"),
            "enabled": 1,
            "status": "pending",
            "status_date": "",
            "last_alert_date": "",
        }

        schedules_data.append(item)
        schedules_data = sorted(schedules_data, key=lambda x: x.get("time", ""))

        write_json(SCHEDULES_JSON, schedules_data)

        log_event("info", f"Schedule added: {item['title']}")

        return jsonify({
            "ok": True,
            "schedule": schedule_for_api(item),
        })

    if evaluate_missed_schedules(patient_id, schedules_data):
        legacy_changed = True
    if legacy_changed:
        write_json(SCHEDULES_JSON, schedules_data)

    patient_schedules = [
        item
        for item in schedules_data
        if safe_int(item.get("patient_id"), patient_id) == patient_id
    ]

    patient_schedules = sorted(
        patient_schedules,
        key=lambda x: x.get("time", ""),
    )

    return jsonify([schedule_for_api(item) for item in patient_schedules])


@app.route("/api/schedules/<int:schedule_id>/status", methods=["POST"])
def schedule_status(schedule_id):
    patient_id = int(g.current_user["id"])
    status_value = str((request.json or {}).get("status", "")).strip().lower()
    if status_value not in {"taken", "missed", "pending"}:
        return jsonify({"error": "Use taken, missed, or pending."}), 400

    schedules_data = read_json(SCHEDULES_JSON, [])
    item = next(
        (
            schedule
            for schedule in schedules_data
            if safe_int(schedule.get("id")) == schedule_id
            and safe_int(schedule.get("patient_id"), patient_id) == patient_id
        ),
        None,
    )
    if item is None:
        return jsonify({"error": "Schedule not found."}), 404

    today = datetime.now().strftime("%Y-%m-%d")
    item["status"] = status_value
    item["status_date"] = today if status_value != "pending" else ""
    if status_value == "taken":
        log_event(
            "medicine",
            f"Medicine taken: {item.get('title', 'Medicine')}.",
            patient_id=patient_id,
        )
    elif status_value == "missed":
        item["last_alert_date"] = today
        log_event(
            "missed",
            (
                f"Patient marked medicine as missed: "
                f"{item.get('title', 'Medicine')} at {item.get('time', '')}."
            ),
            patient_id=patient_id,
            severity="warning",
            source="schedule",
        )

    write_json(SCHEDULES_JSON, schedules_data)
    return jsonify({"ok": True, "schedule": schedule_for_api(item)})


@app.route("/api/command", methods=["POST"])
def command():
    data = request.json or {}
    cmd = data.get("command", "")
    direction_map = {
        "forward": "F",
        "backward": "B",
        "left": "L",
        "right": "R",
        "stop": "S",
    }

    state["bot"]["lastInteraction"] = f"Command: {cmd}"

    if cmd == "Follow Me ON":
        state["bot"]["followMe"] = True
        try:
            set_firebase_direction("F", "command")
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 400

    elif cmd == "Follow Me OFF":
        state["bot"]["followMe"] = False
        try:
            set_firebase_direction("S", "command")
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 400

    elif str(cmd).lower() in direction_map:
        try:
            set_firebase_direction(direction_map[str(cmd).lower()], "command")
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 400

    elif cmd.lower() in ["go to patient", "play calming music", "start video call"]:
        speak_text(cmd)

    elif cmd.lower() == "emergency alert":
        patient_condition = str(
            data.get("patientCondition")
            or "Patient has fallen and is unconscious"
        ).strip()
        log_event(
            "emergency",
            patient_condition,
            location=data.get("location"),
        )

    log_event("command", cmd)

    return jsonify({
        "ok": True,
    })


@app.route("/api/logs")
def logs():
    logs_data = read_json(LOGS_JSON, [])
    patient_id = int(g.current_user["id"])
    return jsonify([
        item
        for item in logs_data
        if safe_int(item.get("patient_id"), patient_id) == patient_id
    ][:50])


@app.route("/api/demo/tick", methods=["POST"])
def demo_tick():
    v = state["vitals"]

    demo = {
        "heartRate": int(np.clip(v["heartRate"] + np.random.randint(-3, 4), 65, 120)),
        "spo2": int(np.clip(v["spo2"] + np.random.randint(-1, 2), 90, 100)),
        "temperature": round(
            float(np.clip(v["temperature"] + np.random.uniform(-0.1, 0.1), 36.0, 38.5)),
            1,
        ),
        "activity": np.random.choice(["normal", "walking", "resting"]).item(),
    }

    with app.test_request_context(json=demo):
        return vitals()


# =========================
# MAIN
# =========================
def print_startup_banner():
    """Say clearly that the server is up.

    MediaPipe prints several W0000 warning lines while it loads its models.
    They are normal and they are the last thing on screen otherwise, which
    makes a healthy start look like a crash.
    """
    print()
    print("=" * 62)
    print("  Companion Care Bot backend is running.")
    print("  Local:    http://localhost:5000")
    print(f"  Network:  http://{lan_ip_address()}:5000")
    print(f"  Tracking: {tracker_link('<patient token>')}")
    print("  The MediaPipe W0000 lines above are normal startup noise.")
    print("  Press Ctrl+C to stop.")
    print("=" * 62)
    print()


def port_in_use(port=5000):
    """A second backend cannot bind port 5000, so say so in plain words."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return probe.connect_ex(("127.0.0.1", port)) == 0
    finally:
        probe.close()


if __name__ == "__main__":
    init_storage()
    if port_in_use(5000):
        print(
            "\nPort 5000 is already taken, so this backend cannot start.\n"
            "Another Companion Care Bot is already running. Close that"
            " window and start this one again.\n"
        )
        sys.exit(1)

    log_event("info", "Companion Care Bot backend started without SQLite.")
    threading.Thread(target=warmup_mediapipe_models, daemon=True).start()
    threading.Thread(target=geofence_watchdog, daemon=True).start()
I Software, our I Go to the... go to the... go to the... go to the... go to the... Go Yeah, I don't know, probably, but I don't really know. But I'm going to keep on the hotspot now, man. First day, come on.
Mardi. Your mobile ID is not working. Name, password, and Now, from the software side, I The way I was raised, I was raised in a family of 3.    try:
        from waitress import serve
    except ImportError:
        print(
            "Waitress is not installed for this Python interpreter. "
            "Using Flask fallback. Run ..\\start-backend.ps1 for the "
            "configured environment."
        )
        try:
            print_startup_banner()
            app.run(
                host="0.0.0.0",
                port=5000,
                debug=False,
                use_reloader=False,
                threaded=True,
            )
        except KeyboardInterrupt:
            pass
    else:
        try:
            print_startup_banner()
            serve(app, host="0.0.0.0", port=5000, threads=8)
        except KeyboardInterrupt:
            pass

    state["camera_running"] = False
    print("\nCompanion Care Bot backend stopped.")
