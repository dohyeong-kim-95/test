"""카메라 영상을 보다가 전신이 잡히면 사진을 저장한다."""
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import requests
from mediapipe.tasks.python import BaseOptions, vision

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
MODEL_PATH = Path("models/pose_landmarker_lite.task")

NOSE, LEFT_ANKLE, RIGHT_ANKLE = 0, 27, 28


class Camera:
    """IP Webcam 스냅샷 URL(http) 또는 홈캠 RTSP 주소에서 프레임을 받는다."""

    def __init__(self, url, user="", password=""):
        self.url = url
        self.auth = (user, password) if user else None
        self.cap = None

    def read(self):
        if self.url.startswith("rtsp"):
            if self.cap is None or not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.url)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = self.cap.read()
            if not ok:
                self.cap.release()
                self.cap = None
                raise ConnectionError("RTSP 프레임을 읽지 못함")
            return frame
        resp = requests.get(self.url, auth=self.auth, timeout=5)
        resp.raise_for_status()
        return cv2.imdecode(np.frombuffer(resp.content, np.uint8), cv2.IMREAD_COLOR)

    def photo(self, url):
        """고화질 사진 원본(JPEG 바이트)을 받는다. IP Webcam의 /photo.jpg."""
        resp = requests.get(url, auth=self.auth, timeout=15)
        resp.raise_for_status()
        return resp.content


class Trigger:
    """전신이 hold_sec 이상 이어지면 촬영, 촬영 후 cooldown_sec 동안은 쉰다."""

    def __init__(self, hold_sec, cooldown_sec):
        self.hold_sec = hold_sec
        self.cooldown_sec = cooldown_sec
        self.since = None
        self.last_shot = -float("inf")

    def update(self, full_body, now):
        if not full_body:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        if now - self.since >= self.hold_sec and now - self.last_shot >= self.cooldown_sec:
            self.last_shot = now
            self.since = None
            return True
        return False


def load_detector():
    if not MODEL_PATH.exists():
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print("포즈 모델 다운로드 중...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        num_poses=2,
    )
    return vision.PoseLandmarker.create_from_options(options)


def is_full_body(detector, frame):
    """사람이 정확히 1명이고 머리와 두 발목이 화면 안에 보이면 True."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if len(result.pose_landmarks) != 1:
        return False
    marks = result.pose_landmarks[0]
    for i in (NOSE, LEFT_ANKLE, RIGHT_ANKLE):
        m = marks[i]
        if m.visibility < 0.5 or not (0 <= m.x <= 1 and 0 <= m.y <= 1):
            return False
    return True


def ootd_date(dt, day_start_hour):
    return (dt - timedelta(hours=day_start_hour)).date()


def save_photo(jpeg_bytes, photo_dir, day_start_hour):
    now = datetime.now()
    folder = Path(photo_dir) / ootd_date(now, day_start_hour).isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{now:%H%M%S}.jpg"
    path.write_bytes(jpeg_bytes)
    return path


def take_photo(camera, frame, photo_url):
    """photo_url이 있으면 고화질 원본을, 없거나 실패하면 감지에 쓴 프레임을 저장용 JPEG로 만든다."""
    if photo_url:
        try:
            return camera.photo(photo_url)
        except Exception as e:
            print("고화질 촬영 실패, 감지 프레임으로 저장:", e)
    return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()


def run(cfg):
    camera = Camera(cfg["camera_url"], cfg.get("camera_user", ""), cfg.get("camera_password", ""))
    detector = load_detector()
    trigger = Trigger(cfg["hold_sec"], cfg["cooldown_min"] * 60)
    print("촬영 대기 중:", cfg["camera_url"])
    while True:
        try:
            frame = camera.read()
        except Exception as e:
            print("카메라 연결 실패, 5초 후 재시도:", e)
            time.sleep(5)
            continue
        if frame is not None and trigger.update(is_full_body(detector, frame), time.monotonic()):
            jpeg = take_photo(camera, frame, cfg.get("photo_url", ""))
            print("촬영:", save_photo(jpeg, cfg["photo_dir"], cfg["day_start_hour"]))
        time.sleep(cfg["check_interval_sec"])
