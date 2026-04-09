# Face_services.py
import face_recognition
import requests
import numpy as np
from io import BytesIO
from PIL import Image

def get_face_encoding_from_url(image_url: str):
    try:
        print("📥 Downloading owner image:", image_url)

        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        image = Image.open(BytesIO(response.content)).convert("RGB")
        image_np = np.array(image)

        encodings = face_recognition.face_encodings(image_np)

        if len(encodings) > 0:
            print("✅ Owner face encoding generated")
            return encodings[0]

        print("❌ No face found in owner image")
        return None

    except Exception as e:
        print("❌ Error loading owner image:", str(e))
        return None


def get_face_encoding_from_file(file_path: str):
    try:
        print("📷 Processing uploaded face image:", file_path)

        image = Image.open(file_path).convert("RGB")
        image_np = np.array(image)

        print("Image shape:", image_np.shape)

        encodings = face_recognition.face_encodings(image_np)

        if len(encodings) > 0:
            print("✅ Face detected in uploaded image")
            return encodings[0]

        print("❌ No face detected in uploaded image")
        return None

    except Exception as e:
        print("❌ Error processing uploaded image:", str(e))
        return None


def compare_faces(unknown_encoding, known_encodings, tolerance=0.6):
    try:
        if not known_encodings:
            print("❌ No known encodings available")
            return False, -1

        matches = face_recognition.compare_faces(
            known_encodings,
            unknown_encoding,
            tolerance=tolerance
        )

        distances = face_recognition.face_distance(
            known_encodings,
            unknown_encoding
        )

        if len(distances) == 0:
            print("❌ No face distances computed")
            return False, -1

        best_match_index = np.argmin(distances)

        print("📏 Face distances:", distances)
        print("🎯 Best match index:", best_match_index)
        print("🎯 Best match distance:", distances[best_match_index])

        if matches[best_match_index]:
            print("✅ Face match accepted")
            return True, best_match_index

        print("❌ Face match rejected")
        return False, -1

    except Exception as e:
        print("❌ Error comparing faces:", str(e))
        return False, -1