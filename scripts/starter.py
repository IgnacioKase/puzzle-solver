"""A compact first group to assemble, drawn from accepted placements."""
import json,cv2 as cv,numpy as np
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
O=Path(__file__).resolve().parents[1]/'output'
ps={p['id']:p for p in json.loads((O/'guide-data.json').read_text())['pieces']}
raw={p['id']:p for p in json.loads((O/'refined.json').read_text())}
ids=['A-d5','A-b7','C-b4','B-h3','B-i1']
state=cv.imread(str(O/'state.jpg'));ref=cv.imread(str(O/'reference.jpg'))
assembled=state.copy()
for pid in ids:
    im=cv.imread(str(O/'pieces'/f'{pid}.png'),-1);H=np.array(raw[pid]['best']['H'])
    warped=cv.warpAffine(im[:,:,:3],H,(1800,2600));m=cv.warpAffine(im[:,:,3],H,(1800,2600))>128
    assembled[m]=warped[m]
    cv.polylines(assembled,[np.int32(ps[pid]['polygon'])],True,(50,220,90),2)
box=(1080,1000,1400,1385)
canvas=Image.new('RGB',(1450,1160),'#f5f3ec');d=ImageDraw.Draw(canvas)
def font(size):return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',size)
d.text((30,20),'Start here: five pieces in the large middle-right gap',font=font(27),fill='#183e35')
d.text((30,64),'Use the labeled sheets to find each piece. Rotations are clockwise from its sheet photo.',font=font(17),fill='#455b50')
for x,title,img in [(30,'Your current puzzle',state),(480,'Proposed five-piece group',assembled),(930,'Matching box artwork',ref)]:
    crop=Image.fromarray(cv.cvtColor(img,cv.COLOR_BGR2RGB)).crop(box).resize((420,505))
    canvas.paste(crop,(x,130));d.text((x,100),title,font=font(19),fill='#183e35')
    if x==480:
        for pid in ids:
            p=ps[pid];xx=x+(p['x']-box[0])*420/(box[2]-box[0]);yy=130+(p['y']-box[1])*505/(box[3]-box[1])
            d.text((xx-27,yy-8),pid,font=font(17),fill='white',stroke_width=2,stroke_fill='black')
for i,pid in enumerate(ids):
    p=ps[pid];x=30+i*280
    im=Image.open(O/'pieces'/f'{pid}.png').convert('RGBA');im.thumbnail((230,200))
    canvas.paste(im,(x+15,680),im)
    d.text((x,900),pid,font=font(24),fill='#183e35')
    d.text((x,938),f"Turn {p['angle']} degrees clockwise",font=font(15),fill='#183e35')
    d.text((x,965),f"{p['x']/18:.1f}% across / {p['y']/26:.1f}% down",font=font(15),fill='#455b50')
d.text((30,1030),'Likely joins: A-d5 left of A-b7; C-b4 below A-b7; B-h3 below C-b4; B-i1 below B-h3.',font=font(18),fill='#183e35')
d.text((30,1070),'Check the physical tabs and sockets. The guide includes another 104 high-confidence entries.',font=font(17),fill='#455b50')
canvas.save(O/'start-here.jpg',quality=94)
