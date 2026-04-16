from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from supabase_service import update_keypad_password
import shutil
import os
import uuid
import json

import firebase_admin
from firebase_admin import credentials, messaging

from face_service import (
    get_face_encoding_from_file,
    get_face_encoding_from_url,
    compare_faces
)
from supabase_service import (
    get_all_owners,
    create_alert,
    save_captured_image,
    upload_image_to_storage,
    get_latest_device_token,
    get_keypad_password
)

# ================= FIREBASE INIT =================
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_ADMIN_JSON")

    if firebase_json:
        print("🔥 Using FIREBASE_ADMIN_JSON from environment")
        cred = credentials.Certificate(json.loads(firebase_json))
    else:
        print("📁 Using local firebase_admin_key.json")
        cred = credentials.Certificate("firebase_admin_key.json")

    firebase_admin.initialize_app(cred)

# ================= FASTAPI APP =================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "temp_uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= PUSH FUNCTION =================
def send_push_notification(title: str, body: str):
    try:
        token = get_latest_device_token()

        if not token:
            print("❌ No device token found in Supabase")
            return

        print("📲 Sending push to latest saved device token...")

        message = messaging.Message(
        token=token,

        # ✅ THIS MAKES NOTIFICATION VISIBLE
        notification=messaging.Notification(
            title=title,
            body=body,
        ),

        # (optional, keep data if needed)
        data={
            "type": "intrusion"
        },

        android=messaging.AndroidConfig(
            priority="high",
        ),
    )

        response = messaging.send(message)
        print("🔥 Push notification sent:", response)

    except Exception as e:
        print("❌ Failed to send push notification:", str(e))


# ================= ROUTES =================
@app.get("/")
def home():
    return {"message": "AuthShield Face Backend Running"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "AuthShield Backend"}


# Fetch latest keypad password for ESP32
# Fetch latest keypad password for ESP32
@app.get("/device-password")
def device_password():
    try:
        password = get_keypad_password()

        return {
            "success": True,
            "password": password
        }

    except Exception as e:
        return {
            "success": False,
            "password": "1234",
            "message": str(e)
        }


# ✅ 👉 ADD THIS HERE (RIGHT BELOW)
from fastapi import Body

@app.post("/device-password")
def update_device_password(data: dict = Body(...)):
    try:
        password = data.get("password")

        if not password:
            return {
                "success": False,
                "message": "Password not provided"
            }

        from supabase_service import update_keypad_password
        result = update_keypad_password(password)

        if result:
            return {
                "success": True   # ✅ IMPORTANT
            }
        else:
            return {
                "success": False
            }

    except Exception as e:
        print("❌ ERROR:", str(e))
        return {
            "success": False,
            "message": str(e)
        }


# ================= FACE VERIFICATION =================
@app.post("/verify-face")
async def verify_face(file: UploadFile = File(...)):
    temp_filename = f"{uuid.uuid4()}_{file.filename}"
    temp_file_path = os.path.join(UPLOAD_FOLDER, temp_filename)

    try:
        print("\n================ VERIFY FACE REQUEST ================")
        print("Received file:", file.filename)
        print("Content type:", file.content_type)

        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not os.path.exists(temp_file_path):
            return {
                "success": False,
                "matched": False,
                "message": "Image file was not saved"
            }

        file_size = os.path.getsize(temp_file_path)
        print("Saved temp file:", temp_file_path)
        print("Image size:", file_size, "bytes")

        if file_size == 0:
            return {
                "success": False,
                "matched": False,
                "message": "Captured image is empty"
            }

        unknown_encoding = get_face_encoding_from_file(temp_file_path)

        if unknown_encoding is None:
            print("❌ NO FACE DETECTED")
            print("Uploading no-face image to storage...")

            failed_image_url = upload_image_to_storage(temp_file_path, temp_filename)
            print("Uploaded image URL:", failed_image_url)

            print("Saving captured image row...")
            save_captured_image(failed_image_url, "no_face")

            print("Creating alert row...")
            create_alert("No face detected at door", failed_image_url)

            try:
                send_push_notification(
                    "AuthShield Alert",
                    "No face detected at your door"
                )
            except Exception as push_error:
                print("⚠ Push notification failed:", str(push_error))

            return {
                "success": False,
                "matched": False,
                "message": "No face detected",
                "image_url": failed_image_url
            }

        owners = get_all_owners()
        print("Owners found:", len(owners))

        known_encodings = []
        valid_owners = []

        for owner in owners:
            image_url = owner.get("image_url")
            if image_url:
                encoding = get_face_encoding_from_url(image_url)
                if encoding is not None:
                    known_encodings.append(encoding)
                    valid_owners.append(owner)

        print("Valid encodings loaded:", len(known_encodings))

        if len(known_encodings) == 0:
            return {
                "success": False,
                "matched": False,
                "message": "No registered owners found"
            }

        match, index = compare_faces(unknown_encoding, known_encodings)

        if match:
            matched_owner = valid_owners[index]
            print("✅ FACE MATCHED:", matched_owner.get("name"))

            return {
                "success": True,
                "matched": True,
                "message": "Face matched successfully",
                "owner": {
                    "id": matched_owner.get("id"),
                    "name": matched_owner.get("name"),
                    "role": matched_owner.get("role"),
                    "image_url": matched_owner.get("image_url")
                }
            }

        else:
            print("❌ FACE NOT MATCHED")
            print("Uploading failed image to storage...")

            failed_image_url = upload_image_to_storage(temp_file_path, temp_filename)
            print("Uploaded image URL:", failed_image_url)

            print("Saving captured image row...")
            save_captured_image(failed_image_url, "unrecognized")

            print("Creating alert row...")
            create_alert("Unknown face detected", failed_image_url)

            try:
                send_push_notification(
                    "Intrusion Detected",
                    "Unknown face detected at your door"
                )
            except Exception as push_error:
                print("⚠ Push notification failed:", str(push_error))

            return {
                "success": True,
                "matched": False,
                "message": "Unknown face",
                "image_url": failed_image_url
            }

    except Exception as e:
        print("❌ SERVER ERROR:", str(e))
        return {
            "success": False,
            "matched": False,
            "message": f"Server error: {str(e)}"
        }

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


# ================= WRONG PASSWORD IMAGE =================
@app.post("/wrong-password-image")
async def wrong_password_image(file: UploadFile = File(...)):
    temp_filename = f"{uuid.uuid4()}_{file.filename}"
    temp_file_path = os.path.join(UPLOAD_FOLDER, temp_filename)

    try:
        print("\n================ WRONG PASSWORD IMAGE REQUEST ================")
        print("Received file:", file.filename)
        print("Content type:", file.content_type)

        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not os.path.exists(temp_file_path):
            return {
                "success": False,
                "message": "Image file was not saved"
            }

        file_size = os.path.getsize(temp_file_path)
        print("Saved temp file:", temp_file_path)
        print("Image size:", file_size, "bytes")

        if file_size == 0:
            return {
                "success": False,
                "message": "Captured image is empty"
            }

        print("📤 Uploading wrong-password intrusion image to storage...")

        image_url = upload_image_to_storage(temp_file_path, temp_filename)
        print("Uploaded image URL:", image_url)

        print("📝 Saving captured image row...")
        save_captured_image(image_url, "wrong_password_intrusion")

        print("🚨 Creating alert row...")
        create_alert("5 wrong keypad password attempts detected", image_url)

        try:
            send_push_notification(
                "AuthShield Alert",
                "5 wrong keypad password attempts detected"
            )
        except Exception as push_error:
            print("⚠ Push notification failed:", str(push_error))

        return {
            "success": True,
            "message": "Wrong password intrusion image saved successfully",
            "image_url": image_url
        }

    except Exception as e:
        print("❌ WRONG PASSWORD IMAGE ERROR:", str(e))
        return {
            "success": False,
            "message": f"Server error: {str(e)}"
        }

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)