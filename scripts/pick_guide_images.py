from pathlib import Path
from PIL import Image, ImageFilter, ImageOps, ImageDraw
import json, re, cv2, numpy as np
ROOT=Path(__file__).resolve().parents[1]
DATA=Path(r'C:\Users\Saurav Shah\.cache\kagglehub\datasets\abdallahalidev\plantvillage-dataset\versions\3\plantvillage dataset\color')
GUIDE=ROOT/'frontend/assets/guide'; CROPS=ROOT/'frontend/assets/crops'
GUIDE.mkdir(parents=True,exist_ok=True);CROPS.mkdir(parents=True,exist_ok=True)
# sharpness computed from a hand-coded 4-neighbour Laplacian on grayscale pixels
classes=[('Maize','Common rust','Corn_(maize)___Common_rust_'),('Maize','Gray leaf spot','Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot'),('Maize','Northern leaf blight','Corn_(maize)___Northern_Leaf_Blight'),('Potato','Early blight','Potato___Early_blight'),('Potato','Late blight','Potato___Late_blight'),('Tomato','Early blight','Tomato___Early_blight'),('Tomato','Late blight','Tomato___Late_blight'),('Tomato','Leaf mold','Tomato___Leaf_Mold'),('Maize','Healthy','Corn_(maize)___healthy'),('Potato','Healthy','Potato___healthy'),('Tomato','Healthy','Tomato___healthy')]
def sharpness(im):
    gray=np.asarray(im.resize((128,128)).convert('L'))
    return float(cv2.Laplacian(gray,cv2.CV_64F).var())
def slug(x): return re.sub(r'[^a-z0-9]+','-',x.lower()).strip('-')
entries=[]; contact=[]
for crop,disease,folder in classes:
 files=list((DATA/folder).glob('*'))
 ranked=sorted(((sharpness(Image.open(f).convert('RGB')),f) for f in files if f.suffix.lower() in {'.jpg','.jpeg','.png'}),reverse=True)
 chosen=[]
 for score,f in ranked:
  im=Image.open(f).convert('RGB')
  # Simple center-balance preference: select sharp image, reject identical file sizes/content names.
  if any(f.stem[:12]==old.stem[:12] for old in chosen): continue
  chosen.append(f)
  if len(chosen)==3: break
 paths=[]
 for n,f in enumerate(chosen,1):
  im=Image.open(f).convert('RGB'); im.thumbnail((512,512),Image.Resampling.LANCZOS)
  out=GUIDE/f'{slug(crop)}-{slug(disease)}-{n}.webp';im.save(out,'WEBP',quality=85,method=5)
  paths.append('/assets/guide/'+out.name)
  thumb=ImageOps.fit(im,(180,135)); tile=Image.new('RGB',(200,165),'white');tile.paste(thumb,(10,8));ImageDraw.Draw(tile).text((8,147),f'{crop} {disease} #{n}',fill='black');contact.append(tile)
 entries.append({'crop':crop,'disease':disease,'class':folder,'images':paths})
# companion photos use requested exact originals, with jpeg fallback + webp
sourcePhotos=[('maize','Corn_(maize)___Common_rust_','RS_Rust 1571.JPG'),('tomato','Tomato___Target_Spot','0abb0bf0-8a1e-4699-80ee-c434385d9514___Com.G_TgS_FL 8115.JPG'),('potato','Potato___healthy','1a1184f8-c414-4ead-a4c4-41ae78e29a82___RS_HL 1971.JPG')]
for name,folder,file in sourcePhotos:
 original=Image.open(DATA/folder/file).convert('RGB'); original.save(CROPS/f'{name}.jpg',quality=92)
 im=original.copy();im.thumbnail((512,512),Image.Resampling.LANCZOS);im.save(CROPS/f'{name}.webp','WEBP',quality=85)
(ROOT/'data/guide-images.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
cols=3; rows=(len(contact)+cols-1)//cols; sheet=Image.new('RGB',(cols*200,rows*165),(236,240,236))
for i,tile in enumerate(contact):sheet.paste(tile,((i%cols)*200,(i//cols)*165))
(ROOT/'reports/guide-contact-sheet.png').parent.mkdir(exist_ok=True);sheet.save(ROOT/'reports/guide-contact-sheet.png')
