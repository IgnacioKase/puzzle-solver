"""Masked, rotation-invariant appearance matching against the box photograph."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2 as cv
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "output"
cv.setNumThreads(1)
factor = 3


def features(im):
    lab = cv.cvtColor(im, cv.COLOR_BGR2LAB).astype(np.float32)
    lab[:, :, 0] = (lab[:, :, 0] - 128) * 0.35
    lab[:, :, 1] -= 128
    lab[:, :, 2] -= 128
    return lab / 64


ref = cv.imread(str(OUT / "reference.jpg"))
ref = cv.resize(ref, (600, 867), interpolation=cv.INTER_AREA)
feat = features(ref)
state = cv.resize(cv.imread(str(OUT / "state.jpg")), (600, 867), interpolation=cv.INTER_AREA)
hsv = cv.cvtColor(state, cv.COLOR_BGR2HSV)
gap = np.uint8((hsv[:, :, 1] < 65) & (hsv[:, :, 2] > 130)) * 255
gap = cv.dilate(gap, np.ones((9, 9), np.uint8))


def transformed(im, mask, angle, scale):
    h, w = im.shape[:2]
    H = cv.getRotationMatrix2D((w / 2, h / 2), -angle, scale)
    ow = int(scale * (abs(w * np.cos(np.deg2rad(angle))) + abs(h * np.sin(np.deg2rad(angle))))) + 4
    oh = int(scale * (abs(h * np.cos(np.deg2rad(angle))) + abs(w * np.sin(np.deg2rad(angle))))) + 4
    H[:, 2] += [ow / 2 - w / 2, oh / 2 - h / 2]
    return cv.warpAffine(im, H, (ow, oh)), cv.warpAffine(mask, H, (ow, oh)), H


def solve(p):
    t = time.time()
    im = cv.imread(str(OUT / "pieces" / f"{p['id']}.png"), cv.IMREAD_UNCHANGED)
    mask = cv.erode(im[:, :, 3], np.ones((11, 11), np.uint8))
    f = features(cv.GaussianBlur(im[:, :, :3], (0, 0), 1.2))
    candidates = []
    scale = 0.577 / factor
    for angle in range(-180, 180, 10):
        patch, pm, H = transformed(f, mask, angle, scale)
        pm = np.float32(pm > 200)
        if pm.sum() < 25:
            continue
        score = cv.matchTemplate(feat, patch, cv.TM_CCOEFF_NORMED, mask=pm)
        np.nan_to_num(score, copy=False, nan=-1, posinf=-1, neginf=-1)
        cx, cy = H @ np.array([*p["center"], 1])
        dx = int(cx)
        dy = int(cy)
        ok = gap[dy : dy + score.shape[0], dx : dx + score.shape[1]]
        if ok.shape != score.shape:
            continue
        score[ok == 0] = -1
        for _ in range(2):
            _, v, _, pos = cv.minMaxLoc(score)
            x, y = pos
            HH = H.copy()
            HH[:, 2] += [x, y]
            candidates.append(
                {
                    "score": v,
                    "angle": angle,
                    "H": (HH * factor).tolist(),
                    "center": ((HH @ np.array([*p["center"], 1])) * factor).tolist(),
                }
            )
            score[max(0, y - 22) : y + 23, max(0, x - 22) : x + 23] = -1
    candidates.sort(key=lambda c: c["score"], reverse=True)
    result = {**p, "dense": candidates[:8]}
    print(
        p["id"],
        round(candidates[0]["score"], 3) if candidates else None,
        "%.1fs" % (time.time() - t),
        flush=True,
    )
    return result


if __name__ == "__main__":
    import sys

    ps = json.loads((OUT / "pieces.json").read_text())
    if len(sys.argv) > 1:
        ps = [p for p in ps if p["id"] in sys.argv[1:]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(solve, ps))
    (OUT / ("dense-test.json" if len(sys.argv) > 1 else "dense.json")).write_text(
        json.dumps(results, indent=2)
    )
