from pathlib import Path
from PIL import Image, ImageFilter, ImageOps, ImageDraw
import cv2, numpy as np
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'frontend/assets/leaf-sequence'
OUT=SRC/'webp'; MOBILE=SRC/'webp-mobile'
OUT.mkdir(exist_ok=True); MOBILE.mkdir(exist_ok=True)
for i in range(1,181):
    source=SRC/f'ezgif-frame-{i:03}.png'
    rgb=np.asarray(Image.open(source).convert('RGB'))
    # Consistent frame-independent neutral studio and floor-shadow classifier.
    spread=rgb.max(axis=2).astype(np.int16)-rgb.min(axis=2).astype(np.int16)
    neutral=(spread<=18)&(rgb.mean(axis=2)>=82)
    # Close tiny JPEG-like background gaps so the connected matte also removes the soft ground shadow.
    neutral=cv2.morphologyEx(neutral.astype(np.uint8),cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))>0
    count,labels=cv2.connectedComponents(neutral.astype(np.uint8),8)
    border=np.unique(np.concatenate((labels[0],labels[-1],labels[:,0],labels[:,-1])))
    bg=np.isin(labels,border)&neutral
    # A one-pixel blurred alpha edge avoids a hard matte while retaining leaf detail.
    alpha=(~bg).astype(np.uint8)*255
    rgba=Image.fromarray(np.dstack((rgb,alpha)),'RGBA')
    rgba.putalpha(rgba.getchannel('A').filter(ImageFilter.GaussianBlur(1.35)))
    rgba.save(OUT/f'frame-{i:03}.webp','WEBP',quality=80,method=5)
    small=rgba.copy();small.thumbnail((720,720),Image.Resampling.LANCZOS)
    small.save(MOBILE/f'frame-{i:03}.webp','WEBP',quality=80,method=5)
    if i%20==0: print('processed',i)
# Light/dark visual review composite of frames 1,60,120,180.
thumbs=[]
for theme,bg in [('light',(247,250,247)),('dark',(15,26,20))]:
 for frame in (1,60,120,180):
    im=Image.open(OUT/f'frame-{frame:03}.webp').convert('RGBA');im.thumbnail((360,203))
    tile=Image.new('RGB',(380,245),bg);tile.paste(im,((380-im.width)//2,25),im)
    ImageDraw.Draw(tile).text((12,220),f'{theme} · frame {frame}',fill=(20,35,27) if theme=='light' else (234,243,237))
    thumbs.append(tile)
sheet=Image.new('RGB',(760,980),(235,235,235))
for n,im in enumerate(thumbs):sheet.paste(im,((n%2)*380,(n//2)*245))
report=ROOT/'reports/frame-check.png';report.parent.mkdir(exist_ok=True);sheet.save(report)
