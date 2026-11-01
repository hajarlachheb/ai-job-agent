import os, re, json, sqlite3, hashlib, datetime as dt
from pathlib import Path
import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from phase2 import load_profile, assess, eligibility_gate, make_pdf

BASE=Path(__file__).parent
DB=os.getenv('DB_PATH',str(BASE/'jobs.sqlite3'))
CONFIG=json.loads((BASE/'config.json').read_text())
app=FastAPI(title='Job Application Agent')

def conn():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, source TEXT, company TEXT, title TEXT, location TEXT, url TEXT, description TEXT, score INTEGER, status TEXT, reason TEXT, discovered_at TEXT, updated_at TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, event TEXT, detail TEXT, at TEXT)')
 c.commit();return c

def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def log(c,jid,event,detail=''):
 c.execute('INSERT INTO events(job_id,event,detail,at) VALUES (?,?,?,?)',(jid,event,detail,now()))
def key(source,company,external_id):return hashlib.sha256(f'{source}|{company.lower()}|{external_id}'.encode()).hexdigest()[:24]
def clean(html):return re.sub(r'<[^>]+>',' ',html or '').replace('&nbsp;',' ')

def fetch_jobs():
 out=[]; errors=[]
 for board in CONFIG['sources']['greenhouse']:
  try:
   response=requests.get(f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs',params={'content':'true'},timeout=20)
   response.raise_for_status()
   for j in response.json().get('jobs',[]):
    out.append(dict(id=key('greenhouse',board,str(j['id'])),source='greenhouse',company=board,title=j['title'],location=j.get('location',{}).get('name',''),url=j['absolute_url'],description=clean(j.get('content',''))))
  except Exception as e:errors.append(f'greenhouse:{board}: {e}')
 for site in CONFIG['sources']['lever']:
  try:
   response=requests.get(f'https://api.lever.co/v0/postings/{site}',params={'mode':'json'},timeout=20)
   response.raise_for_status()
   for j in response.json():
    out.append(dict(id=key('lever',site,j['id']),source='lever',company=site,title=j['text'],location=j.get('categories',{}).get('location',''),url=j['hostedUrl'],description=clean(j.get('descriptionPlain','') or j.get('description',''))))
  except Exception as e:errors.append(f'lever:{site}: {e}')
 return out,errors

def score_job(j):
 text=(j['title']+' '+j['description']).lower(); title=j['title'].lower()
 if not any(t.lower() in title for t in CONFIG['target_titles']):return 0,'Title outside target roles'
 score=45+min(35,sum(5 for s in CONFIG['skills'] if s.lower() in text))
 score+=20 if any(x.lower() in j['location'].lower() for x in CONFIG['locations']) else 0
 if any(x in title for x in ['intern','graduate','sales','recruiter']):return 0,'Excluded role'
 if any(x in text for x in CONFIG['exclusion_phrases']):return 0,'Excluded by configured requirements'
 return min(score,100),'Heuristic score; work authorization and sponsorship must be verified separately'

def run_discovery():
 jobs,errors=fetch_jobs(); c=conn(); new=0
 for j in jobs:
  score,reason=score_job(j)
  cur=c.execute('INSERT OR IGNORE INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(j['id'],j['source'],j['company'],j['title'],j['location'],j['url'],j['description'],score,'discovered',reason,now(),now()))
  if cur.rowcount:new+=1;log(c,j['id'],'discovered',reason)
 c.commit();c.close();return {'found':len(jobs),'new':new,'errors':errors}

def auth(x_agent_key):
 if not os.getenv('AGENT_API_KEY') or x_agent_key!=os.getenv('AGENT_API_KEY'):raise HTTPException(401,'Invalid API key')

@app.post('/discover')
def discover(x_agent_key:str|None=Header(None)):
 auth(x_agent_key);return run_discovery()

@app.get('/jobs')
def jobs(status:str|None=None,limit:int=100,x_agent_key:str|None=Header(None)):
 auth(x_agent_key);c=conn()
 rows=c.execute('SELECT id,source,company,title,location,url,score,status,reason FROM jobs WHERE (? IS NULL OR status=?) ORDER BY score DESC LIMIT ?', (status,status,min(limit,500))).fetchall()
 c.close();return [dict(r) for r in rows]

class Decision(BaseModel):
 status:str
 note:str=''

@app.post('/jobs/{job_id}/decision')
def decision(job_id:str,body:Decision,x_agent_key:str|None=Header(None)):
 auth(x_agent_key)
 if body.status not in ('review','rejected','approved','submitted','interview','offer','closed'):raise HTTPException(400,'Invalid status')
 if body.status=='submitted':raise HTTPException(400,'Submission must be verified by an application adapter')
 c=conn();row=c.execute('SELECT id FROM jobs WHERE id=?',(job_id,)).fetchone()
 if not row:raise HTTPException(404,'Unknown job')
 c.execute('UPDATE jobs SET status=?,reason=?,updated_at=? WHERE id=?',(body.status,body.note,now(),job_id));log(c,job_id,body.status,body.note)
 c.commit();c.close();return {'ok':True}

@app.post('/prepare/{job_id}')
def prepare(job_id:str,x_agent_key:str|None=Header(None)):
 auth(x_agent_key);c=conn();j=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
 if not j:raise HTTPException(404,'Unknown job')
 profile=json.loads((BASE/'profile.json').read_text())
 out=BASE/'drafts';out.mkdir(exist_ok=True)
 relevant=[s for s in profile['skills'] if s.lower() in (j['description'] or '').lower()]
 draft=f"# {profile['name']}\n\nEmail: {profile['email']}\n\n## Verified profile\n{profile['summary']}\n\n## Relevant skills\n{', '.join(relevant)}\n\n## Target role\n{j['title']} at {j['company']}\n\n## Review checklist\n- Confirm all claims and dates\n- Confirm sponsorship and location eligibility\n- Convert to ATS-friendly PDF before submission\n"
 p=out/f'{job_id}.md';p.write_text(draft)
 c.execute('UPDATE jobs SET status=?,updated_at=? WHERE id=?',('review',now(),job_id));log(c,job_id,'prepared',str(p));c.commit();c.close()
 return {'draft':str(p),'status':'review','note':'Template only; no CV or application was submitted'}

@app.get('/stats')
def stats(x_agent_key:str|None=Header(None)):
 auth(x_agent_key);c=conn();rows=c.execute('SELECT status,COUNT(*) AS count FROM jobs GROUP BY status').fetchall();c.close();return {r['status']:r['count'] for r in rows}

@app.get('/health')
def health():return {'status':'ok'}

@app.post('/evaluate/{job_id}')
def evaluate(job_id:str,x_agent_key:str|None=Header(None)):
 auth(x_agent_key)
 c=conn();row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
 if not row:c.close();raise HTTPException(404,'Unknown job')
 try:
  profile=load_profile();assessment=assess(dict(row),profile,CONFIG)
  status,reason=eligibility_gate(dict(row),assessment,CONFIG)
  output=BASE/'drafts'/f'{job_id}.pdf'
  make_pdf(dict(row),profile,assessment,output)
  c.execute('UPDATE jobs SET score=?,status=?,reason=?,updated_at=? WHERE id=?',(assessment['score'],status,reason,now(),job_id))
  log(c,job_id,'llm_evaluation',json.dumps({'assessment':assessment,'pdf':str(output),'gate':reason}))
  c.commit()
  return {'job_id':job_id,'status':status,'reason':reason,'assessment':assessment,'pdf_path':str(output),'submitted':False}
 except (ValueError,RuntimeError) as e:raise HTTPException(422,str(e))
 except requests.RequestException as e:raise HTTPException(502,'LLM service unavailable: '+str(e))
 finally:c.close()
