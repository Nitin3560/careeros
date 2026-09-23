import csv
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.export_label_sample import FIELDS, choose, non_overwriting_path
from scripts.score_classifier import binary_stats, score_rows

def test_label_csv_round_trip(tmp_path):
    path=tmp_path/'labels.csv'; rows=[{'job_id':'1','source':'x','company':'Acme','title':'Software Engineer','location':'Boston','description_head':'hello'}]
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerow({**rows[0],**{k:'' for k in FIELDS[6:]}})
    loaded=list(csv.DictReader(path.open())); assert loaded[0]['job_id']=='1' and loaded[0]['label_is_tech']==''

def test_stratified_sample_is_seeded_and_balanced_across_five_groups():
    rows=[]
    for group,prefix,title,location,description,count in [
        ('software','sw','Software Engineer','Austin, TX','',12),
        ('othertech','dt','Data Scientist','Dallas, TX','',8),
        ('nontech','nt','Mechanical Engineer','Boston, MA','',8),
        ('sponsor','sp','Software Engineer','Seattle, WA','Visa sponsorship information',4),
        ('unusual','un','Software Engineer','Remote','',4),
    ]:
        rows.extend({'job_id':f'{prefix}{i}','title':title,'location':location,'description_text':description} for i in range(count))
    first=choose(rows,10,123); second=choose(rows,10,123)
    assert [r['job_id'] for r in first]==[r['job_id'] for r in second]
    prefixes=[r['job_id'][:2] for r in first]
    assert {key:prefixes.count(key) for key in ('sw','dt','nt','sp','un')}=={'sw':4,'dt':2,'nt':2,'sp':1,'un':1}

def test_export_path_never_overwrites_existing_sample(tmp_path):
    original=tmp_path/'label_sample.csv'; original.write_text('labeled data')
    timestamped=tmp_path/'label_sample_20260923_120000.csv'; timestamped.write_text('prior export')
    candidate=non_overwriting_path(original,'20260923_120000')
    assert candidate.name=='label_sample_20260923_120000_1.csv'
    assert original.read_text()=='labeled data' and timestamped.read_text()=='prior export'

def test_scoring_math_and_disagreements():
    rows=[{'job_id':str(i),'title':'t','location':'Boston','label_is_tech':x} for i,x in enumerate(['y','y','n','n'])]
    preds=[{'is_tech':True},{'is_tech':False},{'is_tech':True},{'is_tech':False}]
    report, disagreements=score_rows(rows,preds); assert report['is_tech']['precision']==.5 and report['is_tech']['recall']==.5; assert len(disagreements['is_tech'])==2

def test_ten_row_binary_score_has_complete_confusion_counts():
    labels=['y','y','y','y','n','n','n','n','n','n']
    predictions=['y','y','n','y','y','n','n','n','n','n']
    result=binary_stats(list(zip(labels,predictions)))
    assert result == {'precision':.75,'recall':.75,'f1':.75,'support':4,'confusion':{'tp':3,'fp':1,'tn':5,'fn':1}}

def test_location_scoring_reports_per_class_precision_recall_f1_and_matrix():
    rows=[{'job_id':str(i),'title':'t','location':'x','label_location_class':label} for i,label in enumerate(['us','us','non_us','unknown'])]
    predictions=[{'location_class':value} for value in ['us','non_us','non_us','unknown']]
    report,_=score_rows(rows,predictions)
    loc=report['location_class']
    assert loc['confusion_matrix']['us']=={'us':1,'non_us':1,'unknown':0}
    assert loc['per_class']['us']=={'precision':1.0,'recall':.5,'f1':2/3,'support':2}
    assert loc['per_class']['non_us']['precision']==.5
