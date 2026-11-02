import json
from pathlib import Path

from werkzeug.security import generate_password_hash


DATA_DIR = Path(__file__).resolve().parent / "data"
USERS_PATH = DATA_DIR / "users.json"
CREDENTIALS_PATH = DATA_DIR / "login-credentials.local.json"

DEFAULT_PASSWORDS = {
    "dasrhan@gmail.com": "Patient@123",
    "ac@gmail.com": "Caregiver@123",
    "darshan@gmaill.com": "Patient2@123",
}
DEMO_PASSWORD = "demo123"


def main():
    users = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    credentials = []

    for user in users:
        email = user["email"]
        password = (
            DEMO_PASSWORD
            if user.get("demo")
            else DEFAULT_PASSWORDS.get(email, "CareBot@123")
        )
        user["password_hash"] = generate_password_hash(password)
        credentials.append({
            "name": user.get("name", ""),
            "role": user.get("role", ""),
            "email": email,
            "password": password,
            "demo": bool(user.get("demo", False)),
        })

    USERS_PATH.write_text(
        json.dumps(users, indent=2),
        encoding="utf-8",
    )
    CREDENTIALS_PATH.write_text(
        json.dumps(credentials, indent=2),
        encoding="utf-8",
    )
    print(f"Updated {len(users)} account password(s).")
    print(f"Copy-paste credentials: {CREDENTIALS_PATH}")


if __name__ == "__main__":
    main()
