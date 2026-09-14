import { useCallback, useEffect, useRef, useState } from 'react'
import Kit from './lib/kit.js'
import { enterDemo, request, type Session } from './lib/api'
import RoleControl from './components/RoleDrawer'
import Setup, { type Onboarding } from './Setup'

type View = 'materials' | 'review' | 'exceptions' | 'setup'
type Planning = { topics: {id:string;title:string}[]; segments:{id:string;label:string;text:string}[]; mappings:{id:string;topic_id:string;suggested_segment_ids:string[];approved_segment_ids:string[];status:string;unmatched:boolean}[] }
type RosterStudent = { student_id:string; display_name:string }
type LessonOccurrence = { id:string; revision:number }
type LessonSessionResult = { job_id:string|null; job_state:string|null; blocked_reason:string|null }
type Packet = { id:string; revision_number:number; status:string; content_hash:string; generation_source:string; payload:{title:string;estimated_minutes?:number;objectives?:string[];steps?:{id:string;title:string;blocks:{text:string;citations:{segment_id:string;page_or_section:string}[]}[]}[];questions?:{id:string;prompt:string;options:Record<string,string>;answer_key?:string;rationale?:string}[]} }
type ExceptionItem = {id:string;student_id:string|null;reason:string;severity:string;open:boolean}

export default function App() {
  const [session,setSession]=useState<Session|null>(null), [profile,setProfile]=useState<Onboarding|null>(null)
  const [view,setView]=useState<View>('setup'), [error,setError]=useState('')
  const themeSlot=useRef<HTMLSpanElement>(null)
  useEffect(()=>{ void enterDemo('teacher').then(s=>{setSession(s);return request<Onboarding>('/teacher/onboarding')}).then(setProfile).catch(e=>setError(e.message)) },[])
  useEffect(()=>{if(profile&&view!=='setup'){if(themeSlot.current&&!themeSlot.current.childElementCount)Kit.themeToggle(()=>{},themeSlot.current);Kit.reveal()}},[profile,view])
  if(error) return <main className="page narrow"><section className="panel"><h2>Could not open Class Catch-Up</h2><p className="neg">{error}</p></section></main>
  if(!session||!profile) return <main className="page narrow"><p className="eyebrow">Opening teacher workspace…</p></main>
  if(view==='setup') return <Setup profile={profile} onDone={p=>{setProfile(p);setView('materials')}} onCancel={profile.completed?()=>setView('materials'):undefined}/>
  const classId=profile.selected_class_id??profile.classes[0]?.id??''
  const selected=profile.classes.find(c=>c.id===classId)
  return <><header className="topbar"><div className="brand"><b>CLASS CATCH-UP</b><span>TEACHER WORKSPACE</span></div><nav className="nav" aria-label="Teacher">{(['materials','review','exceptions','setup'] as View[]).map(v=><button key={v} type="button" className={view===v?'on':''} onClick={()=>setView(v)}>{v==='setup'?'School Setup':v[0].toUpperCase()+v.slice(1)}</button>)}</nav><div className="spacer"/><span className="hdr-meta"><b>{selected?.name}</b> · {selected?.level_label} · {profile.teacher_display_name}</span><span ref={themeSlot}/><RoleControl role="teacher"/></header>{view==='materials'&&<Materials classId={classId} onNext={()=>setView('review')}/>} {view==='review'&&<Review classId={classId} onNext={()=>setView('exceptions')}/>} {view==='exceptions'&&<Exceptions onNext={()=>{location.href='./students.html'}}/>}</>
}

function Materials({classId,onNext}:{classId:string;onNext:()=>void}){
  const [data,setData]=useState<Planning>({topics:[],segments:[],mappings:[]})
  const [roster,setRoster]=useState<RosterStudent[]>([])
  const [topics,setTopics]=useState(''),[file,setFile]=useState<File|null>(null),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false)
  const [lessonDate,setLessonDate]=useState(()=>new Date().toISOString().slice(0,10))
  const [periodKey,setPeriodKey]=useState('Lesson 1'),[absentStudent,setAbsentStudent]=useState('')
  const load=useCallback(async()=>{
    try{
      const [planning,students]=await Promise.all([
        request<Planning>(`/classes/${classId}/planning`),
        request<RosterStudent[]>(`/classes/${classId}/students`),
      ])
      setData(planning);setRoster(students);setAbsentStudent(current=>current||students[0]?.student_id||'')
    }catch(e){setNotice(e instanceof Error?e.message:'Could not load class data')}
  },[classId])
  // This effect synchronizes the selected class with server-owned planning and roster data.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(()=>{void load()},[load])
  async function upload(){if(!file)return;setBusy(true);const body=new FormData();body.append('upload',file);try{await request(`/classes/${classId}/materials`,{method:'POST',body});setNotice('Source uploaded and extracted.');setFile(null);await load()}catch(e){setNotice(e instanceof Error?e.message:'Upload failed')}finally{setBusy(false)}}
  async function saveTopics(){const values=topics.split('\n').map(title=>title.trim()).filter(Boolean);if(!values.length)return;setBusy(true);try{await request(`/classes/${classId}/topics`,{method:'POST',body:JSON.stringify({topics:values.map(title=>({title,objectives:[]}))})});setTopics('');setNotice('Topics saved to the backend.');await load()}catch(e){setNotice(e instanceof Error?e.message:'Could not save topics')}finally{setBusy(false)}}
  async function propose(){setBusy(true);try{await request(`/classes/${classId}/mapping-proposals`,{method:'POST'});setNotice('Evidence mappings proposed. Review and approve each topic.');await load()}catch(e){setNotice(e instanceof Error?e.message:'Could not propose mappings')}finally{setBusy(false)}}
  async function approve(m:Planning['mappings'][number]){const ids=m.suggested_segment_ids;try{await request(`/mapping-proposals/${m.id}/approve`,{method:'PATCH',body:JSON.stringify({segment_ids:ids})});await load()}catch(e){setNotice(e instanceof Error?e.message:'Could not approve mapping')}}
  const approved=data.mappings.filter(m=>m.status==='approved'&&m.approved_segment_ids.length)
  async function prepareCatchUp(){
    if(!approved.length||!absentStudent)return
    setBusy(true)
    try{
      const topicIds=approved.map(m=>m.topic_id)
      const segmentIds=[...new Set(approved.flatMap(m=>m.approved_segment_ids))]
      const lesson=await request<LessonOccurrence>(`/classes/${classId}/lesson-occurrences`,{method:'POST',body:JSON.stringify({local_date:lessonDate,period_key:periodKey,planned_topic_ids:topicIds})})
      const result=await request<LessonSessionResult>(`/lessons/${lesson.id}/session`,{method:'PUT',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({expected_revision:lesson.revision,coverage_status:'covered',actual_topic_ids:topicIds,segment_ids:segmentIds,moved_to_date:null,moved_to_period_key:null,attendance:roster.map(student=>({student_id:student.student_id,status:student.student_id===absentStudent?'absent':'present'}))})})
      if(result.job_state==='queued')setNotice('Live agent job queued. Keep the packet worker running, then open Review.')
      else setNotice(result.blocked_reason||'The catch-up job was not queued.')
    }catch(e){setNotice(e instanceof Error?e.message:'Could not prepare catch-up')}finally{setBusy(false)}
  }
  return <main className="page"><section className="flow" aria-label="Workflow"><Flow n="01" label="Sources" value={new Set(data.segments.map(s=>s.label.split(' · ')[0])).size}/><Flow n="02" label="Evidence" value={data.segments.length}/><Flow n="03" label="Topics" value={data.topics.length}/><Flow n="04" label="Approved" value={approved.length}/></section>{notice&&<p className="note">{notice}</p>}<div className="mat-grid"><section className="panel"><div className="panel-head"><h2>Sources</h2><span className="code">BACKEND EVIDENCE</span></div><div className="panel-body"><div className="src-list">{data.segments.map(s=><details className="src" key={s.id}><summary className="src-head"><span className="kind">SOURCE</span><span className="src-title">{s.label}</span></summary><pre className="src-text">{s.text}</pre></details>)}</div><div className="src-new"><p className="eyebrow">Upload a source</p><input type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={e=>setFile(e.target.files?.[0]??null)}/><button className="btn primary" disabled={!file||busy} onClick={upload}>Upload & extract</button></div></div></section><div className="mat-side"><section className="panel"><div className="panel-head"><h2>Topic sequence</h2><span className="code">ORDER MATTERS</span></div><div className="topic-list">{data.topics.map((t,i)=><div className="topic-row" key={t.id}><span className="ix num">{String(i+1).padStart(2,'0')}</span><span className="topic-title">{t.title}</span></div>)}</div><div className="src-new"><textarea value={topics} placeholder="One new topic per line" onChange={e=>setTopics(e.target.value)}/><button className="btn" disabled={busy} onClick={saveTopics}>Save topics</button><button className="btn primary" disabled={busy||!data.topics.length||!data.segments.length} onClick={propose}>Propose mappings</button></div></section><section className="panel"><div className="panel-head"><h2>Evidence mappings</h2></div><div className="panel-body">{data.mappings.map(m=><div className="xrow" key={m.id}><b>{data.topics.find(t=>t.id===m.topic_id)?.title}</b><p className="dim small">{m.suggested_segment_ids.length} suggested source section(s)</p><button className={'btn'+(m.status==='approved'?' primary':'')} onClick={()=>approve(m)}>{m.status==='approved'?'Approved ✓':'Approve suggested evidence'}</button></div>)}</div></section><section className="panel"><div className="panel-head"><h2>Prepare catch-up</h2><span className="code">START AGENT</span></div><div className="panel-body"><div className="field-row"><div className="field"><label htmlFor="lesson-date">Lesson date</label><input id="lesson-date" type="date" value={lessonDate} onChange={e=>setLessonDate(e.target.value)}/></div><div className="field"><label htmlFor="period-key">Lesson</label><input id="period-key" type="text" value={periodKey} onChange={e=>setPeriodKey(e.target.value)}/></div></div><div className="field"><label htmlFor="absent-student">Learner who was absent</label><select id="absent-student" value={absentStudent} onChange={e=>setAbsentStudent(e.target.value)}>{roster.map(student=><option key={student.student_id} value={student.student_id}>{student.display_name}</option>)}</select></div><p className="note">Uses every approved topic and source above. Other learners are recorded present.</p><button className="btn primary big" disabled={busy||!approved.length||!absentStudent||!periodKey.trim()} onClick={prepareCatchUp}>{busy?'Preparing…':'Prepare with Strands agent'}</button></div></section></div></div><PageNext step="01 complete" title="Sources and topics ready?" detail="Continue to inspect packet drafts and their source evidence." label="Next: Review" onClick={onNext}/></main>
}
function Flow({n,label,value}:{n:string;label:string;value:number}){return <div className="flow-step"><span className="ix">{n}</span><b className="num">{value}</b><span className="fl">{label}</span><span className="fd">live backend records</span></div>}

function Review({classId,onNext}:{classId:string;onNext:()=>void}){
  const [packets,setPackets]=useState<Packet[]>([]),[selected,setSelected]=useState<Packet|null>(null),[notice,setNotice]=useState('')
  const load=useCallback(()=>request<Packet[]>(`/teacher/packets?class_id=${classId}`).then(p=>{setPackets(p);setSelected(s=>p.find(x=>x.id===s?.id)??p[0]??null)}).catch(e=>setNotice(e.message)),[classId])
  useEffect(()=>{void load()},[load])
  async function publish(p:Packet){try{await request(`/teacher/packets/${p.id}/approve-and-publish`,{method:'POST',body:JSON.stringify({expected_revision_number:p.revision_number,expected_hash:p.content_hash})});setNotice('Published to enrolled absent learners.');await load()}catch(e){setNotice(e instanceof Error?e.message:'Could not publish')};}
  return <main className="page">{notice&&<p className="note">{notice}</p>}<div className="rev-grid"><section className="panel"><div className="panel-head"><h2>Packet queue</h2><span className="tail">{packets.length}</span></div><div className="pkt-list">{packets.map(p=><button className={'pkt-row'+(selected?.id===p.id?' on':'')} key={p.id} onClick={()=>setSelected(p)}><span className="pkt-title">{p.payload.title}</span><span className="pkt-sub">Revision {p.revision_number} · {p.status}</span></button>)}</div></section><section className="panel">{selected?<><div className="panel-head"><h2>{selected.payload.title}</h2><span className="tag">{selected.status}</span></div><div className="panel-body pkt-detail"><p className="code">{selected.generation_source==='strands_run'?'STRANDS RUN':'FIXTURE OR TEACHER EDIT'}</p>{selected.payload.steps?.map((s,i)=><div className="step-card" key={s.id}><div className="step-head"><span className="ix">{String(i+1).padStart(2,'0')}</span><b>{s.title}</b></div>{s.blocks.map((b,j)=><div key={j}><p>{b.text}</p><span className="cite">{b.citations.map(c=>c.page_or_section).join(', ')}</span></div>)}</div>)}{!['published','approved'].includes(selected.status)&&<button className="btn primary big" onClick={()=>publish(selected)}>Approve & publish</button>}</div></>:<div className="panel-body"><p className="dim">No packet drafts are available yet.</p></div>}</section></div><PageNext step="02 complete" title="Review finished?" detail="Continue to learner questions, evidence gaps, and preparation failures." label="Next: Exceptions" onClick={onNext}/></main>
}

function Exceptions({onNext}:{onNext:()=>void}){const [items,setItems]=useState<ExceptionItem[]>([]),[notice,setNotice]=useState('');const load=()=>request<ExceptionItem[]>('/teacher/exceptions').then(setItems).catch(e=>setNotice(e.message));useEffect(()=>{void load()},[]);async function resolve(id:string){try{await request(`/teacher/exceptions/${id}/resolve`,{method:'POST'});await load()}catch(e){setNotice(e instanceof Error?e.message:'Could not resolve')}}return <main className="page narrow"><section className="panel"><div className="panel-head"><h2>Exceptions</h2><span className="code">NEEDS ATTENTION</span></div><div className="panel-body">{notice&&<p className="note">{notice}</p>}{!items.length&&<p className="dim">No open exceptions.</p>}{items.map(x=><article className="exc" key={x.id}><div className="exc-head"><span className="tag t-warn">{x.severity}</span><b>{x.reason}</b></div><button className="btn" onClick={()=>resolve(x.id)}>Mark resolved</button></article>)}</div></section><PageNext step="03 complete" title="Teacher check complete" detail="Open the learner experience to confirm what students can see." label="Open student view" onClick={onNext}/></main>}

function PageNext({step,title,detail,label,onClick}:{step:string;title:string;detail:string;label:string;onClick:()=>void}){return <section className="page-next" aria-label="Continue workflow"><div><span className="code">{step}</span><h2>{title}</h2><p>{detail}</p></div><button type="button" className="btn primary big" onClick={onClick}>{label}<span aria-hidden="true">→</span></button></section>}
