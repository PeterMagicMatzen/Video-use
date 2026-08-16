"""Locate the speaker horizontally so landscape clips can be cropped to 9:16 on-subject."""

from pathlib import Path

import cv2


def subject_center(video_path: Path, samples: int = 14) -> float:
    """Return normalised x (0..1) of the dominant face across sampled frames."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0.5
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    xs = []
    try:
        for i in range(samples):
            if total > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / samples))
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            if w == 0:
                continue
            small = cv2.resize(frame, (480, max(1, int(480 * h / w))))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.15, 5, minSize=(36, 36))
            if len(faces):
                fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                xs.append((fx + fw / 2) / small.shape[1])
    finally:
        cap.release()
    if not xs:
        return 0.5
    xs.sort()
    return float(min(0.9, max(0.1, xs[len(xs) // 2])))
