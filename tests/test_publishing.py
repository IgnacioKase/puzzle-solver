import csv

import numpy as np
from helpers import ScriptTestCase
from PIL import Image


class PublishingTests(ScriptTestCase):
    def setUp(self):
        super().setUp()
        self.board()

    def publish(self, pieces):
        self.write_json("refined.json", pieces)
        self.run_script("publish.py")
        return self.read_json("guide-data.json")

    def test_confidence_overrides_and_exports_agree(self):
        high = self.piece("A-a1", 100, 100)
        medium = self.piece("A-a2", 500, 100, score=0.85, gap=0.8)
        ambiguous = self.piece("A-a3", 900, 100, margin=0.001)
        missing = self.piece("A-a4")
        missing.pop("best")
        reviewed = self.piece("A-a5", 1400, 100)
        self.write_json(
            "review.json", {"A-a5": {"status": "unresolved", "note": "Physical fit rejected"}}
        )
        data = self.publish([high, medium, ambiguous, missing, reviewed])
        self.assertEqual(data["summary"], {"high": 1, "medium": 1, "unresolved": 3, "total": 5})
        self.assertEqual(
            [p["status"] for p in data["pieces"]],
            ["high", "medium", "unresolved", "unresolved", "unresolved"],
        )
        self.assertEqual(data["pieces"][0]["angle"], 270)
        for p in data["pieces"][2:]:
            self.assertIsNone(p["x"])
            self.assertIsNone(p["angle"])
            self.assertNotIn("polygon", p)
        self.assertEqual(data["pieces"][-1]["note"], "Physical fit rejected")
        import json

        js = (self.out / "guide-data.js").read_text()
        self.assertEqual(
            json.loads(js.removeprefix("window.PUZZLE_DATA=").removesuffix(";\n")), data
        )
        with (self.out / "placements.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["x_percent_from_left"], "5.6")
        self.assertEqual(rows[0]["clockwise_degrees"], "270")
        self.assertEqual(rows[2]["x_percent_from_left"], "")
        self.assertEqual(self.read_json("conflicts.json"), [])
        with Image.open(self.out / "previews/A-a1.jpg") as im:
            self.assertEqual(im.size, (660, 220))
        for name in ("placement-map-state.jpg", "placement-map-reference.jpg", "review-1.jpg"):
            with Image.open(self.out / name) as im:
                im.verify()

    def test_adjacent_pieces_have_reciprocal_neighbors_and_overlap_is_flagged(self):
        data = self.publish(
            [self.piece("A-a1"), self.piece("A-a2", 141, 100), self.piece("A-a3", 100, 100)]
        )
        pieces = {p["id"]: p for p in data["pieces"]}
        self.assertIn({"id": "A-a2", "direction": "right"}, pieces["A-a1"]["neighbors"])
        self.assertIn({"id": "A-a1", "direction": "left"}, pieces["A-a2"]["neighbors"])
        self.assertNotIn("A-a3", [p["id"] for p in pieces["A-a1"]["neighbors"]])
        self.assertIn(["A-a1", "A-a3", 1.0], self.read_json("conflicts.json"))

    def test_empty_inventory_exports_valid_empty_guide(self):
        data = self.publish([])
        self.assertEqual(data["pieces"], [])
        self.assertEqual(data["summary"]["total"], 0)
        self.assertEqual(self.read_json("conflicts.json"), [])

    def test_starter_generates_documentation_illustrations(self):
        self.publish([self.piece("A-g5", 100, 350), self.piece("B-a4", 141, 350)])
        for name in ("sheet-a-main.jpg", "puzzle-state.jpg", "box-photo.jpg"):
            Image.fromarray(np.full((100, 80, 3), 180, np.uint8)).save(self.root / "images" / name)
        self.run_script("starter.py")
        expected = {
            "upper-left-example.jpg": (1450, 1010),
            "piece-representations.png": (1230, 460),
            "source-photos.jpg": (1450, 820),
        }
        for name, size in expected.items():
            with self.subTest(name=name), Image.open(self.root / "docs/assets" / name) as im:
                self.assertEqual(im.size, size)
                self.assertFalse(im.getexif())
        self.assertEqual(
            (self.out / "start-here.jpg").read_bytes(),
            (self.root / "docs/assets/upper-left-example.jpg").read_bytes(),
        )
