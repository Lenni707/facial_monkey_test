from __future__ import annotations

import base64
import json
import math
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
STATIC_DIR = ROOT_DIR / "static"
MONKEY_IMAGE = ASSETS_DIR / "thinking_monkey.jpeg"
SPEED_FACE_IMAGE = ASSETS_DIR / "speed_face.png"
MOGGING_IMAGE = ASSETS_DIR / "mogger.jpeg"

FRAME_PREFIX = "data:image/jpeg;base64,"
FINGER_MOUTH_THRESHOLD = 0.70
SPEED_FACE_THRESHOLD = 0.62
CHIN_FINGER_THRESHOLD = 0.72

app = FastAPI(title="Finger-to-Mouth Monkey Meme")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

mp_face_mesh = mp.solutions.face_mesh
mp_hands = mp.solutions.hands


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/asset-status")
def asset_status() -> dict[str, bool]:
    return {
        "monkeyImageAvailable": MONKEY_IMAGE.exists(),
        "speedFaceImageAvailable": SPEED_FACE_IMAGE.exists(),
        "moggingImageAvailable": MOGGING_IMAGE.exists(),
    }


@app.websocket("/ws/analyze")
async def analyze(websocket: WebSocket) -> None:
    await websocket.accept()
    detector = GestureDetector()

    try:
        while True:
            payload = await websocket.receive_text()
            result = detector.analyze_payload(payload)
            await websocket.send_text(json.dumps(result))
    except WebSocketDisconnect:
        return
    finally:
        detector.close()


class GestureDetector:
    def __init__(self) -> None:
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def close(self) -> None:
        self.face_mesh.close()
        self.hands.close()

    def analyze_payload(self, payload: str) -> dict[str, Any]:
        frame = decode_frame(payload)
        if frame is None:
            return empty_result()

        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_results = self.face_mesh.process(rgb)
        hand_results = self.hands.process(rgb)

        face = extract_face(face_results, width, height)
        hand = extract_hand(hand_results, width, height)
        finger_mouth_confidence = compute_finger_mouth_confidence(face, hand, width, height)
        chin_finger_confidence = compute_chin_finger_confidence(face, hand, width, height)
        speed_face_confidence = compute_speed_face_confidence(face)
        expression_active = speed_face_confidence >= SPEED_FACE_THRESHOLD
        finger_mouth_active = finger_mouth_confidence >= FINGER_MOUTH_THRESHOLD
        chin_finger_active = chin_finger_confidence >= CHIN_FINGER_THRESHOLD
        active_image = (
            "speedFace"
            if expression_active
            else "monkey"
            if finger_mouth_active
            else "mogging"
            if chin_finger_active
            else None
        )

        return {
            "faceBox": face["box"] if face else None,
            "handBox": hand["box"] if hand else None,
            "confidence": max(finger_mouth_confidence, speed_face_confidence, chin_finger_confidence),
            "fingerMouthConfidence": finger_mouth_confidence,
            "speedFaceConfidence": speed_face_confidence,
            "chinFingerConfidence": chin_finger_confidence,
            "gestureActive": finger_mouth_active or expression_active or chin_finger_active,
            "activeImage": active_image,
            "fingerMouthThreshold": FINGER_MOUTH_THRESHOLD,
            "speedFaceThreshold": SPEED_FACE_THRESHOLD,
            "chinFingerThreshold": CHIN_FINGER_THRESHOLD,
            "monkeyImageAvailable": MONKEY_IMAGE.exists(),
            "speedFaceImageAvailable": SPEED_FACE_IMAGE.exists(),
            "moggingImageAvailable": MOGGING_IMAGE.exists(),
        }


def decode_frame(payload: str) -> np.ndarray | None:
    if payload.startswith(FRAME_PREFIX):
        payload = payload[len(FRAME_PREFIX) :]

    try:
        raw = base64.b64decode(payload, validate=True)
    except ValueError:
        return None

    encoded = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    return frame


def empty_result() -> dict[str, Any]:
    return {
        "faceBox": None,
        "handBox": None,
        "confidence": 0.0,
        "fingerMouthConfidence": 0.0,
        "speedFaceConfidence": 0.0,
        "chinFingerConfidence": 0.0,
        "gestureActive": False,
        "activeImage": None,
        "fingerMouthThreshold": FINGER_MOUTH_THRESHOLD,
        "speedFaceThreshold": SPEED_FACE_THRESHOLD,
        "chinFingerThreshold": CHIN_FINGER_THRESHOLD,
        "monkeyImageAvailable": MONKEY_IMAGE.exists(),
        "speedFaceImageAvailable": SPEED_FACE_IMAGE.exists(),
        "moggingImageAvailable": MOGGING_IMAGE.exists(),
    }


def extract_face(results: Any, width: int, height: int) -> dict[str, Any] | None:
    if not results.multi_face_landmarks:
        return None

    landmarks = results.multi_face_landmarks[0].landmark
    xs = [landmark.x * width for landmark in landmarks]
    ys = [landmark.y * height for landmark in landmarks]

    mouth_indexes = [13, 14, 61, 291]
    mouth_points = [(landmarks[i].x * width, landmarks[i].y * height) for i in mouth_indexes]
    mouth_center = average_point(mouth_points)
    chin_points = [
        point_xy(landmarks[index], width, height)
        for index in [152, 148, 176, 149, 150, 377, 400, 378, 379]
    ]
    metrics = extract_face_metrics(landmarks, width, height)

    return {
        "box": square_box(min(xs), min(ys), max(xs), max(ys), width, height),
        "mouth": mouth_center,
        "chinPoints": chin_points,
        "metrics": metrics,
    }


def extract_hand(results: Any, width: int, height: int) -> dict[str, Any] | None:
    if not results.multi_hand_landmarks:
        return None

    landmarks = results.multi_hand_landmarks[0].landmark
    xs = [landmark.x * width for landmark in landmarks]
    ys = [landmark.y * height for landmark in landmarks]

    index_tip = landmarks[8]
    fingertip = point_xy(index_tip, width, height)

    return {
        "box": square_box(min(xs), min(ys), max(xs), max(ys), width, height),
        "fingertip": fingertip,
    }


def compute_finger_mouth_confidence(
    face: dict[str, Any] | None,
    hand: dict[str, Any] | None,
    width: int,
    height: int,
) -> float:
    if not face or not hand:
        return 0.0

    mouth_x, mouth_y = face["mouth"]
    finger_x, finger_y = hand["fingertip"]
    distance = math.hypot(finger_x - mouth_x, finger_y - mouth_y)

    frame_scale = math.hypot(width, height)
    close_distance = frame_scale * 0.035
    far_distance = frame_scale * 0.16
    confidence = 1.0 - ((distance - close_distance) / (far_distance - close_distance))

    return round(max(0.0, min(1.0, confidence)), 2)


def compute_chin_finger_confidence(
    face: dict[str, Any] | None,
    hand: dict[str, Any] | None,
    width: int,
    height: int,
) -> float:
    if not face or not hand:
        return 0.0

    finger = hand["fingertip"]
    mouth_x, mouth_y = face["mouth"]
    mouth_distance = math.hypot(finger[0] - mouth_x, finger[1] - mouth_y)
    distance = min(math.hypot(finger[0] - point[0], finger[1] - point[1]) for point in face["chinPoints"])

    frame_scale = math.hypot(width, height)
    if mouth_distance < frame_scale * 0.10:
        return 0.0

    close_distance = frame_scale * 0.03
    far_distance = frame_scale * 0.10
    confidence = 1.0 - ((distance - close_distance) / (far_distance - close_distance))

    return round(max(0.0, min(1.0, confidence)), 2)


def compute_speed_face_confidence(face: dict[str, Any] | None) -> float:
    if not face:
        return 0.0

    metrics = face["metrics"]
    eye_score = normalized_inverse(metrics["eye_open"], low=0.075, high=0.16)
    mouth_closed_score = normalized_inverse(metrics["mouth_open"], low=0.015, high=0.06)
    mouth_narrow_score = normalized_inverse(metrics["mouth_width"], low=0.22, high=0.40)
    confidence = min(eye_score, (mouth_closed_score * 0.50) + (mouth_narrow_score * 0.50))

    return round(max(0.0, min(1.0, confidence)), 2)


def extract_face_metrics(landmarks: Any, width: int, height: int) -> dict[str, float]:
    face_width = distance_px(landmarks[234], landmarks[454], width, height)
    face_width = max(face_width, 1.0)

    left_eye_open = distance_px(landmarks[159], landmarks[145], width, height)
    right_eye_open = distance_px(landmarks[386], landmarks[374], width, height)
    mouth_width = distance_px(landmarks[61], landmarks[291], width, height)
    mouth_open = distance_px(landmarks[13], landmarks[14], width, height)

    return {
        "eye_open": ((left_eye_open + right_eye_open) / 2) / face_width,
        "mouth_open": mouth_open / face_width,
        "mouth_width": mouth_width / face_width,
    }


def distance_px(point_a: Any, point_b: Any, width: int, height: int) -> float:
    return math.hypot((point_a.x - point_b.x) * width, (point_a.y - point_b.y) * height)


def point_xy(point: Any, width: int, height: int) -> tuple[float, float]:
    return (point.x * width, point.y * height)


def normalized_inverse(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, 1.0 - ((value - low) / (high - low))))


def normalized_score(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def average_point(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def square_box(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    frame_width: int,
    frame_height: int,
) -> dict[str, int]:
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    side = max(max_x - min_x, max_y - min_y) * 1.15

    x = max(0, center_x - side / 2)
    y = max(0, center_y - side / 2)
    side = min(side, frame_width - x, frame_height - y)

    return {
        "x": int(round(x)),
        "y": int(round(y)),
        "size": int(round(max(0, side))),
    }
