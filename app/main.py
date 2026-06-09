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
SPEED_FACE_THRESHOLD = 0.70
CHIN_FINGER_THRESHOLD = 0.72
CONFETTI_THRESHOLD = 0.42

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
        self.previous_hand_centers: list[tuple[float, float]] | None = None
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
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
        hands = extract_hands(hand_results, width, height)
        finger_mouth_confidence = compute_finger_mouth_confidence(face, hands, width, height)
        chin_finger_confidence = compute_chin_finger_confidence(face, hands, width, height)
        confetti_confidence = self.compute_confetti_confidence(hands, height)
        speed_face_confidence = compute_speed_face_confidence(face)
        expression_active = speed_face_confidence >= SPEED_FACE_THRESHOLD
        finger_mouth_active = finger_mouth_confidence >= FINGER_MOUTH_THRESHOLD
        chin_finger_active = chin_finger_confidence >= CHIN_FINGER_THRESHOLD
        confetti_active = confetti_confidence >= CONFETTI_THRESHOLD
        active_image = strongest_active_image(
            [
                ("monkey", finger_mouth_confidence, FINGER_MOUTH_THRESHOLD),
                ("speedFace", speed_face_confidence, SPEED_FACE_THRESHOLD),
                ("mogging", chin_finger_confidence, CHIN_FINGER_THRESHOLD),
            ]
        )

        return {
            "faceBox": face["box"] if face else None,
            "handBox": hands[0]["box"] if hands else None,
            "handBoxes": [hand["box"] for hand in hands],
            "confidence": max(
                finger_mouth_confidence,
                speed_face_confidence,
                chin_finger_confidence,
                confetti_confidence,
            ),
            "fingerMouthConfidence": finger_mouth_confidence,
            "speedFaceConfidence": speed_face_confidence,
            "chinFingerConfidence": chin_finger_confidence,
            "confettiConfidence": confetti_confidence,
            "gestureActive": finger_mouth_active or expression_active or chin_finger_active or confetti_active,
            "activeImage": active_image,
            "confettiActive": confetti_active,
            "confettiIntensity": confetti_confidence,
            "fingerMouthThreshold": FINGER_MOUTH_THRESHOLD,
            "speedFaceThreshold": SPEED_FACE_THRESHOLD,
            "chinFingerThreshold": CHIN_FINGER_THRESHOLD,
            "confettiThreshold": CONFETTI_THRESHOLD,
            "monkeyImageAvailable": MONKEY_IMAGE.exists(),
            "speedFaceImageAvailable": SPEED_FACE_IMAGE.exists(),
            "moggingImageAvailable": MOGGING_IMAGE.exists(),
        }

    def compute_confetti_confidence(self, hands: list[dict[str, Any]], height: int) -> float:
        centers = sorted([hand["center"] for hand in hands], key=lambda center: center[0])
        if len(centers) < 2:
            self.previous_hand_centers = centers
            return 0.0

        if not self.previous_hand_centers or len(self.previous_hand_centers) < 2:
            self.previous_hand_centers = centers
            return 0.0

        left_delta = centers[0][1] - self.previous_hand_centers[0][1]
        right_delta = centers[1][1] - self.previous_hand_centers[1][1]
        self.previous_hand_centers = centers

        moving_opposite = left_delta * right_delta < 0
        normalized_speed = (abs(left_delta) + abs(right_delta)) / max(height, 1)
        if not moving_opposite:
            return 0.0

        confidence = normalized_score(normalized_speed, low=0.025, high=0.14)
        return round(max(0.0, min(1.0, confidence)), 2)


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
        "handBoxes": [],
        "confidence": 0.0,
        "fingerMouthConfidence": 0.0,
        "speedFaceConfidence": 0.0,
        "chinFingerConfidence": 0.0,
        "confettiConfidence": 0.0,
        "gestureActive": False,
        "activeImage": None,
        "confettiActive": False,
        "confettiIntensity": 0.0,
        "fingerMouthThreshold": FINGER_MOUTH_THRESHOLD,
        "speedFaceThreshold": SPEED_FACE_THRESHOLD,
        "chinFingerThreshold": CHIN_FINGER_THRESHOLD,
        "confettiThreshold": CONFETTI_THRESHOLD,
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


def extract_hands(results: Any, width: int, height: int) -> list[dict[str, Any]]:
    if not results.multi_hand_landmarks:
        return []

    hands = []
    for hand_landmarks in results.multi_hand_landmarks:
        landmarks = hand_landmarks.landmark
        xs = [landmark.x * width for landmark in landmarks]
        ys = [landmark.y * height for landmark in landmarks]

        index_tip = landmarks[8]
        fingertip = point_xy(index_tip, width, height)
        center = average_point(list(zip(xs, ys)))

        hands.append(
            {
                "box": square_box(min(xs), min(ys), max(xs), max(ys), width, height),
                "fingertip": fingertip,
                "center": center,
            }
        )

    return hands


def compute_finger_mouth_confidence(
    face: dict[str, Any] | None,
    hands: list[dict[str, Any]],
    width: int,
    height: int,
) -> float:
    if not face or not hands:
        return 0.0

    mouth_x, mouth_y = face["mouth"]
    frame_scale = math.hypot(width, height)
    close_distance = frame_scale * 0.035
    far_distance = frame_scale * 0.16
    confidence = 0.0
    for hand in hands:
        finger_x, finger_y = hand["fingertip"]
        distance = math.hypot(finger_x - mouth_x, finger_y - mouth_y)
        hand_confidence = 1.0 - ((distance - close_distance) / (far_distance - close_distance))
        confidence = max(confidence, hand_confidence)

    return round(max(0.0, min(1.0, confidence)), 2)


def compute_chin_finger_confidence(
    face: dict[str, Any] | None,
    hands: list[dict[str, Any]],
    width: int,
    height: int,
) -> float:
    if not face or not hands:
        return 0.0

    mouth_x, mouth_y = face["mouth"]
    frame_scale = math.hypot(width, height)
    close_distance = frame_scale * 0.03
    far_distance = frame_scale * 0.10
    confidence = 0.0
    for hand in hands:
        finger = hand["fingertip"]
        mouth_distance = math.hypot(finger[0] - mouth_x, finger[1] - mouth_y)
        if mouth_distance < frame_scale * 0.10:
            continue

        distance = min(math.hypot(finger[0] - point[0], finger[1] - point[1]) for point in face["chinPoints"])
        hand_confidence = 1.0 - ((distance - close_distance) / (far_distance - close_distance))
        confidence = max(confidence, hand_confidence)

    return round(max(0.0, min(1.0, confidence)), 2)


def compute_speed_face_confidence(face: dict[str, Any] | None) -> float:
    if not face:
        return 0.0

    metrics = face["metrics"]
    eye_score = normalized_inverse(metrics["eye_open"], low=0.075, high=0.16)
    mouth_closed_score = normalized_inverse(metrics["mouth_open"], low=0.012, high=0.045)
    mouth_circle_score = centered_score(metrics["mouth_outer_roundness"], target=0.72, tolerance=0.22)
    confidence = min(eye_score, mouth_closed_score, mouth_circle_score)

    return round(max(0.0, min(1.0, confidence)), 2)


def extract_face_metrics(landmarks: Any, width: int, height: int) -> dict[str, float]:
    face_width = distance_px(landmarks[234], landmarks[454], width, height)
    face_width = max(face_width, 1.0)

    left_eye_open = distance_px(landmarks[159], landmarks[145], width, height)
    right_eye_open = distance_px(landmarks[386], landmarks[374], width, height)
    mouth_width = distance_px(landmarks[61], landmarks[291], width, height)
    mouth_open = distance_px(landmarks[13], landmarks[14], width, height)
    mouth_outer_height = distance_px(landmarks[0], landmarks[17], width, height)
    mouth_outer_roundness = mouth_outer_height / max(mouth_width, 1.0)

    return {
        "eye_open": ((left_eye_open + right_eye_open) / 2) / face_width,
        "mouth_open": mouth_open / face_width,
        "mouth_outer_roundness": mouth_outer_roundness,
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


def centered_score(value: float, target: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (abs(value - target) / tolerance)))


def strongest_active_image(candidates: list[tuple[str, float, float]]) -> str | None:
    active_candidates = [
        (name, confidence)
        for name, confidence, threshold in candidates
        if confidence >= threshold
    ]
    if not active_candidates:
        return None
    return max(active_candidates, key=lambda candidate: candidate[1])[0]


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
