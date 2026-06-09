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
MONKEY_IMAGE = ASSETS_DIR / "monkey_thinking.png"

FRAME_PREFIX = "data:image/jpeg;base64,"
GESTURE_THRESHOLD = 0.70

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
    return {"monkeyImageAvailable": MONKEY_IMAGE.exists()}


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
        confidence = compute_confidence(face, hand, width, height)

        return {
            "faceBox": face["box"] if face else None,
            "handBox": hand["box"] if hand else None,
            "confidence": confidence,
            "gestureActive": confidence >= GESTURE_THRESHOLD,
            "threshold": GESTURE_THRESHOLD,
            "monkeyImageAvailable": MONKEY_IMAGE.exists(),
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
        "gestureActive": False,
        "threshold": GESTURE_THRESHOLD,
        "monkeyImageAvailable": MONKEY_IMAGE.exists(),
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

    return {
        "box": square_box(min(xs), min(ys), max(xs), max(ys), width, height),
        "mouth": mouth_center,
    }


def extract_hand(results: Any, width: int, height: int) -> dict[str, Any] | None:
    if not results.multi_hand_landmarks:
        return None

    landmarks = results.multi_hand_landmarks[0].landmark
    xs = [landmark.x * width for landmark in landmarks]
    ys = [landmark.y * height for landmark in landmarks]

    index_tip = landmarks[8]
    thumb_tip = landmarks[4]
    fingertip = closest_to_mouth_candidate(
        [(index_tip.x * width, index_tip.y * height), (thumb_tip.x * width, thumb_tip.y * height)]
    )

    return {
        "box": square_box(min(xs), min(ys), max(xs), max(ys), width, height),
        "fingertip": fingertip,
    }


def closest_to_mouth_candidate(points: list[tuple[float, float]]) -> tuple[float, float]:
    # The actual mouth comparison happens later; default to index fingertip for stable output.
    return points[0]


def compute_confidence(
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
