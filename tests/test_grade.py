from __future__ import annotations

from grade import auto_grade_for_clip, get_preset


def test_none_and_natural_are_empty():
    assert get_preset("none") == ""
    assert get_preset("natural") == ""
    assert get_preset("subtle") == ""


def test_named_looks_have_no_hue_shift():
    for name in ("cinematic", "warm_cinematic", "neutral_punch"):
        filt = get_preset(name)
        assert "colorbalance" not in filt
        assert "hue" not in filt
        assert "curves" not in filt
        if "contrast=" in filt:
            value = float(filt.split("contrast=")[1].split(":")[0].split(",")[0])
            assert value <= 1.03


def test_auto_grade_leaves_balanced_clip_alone(monkeypatch):
    def fake_stats(video, start, duration, n_samples=10):
        return {"y_mean": 0.48, "y_std": 0.18, "sat_mean": 0.25}

    monkeypatch.setattr("grade._sample_frame_stats", fake_stats)
    filt, _stats = auto_grade_for_clip(__import__("pathlib").Path("unused.mp4"), duration=5.0)
    assert filt == ""


def test_auto_grade_only_lifts_severe_underexposure(monkeypatch):
    def fake_stats(video, start, duration, n_samples=10):
        return {"y_mean": 0.20, "y_std": 0.18, "sat_mean": 0.25}

    monkeypatch.setattr("grade._sample_frame_stats", fake_stats)
    filt, _stats = auto_grade_for_clip(__import__("pathlib").Path("unused.mp4"), duration=5.0)
    assert filt.startswith("eq=")
    assert "saturation=" not in filt
    assert "colorbalance" not in filt
