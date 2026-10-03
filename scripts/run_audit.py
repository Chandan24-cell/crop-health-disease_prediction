import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
import json, cv2, numpy as np, tensorflow as tf
from pathlib import Path
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'processed'; MODELS=ROOT/'models'; OUT=ROOT/'reports'; OUT.mkdir(exist_ok=True)
classes=json.loads((MODELS/'class_names.json').read_text(encoding='utf-8'))
model=tf.keras.models.load_model(MODELS/'crop_disease_model.keras')
test=tf.keras.utils.image_dataset_from_directory(DATA/'test', image_size=(224,224),batch_size=32,shuffle=False)
ys=[]; ps=[]
for x,y in test:
    pred=model.predict(x,verbose=0)
    ys.extend(y.numpy().tolist()); ps.extend(np.argmax(pred,axis=1).tolist())
cm=confusion_matrix(ys,ps,labels=list(range(len(classes))))
report=classification_report(ys,ps,labels=list(range(len(classes))),target_names=classes,output_dict=True,zero_division=0)
metrics={'accuracy':float(accuracy_score(ys,ps)),'macro_f1':float(f1_score(ys,ps,labels=list(range(len(classes))),average='macro',zero_division=0)),'per_class':{c:{'precision':report[c]['precision'],'recall':report[c]['recall'],'f1':report[c]['f1-score'],'support':int(report[c]['support'])} for c in classes},'confusion_matrix':{'labels':classes,'counts':cm.tolist()},'evaluation':{'split':'test','sample_count':len(ys),'model':'models/crop_disease_model.keras','input_resize':[224,224],'batch_size':32,'class_order_source':'models/class_names.json; directory loader class order checked'} }
# Assert Keras directory order is the model order before publishing numbers.
if test.class_names != classes: raise ValueError(f'class order mismatch model={classes} data={test.class_names}')
(OUT/'baseline.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
print('BASELINE',json.dumps({'accuracy':metrics['accuracy'],'macro_f1':metrics['macro_f1'],'n':len(ys),'class_order':classes},indent=2))
# Perceptual hash (64-bit DCT pHash); BK-tree querying avoids all-pairs comparisons.
def phash(path):
    im=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
    if im is None: return None
    d=cv2.dct(cv2.resize(np.float32(im),(32,32)))[:8,:8]
    vals=d.flatten()[1:]
    med=np.median(vals)
    bits=0
    for v in vals: bits=(bits<<1)|int(v>med)
    return bits
class Node:
    def __init__(self,key,item): self.key=key; self.items=[item]; self.children={}
def dist(a,b): return (a^b).bit_count()
def insert(node,key,item):
    while True:
      d=dist(key,node.key)
      if d==0: node.items.append(item); return
      if d not in node.children: node.children[d]=Node(key,item); return
      node=node.children[d]
def query(node,key,r,out):
    if node is None:return
    d=dist(key,node.key)
    if d<=r: out.extend((x,d) for x in node.items)
    for edge,ch in node.children.items():
      if d-r<=edge<=d+r:query(ch,key,r,out)
files=[]
for split in ('train','val','test'):
  for cdir in sorted((DATA/split).iterdir()):
    if cdir.is_dir():
      for p in cdir.iterdir():
        if p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png','.bmp','.webp'):
          files.append({'path':p.relative_to(ROOT).as_posix(),'split':split,'class':cdir.name})
# All split-to-split pairs only (train/val/test); report image involvement per class.
root=None; hash_errors=[]; pairs=[]
for i,item in enumerate(files):
  h=phash(ROOT/item['path'])
  if h is None: hash_errors.append(item['path']); continue
  if root:
    matches=[]; query(root,h,6,matches)
    for prev,d in matches:
      if item['split'] != prev['split']:
        pairs.append({'a':prev,'b':item,'distance':d})
    insert(root,h,item)
  else: root=Node(h,item)
by_class={c:{'cross_split_images_involved':0,'cross_split_pairs':0} for c in classes}
seen={c:set() for c in classes}
pair_class_counts={}
for pair in pairs:
  a,b=pair['a'],pair['b']; k=' ↔ '.join(sorted((a['class'],b['class'])))
  pair_class_counts[k]=pair_class_counts.get(k,0)+1
  for it in (a,b): seen[it['class']].add(it['path'])
for c in classes: by_class[c]={'cross_split_images_involved':len(seen[c]),'cross_split_pairs':sum(1 for p in pairs if c in (p['a']['class'],p['b']['class']))}
(OUT/'duplicates.json').write_text(json.dumps({'method':'64-bit DCT pHash: grayscale 32x32, 8x8 low-frequency coefficients excluding DC, median threshold','max_hamming_distance':6,'images_scanned':len(files),'hash_failures':hash_errors,'cross_split_pair_count':len(pairs),'cross_split_images_involved':sum(len(x) for x in seen.values()),'per_class':by_class,'class_pair_counts':pair_class_counts,'pairs':[{'path_a':p['a']['path'],'class_a':p['a']['class'],'split_a':p['a']['split'],'path_b':p['b']['path'],'class_b':p['b']['class'],'split_b':p['b']['split'],'distance':p['distance']} for p in pairs]},indent=2),encoding='utf-8')
print('DUPLICATES',json.dumps({'images_scanned':len(files),'pairs':len(pairs),'involved_class_image_counts':{c:v['cross_split_images_involved'] for c,v in by_class.items()},'class_pair_counts':pair_class_counts},indent=2))

