"""Isolated script copies: imports and CLI runs cannot touch the real guide."""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import cv2 as cv
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class ScriptTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(
            ROOT / "scripts", self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__")
        )
        self.out = self.root / "output"
        (self.out / "pieces").mkdir(parents=True)
        (self.root / "images").mkdir()
        (self.root / "docs").mkdir()

    def load(self, name):
        spec = importlib.util.spec_from_file_location(name, self.root / "scripts" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def run_script(self, name, *args):
        result = subprocess.run(
            [sys.executable, str(self.root / "scripts" / name), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def write_json(self, name, data):
        (self.out / name).write_text(json.dumps(data))

    def read_json(self, name):
        return json.loads((self.out / name).read_text())

    def write_image(self, name, data):
        self.assertTrue(cv.imwrite(str(self.out / name), data))

    def board(self):
        for name in ("reference.jpg", "reference-clean.jpg", "state.jpg"):
            self.write_image(name, np.full((2600, 1800, 3), 220, np.uint8))

    def piece(self, pid="A-a1", x=100, y=100, score=0.96, gap=0.95, margin=0.1):
        # Dense edge points let the real neighboring-contour check run.
        contour = [[i, 0] for i in range(40)] + [[39, i] for i in range(1, 40)]
        contour += [[i, 39] for i in range(38, -1, -1)] + [[0, i] for i in range(38, 0, -1)]
        self.write_image(f"pieces/{pid}.png", np.full((40, 40, 4), 255, np.uint8))
        return {
            "id": pid,
            "sheet": pid[0],
            "row": 0,
            "col": 0,
            "center": [20, 20],
            "contour": contour,
            "area": 1521,
            "margin": margin,
            "best": {
                "score": score,
                "gapFraction": gap,
                "siftInliers": 0,
                "center": [x, y],
                "angle": -90,
                "H": [[1.0, 0.0, x - 20], [0.0, 1.0, y - 20]],
            },
        }
