import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_all_owners():
    response = supabase.table("owners").select("*").execute()
    return response.data


def save_captured_image(image_url: str, status: str):
    try:
        print("📝 Inserting into captured_images...")

        payload = {
            "image_url": image_url,
            "status": status
        }
        print("Payload:", payload)

        response = supabase.table("captured_images").insert(payload).execute()

        print("✅ captured_images insert response:", response.data)
        return response.data

    except Exception as e:
        print("❌ captured_images INSERT ERROR:", str(e))
        raise e


def create_alert(title: str, image_url: str = None):
    try:
        print("🚨 Inserting into alerts...")

        payload = {
            "type": "unrecognizedSubject",
            "title": title,
            "device_id": "AuthShield-X-9000",
            "image_url": image_url,
            "dismissed": False,
            "lockout_initiated": False,
            "camera_id": "CAM_01_ENTRY"
        }
        print("Payload:", payload)

        response = supabase.table("alerts").insert(payload).execute()

        print("✅ alerts insert response:", response.data)
        return response.data

    except Exception as e:
        print("❌ alerts INSERT ERROR:", str(e))
        raise e


def upload_image_to_storage(file_path: str, file_name: str):
    try:
        print("📤 Starting upload to Supabase Storage...")
        print("File path:", file_path)
        print("File name:", file_name)

        if not os.path.exists(file_path):
            raise Exception("File does not exist before upload")

        file_size = os.path.getsize(file_path)
        print("📏 File size before upload:", file_size)

        if file_size == 0:
            raise Exception("File is empty before upload")

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        response = supabase.storage.from_("captured-images").upload(
            path=file_name,
            file=file_bytes,
            file_options={"content-type": "image/jpeg"}
        )

        print("✅ Upload response:", response)

        public_url = supabase.storage.from_("captured-images").get_public_url(file_name)
        print("🌍 Public URL:", public_url)

        return public_url

    except Exception as e:
        print("❌ STORAGE UPLOAD ERROR:", str(e))
        raise e


# Fetch latest saved device token from Supabase
def get_latest_device_token():
    try:
        print("📲 Fetching latest FCM device token from Supabase...")

        response = (
            supabase.table("device_tokens")
            .select("fcm_token, updated_at")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )

        data = response.data

        if data and len(data) > 0:
            token = data[0]["fcm_token"]
            print("✅ Latest device token fetched")
            return token

        print("⚠ No device token found in Supabase")
        return None

    except Exception as e:
        print("❌ DEVICE TOKEN FETCH ERROR:", str(e))
        return None


# 🔐 SAFE keypad password fetch
def get_keypad_password():
    try:
        print("🔐 Fetching keypad password from Supabase settings...")

        response = (
            supabase.table("settings")
            .select("*")
            .eq("key", "keypad_password")
            .limit(1)
            .execute()
        )

        data = response.data

        if data and len(data) > 0:
            row = data[0]

            password = (
                row.get("value")
                or row.get("password")
                or "1234"
            )

            print("✅ Keypad password fetched:", password)
            return str(password)

        return "1234"

    except Exception as e:
        print("❌ KEYPAD PASSWORD FETCH ERROR:", str(e))
        return "1234"


# ✅ 👉 ADD THIS FUNCTION HERE (BOTTOM OF FILE)
def update_keypad_password(new_password: str):
    try:
        print("🔐 Updating keypad password in Supabase...")

        response = (
            supabase.table("settings")
            .update({"value": new_password})
            .eq("key", "keypad_password")
            .execute()
        )

        if not response.data:
            print("⚠ No existing row, inserting new one...")

            supabase.table("settings").insert({
                "key": "keypad_password",
                "value": new_password   # ✅ FIXED
            }).execute()

        print("✅ Password updated successfully")
        return True

    except Exception as e:
        print("❌ PASSWORD UPDATE ERROR:", str(e))
        return False