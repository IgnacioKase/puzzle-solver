"""Refine candidates locally and assess artwork agreement and gap overlap."""
import cv2 as cv, numpy as np, json, math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dense import features, transformed
O=Path(__file__).resolve().parents[1]/'output'
cv.setNumThreads(1)
ref=cv.imread(str(O/'reference.jpg')); feat=features(cv.GaussianBlur(ref,(0,0),1.2))
state=cv.imread(str(O/'state.jpg'));hsv=cv.cvtColor(state,cv.COLOR_BGR2HSV)
gap=np.uint8((hsv[:,:,1]<65)&(hsv[:,:,2]>130))*255
gap=cv.morphologyEx(gap,cv.MORPH_OPEN,np.ones((11,11),np.uint8))
gap=cv.dilate(gap,np.ones((9,9),np.uint8))
sifts={p['id']:p for p in json.loads((O/'matches.json').read_text())}

def solve(p):
    im=cv.imread(str(O/'pieces'/f'{p["id"]}.png'),cv.IMREAD_UNCHANGED)
    f=features(cv.GaussianBlur(im[:,:,:3],(0,0),1.8))
    mask=cv.erode(im[:,:,3],np.ones((9,9),np.uint8))
    candidates=p['dense'][:]
    sm=sifts[p['id']]['match']
    if sm and sm['inliers']>=3 and .52<sm['scale']<.64:candidates.append({**sm,'score':0})
    distinct=[]
    for c in candidates:
        if not any(np.linalg.norm(np.array(c['center'])-d['center'])<35 and abs((c['angle']-d['angle']+180)%360-180)<20 for d in distinct):distinct.append(c)
    refined=[]
    for cand in distinct[:5]:
        x,y=cand['center']; x0=max(0,int(x)-180);y0=max(0,int(y)-180);x1=min(1800,int(x)+180);y1=min(2600,int(y)+180)
        roi=feat[y0:y1,x0:x1];best=None
        for angle in np.arange(cand['angle']-6,cand['angle']+6.1,2):
            for scale in [.56,.577,.595]:
                patch,pm,H=transformed(f,mask,angle,scale); pm=np.float32(pm>200)
                if patch.shape[0]>=roi.shape[0] or patch.shape[1]>=roi.shape[1] or pm.sum()<100:continue
                score=cv.matchTemplate(roi,patch,cv.TM_CCOEFF_NORMED,mask=pm)
                np.nan_to_num(score,copy=False,nan=-1,posinf=-1,neginf=-1)
                _,v,_,pos=cv.minMaxLoc(score)
                if best is None or v>best['score']:
                    HH=H.copy();HH[:,2]+=np.array(pos)+[x0,y0]
                    center=HH@np.array([*p['center'],1])
                    best=dict(score=v,angle=float(angle),scale=scale,H=HH.tolist(),center=center.tolist())
        if best:
            HH=np.array(best['H']);wm=cv.warpAffine(mask,HH,(1800,2600))>200
            best['gapFraction']=float((gap[wm]>0).mean()) if wm.sum() else 0
            best['siftInliers']=sm['inliers'] if sm and np.linalg.norm(np.array(sm['center'])-best['center'])<18 else 0
            refined.append(best)
    refined.sort(key=lambda c:c['score'],reverse=True)
    p['refined']=refined
    if refined:
        best=refined[0];alts=[c for c in refined[1:] if np.linalg.norm(np.array(c['center'])-best['center'])>40 or abs((c['angle']-best['angle']+180)%360-180)>35]
        p['margin']=best['score']-alts[0]['score'] if alts else None
        p['best']=best
        print(p['id'],round(best['score'],3),'gap',round(best['gapFraction'],2),'SIFT',best['siftInliers'],flush=True)
    return p

if __name__=='__main__':
    ps=json.loads((O/'dense.json').read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:res=list(pool.map(solve,ps))
    (O/'refined.json').write_text(json.dumps(res,indent=2))
