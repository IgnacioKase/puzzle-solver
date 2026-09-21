import contextlib
import io
from unittest.mock import patch

import cv2 as cv
import numpy as np
from helpers import ScriptTestCase


class MatchingTests(ScriptTestCase):
    def setUp(self):
        super().setUp()
        self.board()
        self.dense = self.load("dense")

    def test_perspective_warp_maps_corners_and_preserves_identity(self):
        solve = self.load("solve")
        im = np.random.default_rng(3).integers(0, 256, (30, 40, 3), dtype=np.uint8)
        corners = [[0, 0], [39, 0], [39, 29], [0, 29]]
        warped, transform = solve.warp(im, corners, (40, 30))
        np.testing.assert_array_equal(warped, im)
        corners = np.float32([[5, 2], [35, 5], [37, 25], [1, 27]])
        warped, transform = solve.warp(im, corners, (20, 40))
        mapped = cv.perspectiveTransform(corners[None], transform)[0]
        np.testing.assert_allclose(mapped, [[0, 0], [19, 0], [19, 39], [0, 39]], atol=1e-5)
        self.assertEqual(warped.shape, (40, 20, 3))

    def test_rotation_is_clockwise_and_center_stays_centered(self):
        im = np.zeros((30, 40, 3), np.uint8)
        im[15, 30] = [20, 100, 220]
        mask = np.full((30, 40), 255, np.uint8)
        for angle in (0, 90, -90, 37, 180):
            with self.subTest(angle=angle):
                rotated, rotated_mask, transform = self.dense.transformed(im, mask, angle, 1)
                h, w = rotated.shape[:2]
                np.testing.assert_allclose(transform @ [20, 15, 1], [w / 2, h / 2])
                self.assertEqual(rotated_mask.shape, (h, w))
                self.assertGreater(np.count_nonzero(rotated_mask), 1100)
                if angle == 90:
                    x, y = np.rint(transform @ [30, 15, 1]).astype(int)
                    self.assertGreater(y, h / 2)
                    np.testing.assert_array_equal(rotated[y, x], im[15, 30])

    def test_color_features_are_finite_and_distinguish_colors(self):
        im = np.array([[[0, 0, 255], [255, 0, 0], [128, 128, 128]]], np.uint8)
        result = self.dense.features(im)
        self.assertEqual(result.shape, im.shape)
        self.assertEqual(result.dtype, np.float32)
        self.assertTrue(np.isfinite(result).all())
        self.assertGreater(np.linalg.norm(result[0, 0] - result[0, 1]), 1)
        np.testing.assert_allclose(result[0, 2, 1:], 0, atol=0.02)

    def test_dense_search_finds_known_rotated_patch_and_respects_gaps(self):
        # Search real texture at the production scale, on a small synthetic board.
        rng = np.random.default_rng(4)
        im = cv.resize(rng.integers(0, 256, (15, 18, 3), dtype=np.uint8), (90, 75))
        alpha = np.full(im.shape[:2], 255, np.uint8)
        self.write_image("pieces/A-a1.png", np.dstack([im, alpha]))
        p = {"id": "A-a1", "center": [45, 37.5]}
        f = self.dense.features(cv.GaussianBlur(im, (0, 0), 1.2))
        template, _, transform = self.dense.transformed(f, alpha, 90, 0.577 / 3)
        h, w = template.shape[:2]
        board = rng.normal(0, 0.1, (100, 150, 3)).astype(np.float32)
        board[40 : 40 + h, 65 : 65 + w] = template
        gap = np.full(board.shape[:2], 255, np.uint8)
        expected = (transform @ [45, 37.5, 1] + [65, 40]) * 3
        with (
            patch.multiple(self.dense, feat=board, gap=gap),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = self.dense.solve(p)
            best = result["dense"][0]
            self.assertGreater(best["score"], 0.99)
            self.assertEqual(best["angle"], 90)
            np.testing.assert_allclose(best["center"], expected, atol=0.1)
            gap[35:75, 60:95] = 0
            blocked = self.dense.solve(p)
        self.assertTrue(
            all(np.linalg.norm(np.array(c["center"]) - expected) > 20 for c in blocked["dense"])
        )
        self.assertEqual(len(result["dense"]), 8)
        self.assertEqual(
            [c["score"] for c in result["dense"]],
            sorted((c["score"] for c in result["dense"]), reverse=True),
        )

    def test_sift_match_handles_featureless_piece(self):
        p = self.piece()
        self.write_json("pieces.json", [p])
        self.run_script("solve.py", "match")
        result = self.read_json("matches.json")
        self.assertEqual(result[0]["id"], p["id"])
        self.assertIsNone(result[0]["match"])
        self.assertEqual(result[0]["candidates"], [])

    def test_dense_cli_filters_piece_ids(self):
        p = self.piece()
        self.write_json("pieces.json", [p])
        self.run_script("dense.py", "missing-id")
        self.assertEqual(self.read_json("dense-test.json"), [])
        self.assertFalse((self.out / "dense.json").exists())

    def test_refine_handles_no_candidates(self):
        p = self.piece()
        p.pop("best")
        p.pop("margin")
        p["dense"] = []
        self.write_json("matches.json", [{"id": p["id"], "match": None}])
        self.write_json("dense.json", [p])
        self.run_script("refine.py")
        result = self.read_json("refined.json")[0]
        self.assertEqual(result["refined"], [])
        self.assertNotIn("best", result)

    def test_refine_recovers_known_position_and_reports_gap_overlap(self):
        rng = np.random.default_rng(9)
        im = cv.resize(rng.integers(0, 256, (15, 18, 3), dtype=np.uint8), (90, 75))
        alpha = np.full(im.shape[:2], 255, np.uint8)
        self.write_image("pieces/A-a1.png", np.dstack([im, alpha]))
        self.write_json("matches.json", [{"id": "A-a1", "match": None}])
        # refine imports dense as a sibling module, just as its CLI does.
        with patch.dict("sys.modules", {"dense": self.dense}):
            refine = self.load("refine")
        f = self.dense.features(cv.GaussianBlur(im, (0, 0), 1.8))
        template, _, transform = self.dense.transformed(f, alpha, 0, 0.577)
        h, w = template.shape[:2]
        board = np.zeros((600, 600, 3), np.float32)
        board[270 : 270 + h, 250 : 250 + w] = template
        expected = transform @ [45, 37.5, 1] + [250, 270]
        p = {
            "id": "A-a1",
            "center": [45, 37.5],
            "dense": [{"center": (expected + 5).tolist(), "angle": 0}],
        }
        with (
            patch.multiple(refine, feat=board, gap=np.full((2600, 1800), 255, np.uint8)),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = refine.solve(p)
        np.testing.assert_allclose(result["best"]["center"], expected, atol=1)
        self.assertGreater(result["best"]["score"], 0.99)
        self.assertEqual(result["best"]["gapFraction"], 1)
        self.assertEqual(result["best"]["siftInliers"], 0)
        self.assertIsNone(result["margin"])
