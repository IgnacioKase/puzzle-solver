"""Illustrate an upper-left candidate without claiming a physically confirmed fit."""
import json
from pathlib import Path

import cv2 as cv
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
ASSETS = ROOT / 'docs' / 'assets'
ASSETS.mkdir(exist_ok=True)
pieces = {p['id']: p for p in json.loads((OUT / 'guide-data.json').read_text())['pieces']}
raw = {p['id']: p for p in json.loads((OUT / 'refined.json').read_text())}
ids = ['A-g5', 'B-a4']
state = cv.imread(str(OUT / 'state.jpg'))
reference = cv.imread(str(OUT / 'reference.jpg'))
proposed = state.copy()
for pid in ids:
    im = cv.imread(str(OUT / 'pieces' / f'{pid}.png'), cv.IMREAD_UNCHANGED)
    transform = np.array(raw[pid]['best']['H'])
    warped = cv.warpAffine(im[:, :, :3], transform, (1800, 2600))
    mask = cv.warpAffine(im[:, :, 3], transform, (1800, 2600)) > 128
    proposed[mask] = warped[mask]
    cv.polylines(proposed, [np.int32(pieces[pid]['polygon'])], True, (50, 220, 90), 2)

canvas = Image.new('RGB', (1450, 1010), '#f5f3ec')
draw = ImageDraw.Draw(canvas)
def font(size):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)

draw.text((30, 20), 'How a placement is checked: the small upper-left gap', font=font(27), fill='#183e35')
draw.text((30, 64), 'Illustrative candidates A-g5 and B-a4. Their individual physical fits have not been confirmed.', font=font(18), fill='#455b50')
box = (0, 245, 350, 610)
for x, title, image in [(30, '1. Gap in the supplied photograph', state),
                         (500, '2. Actual piece crops placed over it', proposed),
                         (970, '3. Corresponding box artwork', reference)]:
    crop = Image.fromarray(cv.cvtColor(image, cv.COLOR_BGR2RGB)).crop(box).resize((440, 459))
    canvas.paste(crop, (x, 135))
    draw.text((x, 108), title, font=font(18), fill='#183e35')
    if x == 500:
        for pid in ids:
            p = pieces[pid]
            xx = x + (p['x'] - box[0]) * 440 / (box[2] - box[0])
            yy = 135 + (p['y'] - box[1]) * 459 / (box[3] - box[1])
            draw.text((xx - 25, yy - 8), pid, font=font(18), fill='white', stroke_width=2, stroke_fill='black')

for x, pid in [(30, ids[0]), (490, ids[1])]:
    p = pieces[pid]
    crop = Image.open(OUT / 'pieces' / f'{pid}.png').convert('RGBA')
    crop.thumbnail((150, 165))
    canvas.paste(crop, (x, 665), crop)
    draw.text((x + 175, 665), pid, font=font(25), fill='#183e35')
    draw.text((x + 175, 710), f"Turn {p['angle']} degrees clockwise", font=font(16), fill='#183e35')
    draw.text((x + 175, 745), f"{p['x']/18:.1f}% across / {p['y']/26:.1f}% down", font=font(16), fill='#455b50')
    draw.text((x + 175, 780), 'From the upright source crop', font=font(15), fill='#455b50')

overview = Image.fromarray(cv.cvtColor(state, cv.COLOR_BGR2RGB))
overview.thumbnail((210, 290))
canvas.paste(overview, (1165, 645))
sx = overview.width / 1800
sy = overview.height / 2600
draw.rectangle((1165 + box[0]*sx, 645 + box[1]*sy, 1165 + box[2]*sx, 645 + box[3]*sy), outline='#00aa55', width=3)
draw.text((970, 635), 'Location on the board', font=font(17), fill='#183e35')
draw.text((30, 880), 'Evidence: matching artwork, the photographed empty area, and the surrounding piece boundaries.', font=font(19), fill='#183e35')
draw.text((30, 920), 'The middle panel is a computed overlay, not a photograph of a completed assembly.', font=font(18), fill='#455b50')
canvas.save(ASSETS / 'upper-left-example.jpg', quality=94)
canvas.save(OUT / 'start-here.jpg', quality=94)

# Show the same piece as artwork, a filled binary mask, and an outline.
im = Image.open(OUT / 'pieces' / 'B-a4.png').convert('RGBA')
canvas = Image.new('RGB', (1230, 460), '#f5f3ec')
draw = ImageDraw.Draw(canvas)
draw.text((24, 15), 'One inventory entry, three useful representations: B-a4', font=font(25), fill='#183e35')
alpha = np.array(im.getchannel('A'))
contours, _ = cv.findContours(alpha, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
outline = np.zeros_like(alpha)
cv.drawContours(outline, contours, -1, 255, 2)
for x, title, graphic in [(30, 'Color artwork', im), (440, 'Binary mask: white = piece', Image.fromarray(alpha).convert('RGBA')),
                            (850, 'Outline: physical boundary', Image.fromarray(outline).convert('RGBA'))]:
    graphic.thumbnail((290, 285))
    canvas.paste(graphic, (x + 35, 105), graphic)
    draw.text((x, 65), title, font=font(20), fill='#183e35')
draw.text((30, 412), 'Color suggests a location. The mask excludes paper. The outline supports geometric checks.', font=font(20), fill='#455b50')
canvas.save(ASSETS / 'piece-representations.png')

canvas = Image.new('RGB', (1450, 820), '#f5f3ec')
draw = ImageDraw.Draw(canvas)
draw.text((25, 15), 'Three kinds of source photographs', font=font(27), fill='#183e35')
for x, label, name in [(25, 'Loose pieces on numbered sheets', 'sheet-a-main.jpg'),
                        (505, 'Puzzle state when photographed', 'puzzle-state.jpg'),
                        (985, 'Box artwork used as reference', 'box-photo.jpg')]:
    im = Image.open(ROOT / 'images' / name).convert('RGB')
    im.thumbnail((440, 675))
    canvas.paste(im, (x, 105))
    draw.text((x, 67), label, font=font(19), fill='#183e35')
canvas.save(ASSETS / 'source-photos.jpg', quality=92)
