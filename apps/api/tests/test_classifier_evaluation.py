import csv
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.export_label_sample import FIELDS, choose
from scripts.score_classifier import binary_stats, score_rows

def test_label_csv_round_trip(tmp_path):
    path=tmp_path/'labels.csv'; rows=[{'job_id':'1','source':'x','company':'Acme','title':'Software Engineer','location':'Boston','description_head':'hello'}]
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerow({**rows[0],**{k:'' for k in FIELDS[6:]}})
    loaded=list(csv.DictReader(path.open())); assert loaded[0]['job_id']=='1' and loaded[0]['label_is_tech']==''

def test_scoring_math_and_disagreements():
    rows=[{'job_id':str(i),'title':'t','location':'Boston','label_is_tech':x} for i,x in enumerate(['y','y','n','n'])]
    preds=[{'is_tech':True},{'is_tech':False},{'is_tech':True},{'is_tech':False}]
    report, disagreements=score_rows(rows,preds); assert report['is_tech']['precision']==.5 and report['is_tech']['recall']==.5; assert len(disagreements['is_tech'])==2
