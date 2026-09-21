"""Reproducible photo-based puzzle matching. All coordinates use rectified artwork."""
import cv2 as cv
import numpy as np
from pathlib import Path
import json, math
from scipy import ndimage

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)
cv.setNumThreads(4)

def read(name, width=None):
    im=cv.imread(str(ROOT/'images'/name))
    if width: im=cv.resize(im,(width,round(im.shape[0]*width/im.shape[1])))
    return im

def warp(im, corners, size=(1800,2600)):
    w,h=size
    H=cv.getPerspectiveTransform(np.float32(corners),np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]]))
    return cv.warpPerspective(im,H,size),H

def prepare():
    ref,_=warp(read('box-photo.jpg',1373),[[205,64],[1277,86],[1283,1635],[153,1623]])
    cv.imwrite(str(OUT/'reference.jpg'),ref)
    low,_=warp(read('reference-box.png'),[[153,60],[748,62],[748,927],[152,936]])
    cv.imwrite(str(OUT/'reference-clean.jpg'),low)
    state,H=warp(read('puzzle-state.jpg',1373),[[128,46],[1254,60],[1365,1763],[27,1780]])
    # Feature registration refines the manually identified outer corners.
    sift=cv.SIFT_create(nfeatures=22000,contrastThreshold=.02)
    k1,d1=sift.detectAndCompute(cv.cvtColor(state,cv.COLOR_BGR2GRAY),None)
    k2,d2=sift.detectAndCompute(cv.cvtColor(ref,cv.COLOR_BGR2GRAY),None)
    matches=cv.BFMatcher().knnMatch(d1,d2,k=2)
    good=[m for m,n in matches if m.distance<.7*n.distance]
    HH,keep=cv.findHomography(np.float32([k1[m.queryIdx].pt for m in good]),np.float32([k2[m.trainIdx].pt for m in good]),cv.RANSAC,4)
    state=cv.warpPerspective(state,HH,(1800,2600))
    cv.imwrite(str(OUT/'state.jpg'),state)
    print('State registration:',int(keep.sum()),'inliers',flush=True)
    sheets=[
      ('A','sheet-a-main.jpg',1373,[[110,90],[1215,87],[1225,1665],[96,1670]],(1400,2000),10,7),
      ('B','sheet-b-main.jpg',900,[[54,64],[810,63],[818,1158],[27,1150]],(1400,2000),9,8),
      ('C','sheet-c-main.jpg',900,[[34,233],[809,227],[820,562],[22,566]],(1400,600),2,6),
    ]
    pieces=[]
    for name,source,width,corners,size,rows,cols in sheets:
        sheet,_=warp(read(source,width),corners,size)
        hsv=cv.cvtColor(sheet,cv.COLOR_BGR2HSV)
        mask=np.uint8((hsv[:,:,1]>55)&(hsv[:,:,2]>45))*255
        mask=cv.morphologyEx(mask,cv.MORPH_CLOSE,np.ones((5,5),np.uint8))
        cs,_=cv.findContours(mask,cv.RETR_EXTERNAL,cv.CHAIN_APPROX_SIMPLE)
        cv.drawContours(mask,cs,-1,255,-1)
        # Narrow cuts across accidental contacts on the source sheets.
        cuts={'A':[(370,252,560,252),(365,398,560,398),(515,424,720,424),(730,421,950,421),(790,1368,980,1368)],
              'B':[(1215,470,1215,690),(225,1100,225,1330),(575,1129,750,1129),(1200,1149,1390,1149)],'C':[]}
        for x0,y0,x1,y1 in cuts[name]:cv.line(mask,(x0,y0),(x1,y1),0,4)
        contours,_=cv.findContours(mask,cv.RETR_EXTERNAL,cv.CHAIN_APPROX_SIMPLE)
        contours=[c for c in contours if cv.contourArea(c)>1600]
        annotated=sheet.copy()
        for c in contours:
            x,y,w,h=cv.boundingRect(c); M=cv.moments(c);cx=M['m10']/M['m00'];cy=M['m01']/M['m00']
            if name=='A':
                row=int(np.argmin(abs(np.array([140,340,510,700,895,1090,1280,1480,1680,1880])-cy)))
                xs=[120,310,500,690,885,1085,1290] if row<5 else [120,340,520,710,905,1100,1285]
                col=int(np.argmin(abs(np.array(xs)-cx)))
            elif name=='B':
                row=int(np.argmin(abs(np.array([120,350,565,790,1010,1230,1450,1660,1890])-cy)))
                xs=[120,315,490,670,845,1000,1150,1305]
                if row==7:xs=[150,320,510,700,905,1130,1310]
                if row==8:xs=[150,340,515,710,930,1090,1310]
                col=int(np.argmin(abs(np.array(xs)-cx)))
            else:
                row=0 if cy<260 else 1; col=int(round((cx-125)/198))
            pid=f'{name}-{chr(97+row)}{col+1}'
            if any(p['id']==pid for p in pieces):pid+='x'
            pad=8;x0=max(0,x-pad);y0=max(0,y-pad);x1=min(size[0],x+w+pad);y1=min(size[1],y+h+pad)
            fullmask=np.zeros(sheet.shape[:2],np.uint8);cv.drawContours(fullmask,[c],-1,255,-1)
            crop=sheet[y0:y1,x0:x1];pmask=fullmask[y0:y1,x0:x1]
            cv.imwrite(str(OUT/'pieces'/f'{pid}.png'),np.dstack([crop,pmask]))
            pieces.append(dict(id=pid,sheet=name,row=row,col=col,bbox=[x0,y0,x1,y1],center=[cx-x0,cy-y0],area=cv.contourArea(c),contour=(c[:,0,:]-[x0,y0]).tolist()))
            cv.drawContours(annotated,[c],-1,(0,160,0),2)
            cv.putText(annotated,pid,(x,max(18,y)),cv.FONT_HERSHEY_SIMPLEX,.7,(255,0,0),2)
        cv.imwrite(str(OUT/f'sheet-{name}.jpg'),sheet)
        cv.imwrite(str(OUT/f'sheet-{name}-labels.jpg'),annotated)
        print(name,len(contours),'objects',flush=True)
    pieces.sort(key=lambda p:(p['sheet'],p['row'],p['col']))
    (OUT/'pieces.json').write_text(json.dumps(pieces,indent=2))

def match():
    pieces=json.loads((OUT/'pieces.json').read_text())
    sift=cv.SIFT_create(nfeatures=35000,contrastThreshold=.012,edgeThreshold=15)
    refs=[]
    for name in ['reference','reference-clean']:
        im=cv.imread(str(OUT/f'{name}.jpg'))
        gray=cv.cvtColor(im,cv.COLOR_BGR2GRAY)
        kp,des=sift.detectAndCompute(gray,None)
        refs.append((name,im,kp,des))
        print(name,len(kp),'features',flush=True)
    bf=cv.BFMatcher()
    results=[]
    for i,p in enumerate(pieces):
        im=cv.imread(str(OUT/'pieces'/f'{p["id"]}.png'),cv.IMREAD_UNCHANGED)
        mask=cv.erode(im[:,:,3],np.ones((9,9),np.uint8))
        kp,des=sift.detectAndCompute(cv.cvtColor(im[:,:,:3],cv.COLOR_BGR2GRAY),mask)
        candidates=[]
        if des is not None and len(kp)>3:
            for name,ref,rkp,rdes in refs:
                ms=bf.knnMatch(des,rdes,k=2)
                for ratio in [.7,.8,.9]:
                    good=[m for m,n in ms if m.distance<ratio*n.distance]
                    if len(good)<3: continue
                    src=np.float32([kp[m.queryIdx].pt for m in good]);dst=np.float32([rkp[m.trainIdx].pt for m in good])
                    H,inliers=cv.estimateAffinePartial2D(src,dst,method=cv.RANSAC,ransacReprojThreshold=3,maxIters=5000,confidence=.999)
                    if H is None: continue
                    scale=np.linalg.norm(H[:,0]); n=int(inliers.sum())
                    if n<3 or not .25<scale<1.5: continue
                    center=(H@np.array([*p['center'],1])).tolist()
                    if not (0<center[0]<1800 and 0<center[1]<2600): continue
                    residual=np.linalg.norm(src@H[:,:2].T+H[:,2]-dst,axis=1)[inliers.ravel().astype(bool)]
                    pts=src[inliers.ravel().astype(bool)]
                    spread=float(cv.contourArea(cv.convexHull(pts)))/p['area'] if len(pts)>2 else 0
                    candidates.append(dict(reference=name,H=H.tolist(),center=center,inliers=n,total=len(good),error=float(np.median(residual)),spread=spread,scale=scale,angle=math.degrees(math.atan2(H[1,0],H[0,0])),ratio=ratio))
        candidates.sort(key=lambda c:(c['inliers']+min(c['spread'],.3)*10-c['error']),reverse=True)
        p['candidates']=candidates[:6]
        p['match']=candidates[0] if candidates else None
        results.append(p)
        print(p['id'], ('%.0f matches at %.0f,%.0f'%(p['match']['inliers'],*p['match']['center'])) if candidates else 'unmatched',flush=True)
    (OUT/'matches.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':
    import sys
    if len(sys.argv)<2 or sys.argv[1]=='prepare':prepare()
    if len(sys.argv)<2 or sys.argv[1]=='match':match()
