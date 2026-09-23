#!/usr/bin/env python3
import argparse,csv,datetime,json,sys
from pathlib import Path
from collections import Counter
from sqlalchemy import text
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'apps/api'))
from app.database import SessionLocal
from app.classification import classify_job

def binary_stats(pairs):
    tp=sum(a==b=='y' for a,b in pairs); fp=sum(a=='y' and b!='y' for a,b in pairs); fn=sum(a!='y' and b=='y' for a,b in pairs); support=tp+fn
    precision=tp/(tp+fp) if tp+fp else 0; recall=tp/support if support else 0; f1=2*precision*recall/(precision+recall) if precision+recall else 0
    return {'precision':precision,'recall':recall,'f1':f1,'support':support,'confusion':{'tp':tp,'fp':fp,'fn':fn}}
def score_rows(rows, predictions):
    report={}; disagreements={}
    for field in ('is_tech','is_senior','location_class','sponsorship_block','min_years'):
        label='label_'+field; pairs=[]; disagreements[field]=[]
        for row,pred in zip(rows,predictions):
            if not row.get(label): continue
            expected=row[label]; got=pred[field]
            if field in ('is_tech','is_senior','sponsorship_block'): expected={'y':'y','n':'n'}[expected]; got='y' if got else 'n'; stat=binary_stats([(expected,got)]); pairs.append((expected,got))
            else: pairs.append((expected,got))
            if expected!=got: disagreements[field].append({'job_id':row['job_id'],'title':row['title'],'location':row['location'],'expected':expected,'got':got,'evidence':pred.get('sponsorship_evidence') or pred.get('location_reason','')})
        if field=='location_class':
            labels=['us','non_us','unknown']; matrix={x:{y:0 for y in labels} for x in labels}
            for a,b in pairs:
                if a in matrix and b in matrix[a]: matrix[a][b]+=1
            report[field]={'support':len(pairs),'confusion_matrix':matrix}
        elif field=='min_years': report[field]={'support':len(pairs),'exact_accuracy':sum(a==b for a,b in pairs)/len(pairs) if pairs else 0}
        else: report[field]=binary_stats(pairs)
    return report,disagreements
def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',default='data/label_sample.csv'); args=p.parse_args(); rows=list(csv.DictReader(open(args.input,encoding='utf-8'))); db=SessionLocal(); predictions=[]
    try:
        for row in rows:
            desc=db.execute(text('SELECT description_text FROM jobs WHERE id=:id'),{'id':row['job_id']}).scalar() or row['description_head']; c=classify_job(row['title'],desc,row['location']); predictions.append({'is_tech':c['is_tech_title'],'is_senior':c['is_senior_title'],'location_class':c['location_class'],'sponsorship_block':c['sponsorship_block'],'min_years':str(c['min_years_required'] or ''),'sponsorship_evidence':c['sponsorship_evidence'],'location_reason':c['location_reason']})
    finally: db.close()
    report,disagreements=score_rows(rows,predictions); skipped={f:sum(not r.get('label_'+f) for r in rows) for f in ('is_tech','is_senior','location_class','sponsorship_block','min_years')}; payload={'report':report,'skipped':skipped,'disagreements':disagreements}; out=Path('reports')/f'classifier_score_{datetime.datetime.now():%Y%m%d_%H%M%S}.json'; out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    for f in report: print(f,report[f]); print('skipped',skipped[f]); [print(f"[{f}] {d['job_id']} | {d['title']} | {d['location']} | expected={d['expected']} got={d['got']} | {d['evidence']}") for d in disagreements[f]]
    print('wrote',out)
if __name__=='__main__': main()
