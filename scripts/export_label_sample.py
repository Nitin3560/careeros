#!/usr/bin/env python3
import argparse, csv, datetime, random
import re
from pathlib import Path
from sqlalchemy import text
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'apps/api'))
from app.database import SessionLocal

GUIDE='''# Classifier label guide

Fill each `label_` column with the allowed values below. Leave `label_min_years` blank when no minimum is stated in a required section.

- `label_is_tech`: `y` or `n`. Software, data, ML, infrastructure, and security roles are `y`; mechanical, electrical, quality, clinical, sales, curriculum, trainer, and non-data analyst roles are `n`.
- `label_is_senior`: `y` or `n`. Senior, staff, principal, lead, manager, and level 3+ are `y`; new grad, junior, entry, associate, and levels I-II are `n`.
- `label_location_class`: `us`, `non_us`, or `unknown`.
- `label_sponsorship_block`: `y` or `n`. Use `y` only when the posting restricts the candidate through sponsorship, citizenship, clearance, or ITAR requirements.
- `label_min_years`: an integer minimum from the required section, or blank.
'''
FIELDS=['job_id','source','company','title','location','description_head','label_is_tech','label_is_senior','label_location_class','label_sponsorship_block','label_min_years']

def choose(rows, n, seed):
    rng=random.Random(seed); groups=[[],[],[],[],[]]
    for row in rows:
        title=(row['title'] or '').lower(); desc=(row['description_text'] or '').lower(); loc=(row['location'] or '').lower()
        if re.search(r"\b(?:sponsor(?:ship)?|citizenship|clearance|itar|visa)\b", desc): groups[3].append(row)
        elif not loc or loc in ('remote','hybrid') or 'locations' in loc or ',' not in loc: groups[4].append(row)
        elif re.search(r"\b(?:mechanical|electrical|chemical|civil|industrial|quality|clinical|sales|curriculum|machinist|trainer|business analyst|statistical|nurse|physician|technician)\b", title): groups[2].append(row)
        elif re.search(r"\b(?:software|engineer|developer)\b", title): groups[0].append(row)
        elif re.search(r"\b(?:data|ml|ai|devops|security|cloud|platform|sre|machine learning|firmware|mobile|embedded)\b", title): groups[1].append(row)
        else: groups[2].append(row)
    targets=[round(n*.4),round(n*.2),round(n*.2),round(n*.1),n-round(n*.9)]
    out=[]
    for group,target in zip(groups,targets): out.extend(rng.sample(group,min(target,len(group))))
    if len(out)<n:
        remaining=[r for r in rows if r not in out]; out.extend(rng.sample(remaining,min(n-len(out),len(remaining))))
    rng.shuffle(out); return out[:n]

def non_overwriting_path(path: Path, stamp: str | None = None) -> Path:
    if not path.exists(): return path
    stamp = stamp or datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    candidate=path.with_name(f'label_sample_{stamp}.csv'); suffix=1
    while candidate.exists():
        candidate=path.with_name(f'label_sample_{stamp}_{suffix}.csv'); suffix+=1
    return candidate

def main():
    p=argparse.ArgumentParser(); p.add_argument('--sample-size',type=int,default=300); p.add_argument('--seed',type=int,default=42); p.add_argument('--output',default='data/label_sample.csv'); args=p.parse_args()
    path=Path(args.output); guide=path.with_name('label_sample_guide.md'); path.parent.mkdir(parents=True,exist_ok=True)
    path=non_overwriting_path(path)
    db=SessionLocal()
    try:
        rows=db.execute(text("SELECT id AS job_id, source, company, title, location, description_text FROM jobs WHERE expired_at IS NULL ORDER BY md5(id::text || :seed) LIMIT 10000"), {"seed": str(args.seed)}).mappings().all()
    finally: db.close()
    selected=choose(rows,args.sample_size,args.seed)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
        for r in selected:
            w.writerow({**{k:r.get(k) or '' for k in FIELDS[:5]},'description_head':' '.join((r.get('description_text') or '')[:400].split()),**{k:'' for k in FIELDS[6:]}})
    guide.write_text(GUIDE,encoding='utf-8'); print(f'wrote {path} ({len(selected)} rows)'); print(f'guide {guide}')
if __name__=='__main__': main()
