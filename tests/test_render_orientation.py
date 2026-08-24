import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "helpers" / "render.py"
SPEC = importlib.util.spec_from_file_location("video_use_render", MODULE_PATH)
assert SPEC and SPEC.loader
render = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render)


class PortraitDetectionTests(unittest.TestCase):
    def _is_portrait(self, stream: dict) -> bool:
        result = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({"streams": [stream]}), stderr=""
        )
        with patch.object(render.subprocess, "run", return_value=result):
            return render.is_portrait_source(Path("source.mp4"))

    def test_native_portrait_dimensions(self):
        self.assertTrue(self._is_portrait({"width": 1080, "height": 1920}))

    def test_native_landscape_dimensions(self):
        self.assertFalse(self._is_portrait({"width": 1920, "height": 1080}))

    def test_side_data_rotation_turns_coded_landscape_into_portrait(self):
        stream = {
            "width": 1920,
            "height": 1080,
            "side_data_list": [{"rotation": -90}],
        }
        self.assertTrue(self._is_portrait(stream))

    def test_legacy_rotation_tag_is_supported(self):
        stream = {"width": 1920, "height": 1080, "tags": {"rotate": "270"}}
        self.assertTrue(self._is_portrait(stream))

    def test_rotation_can_turn_coded_portrait_into_landscape(self):
        stream = {
            "width": 1080,
            "height": 1920,
            "side_data_list": [{"rotation": 90}],
        }
        self.assertFalse(self._is_portrait(stream))

    def test_invalid_probe_output_falls_back_to_landscape(self):
        result = subprocess.CompletedProcess([], 0, stdout="not json", stderr="")
        with patch.object(render.subprocess, "run", return_value=result):
            self.assertFalse(render.is_portrait_source(Path("source.mp4")))


if __name__ == "__main__":
    unittest.main()
