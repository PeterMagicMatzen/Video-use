"""Cloudinary delivery + transformation layer (9:16 reframe with g_auto, CDN preview)."""

import os
from pathlib import Path

import cloudinary
import cloudinary.uploader
import cloudinary.utils

_CONFIGURED = False


def enabled() -> bool:
    return all(
        os.environ.get(k)
        for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    )


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    cloudinary.config(
        cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key=os.environ["CLOUDINARY_API_KEY"],
        api_secret=os.environ["CLOUDINARY_API_SECRET"],
        secure=True,
    )
    _CONFIGURED = True


REEL_TRANSFORM = [
    {"aspect_ratio": "9:16", "crop": "fill", "gravity": "auto", "width": 1080},
    {"quality": "auto", "fetch_format": "auto"},
]


def upload_reel(path: Path, public_id: str, reframe: bool) -> dict:
    """Upload a rendered reel; when reframe is on, Cloudinary crops to 9:16 with g_auto."""
    _configure()
    result = cloudinary.uploader.upload_large(
        str(path),
        resource_type="video",
        public_id=public_id,
        folder="uploads/reels",
        overwrite=True,
        eager=[REEL_TRANSFORM[0]] if reframe else None,
        eager_async=True,
        chunk_size=6_000_000,
    )
    pid = result.get("public_id")
    url = result.get("secure_url")
    if reframe and pid:
        url, _ = cloudinary.utils.cloudinary_url(
            pid, resource_type="video", transformation=REEL_TRANSFORM, secure=True
        )
    return {"public_id": pid, "url": url}


def destroy(public_id: str) -> None:
    _configure()
    cloudinary.uploader.destroy(public_id, resource_type="video", invalidate=True)
