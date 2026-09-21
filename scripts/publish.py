"""Build the offline guide, CSV and static visual placement maps."""

import csv
import json
import math
from pathlib import Path

import cv2 as cv
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

OUT = Path(__file__).resolve().parents[1] / "output"


def region(x, y):
    if x < 600 and y < 500:
        return "Small top-left blossom gap"
    if y < 400:
        return "Top-right blossom gap"
    if x < 700 and y < 900:
        return "Left of raised sleeve"
    if x < 550 and y < 1500:
        return "Left of green sleeve"
    if x < 550:
        return "Lower-left blossoms"
    if y < 850:
        return "Gold area right of head"
    if y < 1450:
        return "Large middle-right gap"
    if y < 1700:
        return "Waist / blue branch area"
    if y < 2200:
        return "Large lower-right gap"
    return "Bottom red hem"


def main():
    ps = json.loads((OUT / "refined.json").read_text())
    (OUT / "previews").mkdir(exist_ok=True)
    ref = cv.imread(str(OUT / "reference.jpg"))
    state = cv.imread(str(OUT / "state.jpg"))
    guide = []
    masks = {}
    trees = {}
    contours = {}
    manual = json.loads((OUT / "review.json").read_text()) if (OUT / "review.json").exists() else {}
    for p in ps:
        b = p.get("best")
        status = "unresolved"
        note = "No reliable placement found."
        if b:
            s = b["score"]
            g = b["gapFraction"]
            n = b["siftInliers"]
            margin = p["margin"]
            if s >= 0.9 and g >= 0.84 and (margin is None or margin >= 0.025 or n >= 4):
                status = "high"
            elif s >= 0.8 and g >= 0.72 and (margin is None or margin >= 0.018 or n >= 3):
                status = "medium"
            note = "Artwork match; confirm the physical tabs and sockets before placing."
            if status == "medium":
                note = "Tentative artwork match. Check the preview and physical fit."
            if status == "unresolved":
                note = "Pattern, glare, competing matches, or gap overlap prevented a reliable placement."
        if p["id"] in manual:
            status = manual[p["id"]]["status"]
            note = manual[p["id"]]["note"]
        pp = {
            "id": p["id"],
            "sheet": p["sheet"],
            "row": p["row"],
            "col": p["col"],
            "status": status,
            "score": b["score"] if b else None,
            "region": "",
            "note": note,
            "neighbors": [],
        }
        if status != "unresolved":
            H = np.array(b["H"])
            cx, cy = b["center"]
            pp.update(
                x=round(cx, 1), y=round(cy, 1), angle=round(b["angle"]) % 360, region=region(cx, cy)
            )
            contour = np.array(p["contour"], np.float32) @ H[:, :2].T + H[:, 2]
            pp["polygon"] = (
                cv.approxPolyDP(contour.astype(np.float32), 1.2, True)[:, 0, :].round(1).tolist()
            )
            contours[p["id"]] = contour
            trees[p["id"]] = cKDTree(contour)
            im = cv.imread(str(OUT / "pieces" / f"{p['id']}.png"), cv.IMREAD_UNCHANGED)
            wm = cv.warpAffine(im[:, :, 3], H, (1800, 2600))
            masks[p["id"]] = cv.resize(wm, (600, 867), interpolation=cv.INTER_NEAREST) > 128
            warped = cv.warpAffine(im[:, :, :3], H, (1800, 2600))
            x0 = max(0, int(cx) - 110)
            y0 = max(0, int(cy) - 110)
            x1 = min(1800, x0 + 220)
            y1 = min(2600, y0 + 220)
            r = ref[y0:y1, x0:x1].copy()
            over = r.copy()
            m = wm[y0:y1, x0:x1] > 128
            over[m] = warped[y0:y1, x0:x1][m]
            board = state[y0:y1, x0:x1].copy()
            board[m] = warped[y0:y1, x0:x1][m]
            tile = np.hstack([r, over, board])
            cv.imwrite(str(OUT / "previews" / f"{p['id']}.jpg"), tile)
        else:
            pp.update(x=None, y=None, angle=None)
        guide.append(pp)
    # Reject physically impossible overlaps between independent proposed placements.
    conflicts = []
    placed = [p for p in guide if p["status"] != "unresolved"]
    for i, p in enumerate(placed):
        for q in placed[i + 1 :]:
            if np.hypot(p["x"] - q["x"], p["y"] - q["y"]) > 240:
                continue
            overlap = (masks[p["id"]] & masks[q["id"]]).sum() / min(
                masks[p["id"]].sum(), masks[q["id"]].sum()
            )
            if overlap > 0.15:
                conflicts.append([p["id"], q["id"], round(float(overlap), 3)])
    (OUT / "conflicts.json").write_text(json.dumps(conflicts, indent=2))
    for i, p in enumerate(placed):
        for q in placed[i + 1 :]:
            dx = q["x"] - p["x"]
            dy = q["y"] - p["y"]
            if math.hypot(dx, dy) > 180:
                continue
            dist = trees[p["id"]].query(contours[q["id"]])[0]
            overlap = (masks[p["id"]] & masks[q["id"]]).sum() / min(
                masks[p["id"]].sum(), masks[q["id"]].sum()
            )
            if (dist < 9).sum() >= 6 and overlap < 0.1:
                direction = (
                    ("right" if dx > 0 else "left")
                    if abs(dx) > abs(dy) * 1.5
                    else ("below" if dy > 0 else "above")
                    if abs(dy) > abs(dx) * 1.5
                    else ("below-" if dy > 0 else "above-") + ("right" if dx > 0 else "left")
                )
                rev = {
                    "right": "left",
                    "left": "right",
                    "below": "above",
                    "above": "below",
                    "below-right": "above-left",
                    "below-left": "above-right",
                    "above-right": "below-left",
                    "above-left": "below-right",
                }[direction]
                p["neighbors"].append({"id": q["id"], "direction": direction})
                q["neighbors"].append({"id": p["id"], "direction": rev})
    summary = {s: sum(p["status"] == s for p in guide) for s in ["high", "medium", "unresolved"]}
    summary["total"] = len(guide)
    data = {"width": 1800, "height": 2600, "pieces": guide, "summary": summary}
    (OUT / "guide-data.js").write_text("window.PUZZLE_DATA=" + json.dumps(data) + ";\n")
    (OUT / "guide-data.json").write_text(json.dumps(data, indent=2))
    with (OUT / "placements.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "confidence",
                "x_percent_from_left",
                "y_percent_from_top",
                "clockwise_degrees",
                "region",
                "possible_neighbors",
                "artwork_similarity",
            ]
        )
        for p in guide:
            writer.writerow(
                [
                    p["id"],
                    p["status"],
                    round(p["x"] / 18, 1) if p["x"] else "",
                    round(p["y"] / 26, 1) if p["y"] else "",
                    p["angle"],
                    p["region"],
                    "; ".join(n["id"] + " " + n["direction"] for n in p["neighbors"]),
                    round(p["score"], 3) if p["score"] else "",
                ]
            )
    for mode, bg in [("reference", ref), ("state", state)]:
        canvas = bg.copy()
        for p in placed:
            color = (65, 210, 100) if p["status"] == "high" else (30, 180, 255)
            cv.polylines(canvas, [np.int32(p["polygon"])], True, color, 2)
            x, y = int(p["x"]), int(p["y"])
            label = p["id"]
            cv.putText(
                canvas, label, (x - 30, y), cv.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv.LINE_AA
            )
            cv.putText(
                canvas,
                label,
                (x - 30, y),
                cv.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
                cv.LINE_AA,
            )
        cv.imwrite(str(OUT / f"placement-map-{mode}.jpg"), canvas)
    # Inspection sheets: artwork, piece superimposed, current board with piece.
    for offset in range(0, len(placed), 24):
        page = Image.new("RGB", (1320, 8 * 250), "#f5f5f5")
        d = ImageDraw.Draw(page)
        for j, p in enumerate(placed[offset : offset + 24]):
            tile = Image.open(OUT / "previews" / f"{p['id']}.jpg")
            tile.thumbnail((435, 210))
            x = (j % 3) * 440
            y = (j // 3) * 250
            d.text((x + 5, y + 8), f"{p['id']} {p['status']} {p['score']:.3f}", fill="black")
            page.paste(tile, (x, y + 30))
        page.save(OUT / f"review-{offset // 24 + 1}.jpg")
    print(json.dumps(summary))
    print("Conflicts:", conflicts)


if __name__ == "__main__":
    main()
