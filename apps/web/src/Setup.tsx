import { useEffect, useMemo, useRef, useState } from 'react'
import Kit from './lib/kit.js'
import { request } from './lib/api'
import RoleControl from './components/RoleDrawer'

export type EducationSystemId = 'united_states_high_school' | 'england_wales_secondary'
export type SchoolClass = { id: string; name: string; subject: string; timezone: string; education_system: EducationSystemId | null; level_label: string | null }
export type EducationSystem = { id: EducationSystemId; label: string; class_label: string; period_label: string; level_label: string; levels: string[]; timezones: string[] }
export type Onboarding = { completed: boolean; teacher_display_name: string; introduction: string; selected_class_id: string | null; classes: SchoolClass[]; education_systems: EducationSystem[] }

export default function Setup({ profile, onDone, onCancel }: { profile: Onboarding; onDone: (profile: Onboarding) => void; onCancel?: () => void }) {
  const initialClass = profile.classes.find(c => c.id === profile.selected_class_id) ?? profile.classes[0]
  const [teacherName, setTeacherName] = useState(profile.teacher_display_name)
  const [intro, setIntro] = useState(profile.introduction)
  const [classId, setClassId] = useState(initialClass?.id ?? '')
  const [system, setSystem] = useState<EducationSystemId>(initialClass?.education_system ?? 'united_states_high_school')
  const selectedSystem = useMemo(() => profile.education_systems.find(s => s.id === system)!, [profile, system])
  const [level, setLevel] = useState(initialClass?.level_label ?? selectedSystem.levels[0])
  const [timezone, setTimezone] = useState(initialClass?.timezone ?? selectedSystem.timezones[0])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const themeSlot = useRef<HTMLSpanElement>(null)
  useEffect(() => { Kit.themeToggle(() => {}, themeSlot.current); Kit.reveal() }, [])
  function chooseSystem(id: EducationSystemId) { const next = profile.education_systems.find(s => s.id === id)!; setSystem(id); setLevel(next.levels[0]); setTimezone(next.timezones[0]) }
  async function submit() {
    setError('')
    if (!teacherName.trim() || intro.trim().length < 10 || !classId) { setError('Add your name, class, and a learner introduction of at least 10 characters.'); return }
    setBusy(true)
    try {
      onDone(await request<Onboarding>('/teacher/onboarding', { method: 'PUT', body: JSON.stringify({ display_name: teacherName.trim(), introduction: intro.trim(), class_id: classId, education_system: system, level_label: level, timezone }) }))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'School setup could not be saved.') }
    finally { setBusy(false) }
  }
  return <div className="setup-wrap">
    <header className="setup-bar"><div className="brand"><b>CLASS CATCH-UP</b><span>SYNTHETIC DEMO</span></div><div className="spacer"/><span ref={themeSlot}/><RoleControl role="teacher"/></header>
    <main className="setup">
      <section className="setup-intro" data-reveal><p className="eyebrow">Welcome, teacher</p><h1 className="display">Make catch-up feel like it belongs in your school.</h1><p className="lede">Tell us about your class once. Upload missed material, approve the evidence, and review every packet before it reaches a learner.</p><ul className="setup-points"><li><b>Grounded</b><span>Every step cites a source you approved.</span></li><li><b>Reviewed</b><span>Packets stay drafts until you publish them.</span></li><li><b>Honest</b><span>Missing evidence becomes an exception.</span></li></ul></section>
      <section className="setup-form panel" data-reveal><div className="panel-head"><h2>School setup</h2><span className="spacer"/><span className="code">STEP 1 OF 1</span></div><div className="panel-body form">
        <div className="field"><label htmlFor="f-name">Your display name</label><input id="f-name" value={teacherName} onChange={e=>setTeacherName(e.target.value)}/></div>
        <div className="field"><label htmlFor="f-intro">Learner-facing introduction</label><textarea id="f-intro" value={intro} onChange={e=>setIntro(e.target.value)}/></div>
        <div className="field"><label htmlFor="f-class">Class</label><select id="f-class" value={classId} onChange={e=>setClassId(e.target.value)}>{profile.classes.map(c=><option key={c.id} value={c.id}>{c.name} · {c.subject}</option>)}</select></div>
        <div className="field"><label>School system</label><div className="sys-cards" role="radiogroup">{profile.education_systems.map(s=><button type="button" role="radio" aria-checked={system===s.id} className={'sys-card'+(system===s.id?' on':'')} key={s.id} onClick={()=>chooseSystem(s.id)}><b>{s.label}</b><small>{s.id==='united_states_high_school'?'Grades 9–12 · class periods':'Years 7–13 · lessons and sixth form'}</small></button>)}</div></div>
        <div className="field-row"><div className="field"><label htmlFor="f-grade">{selectedSystem.level_label}</label><select id="f-grade" value={level} onChange={e=>setLevel(e.target.value)}>{selectedSystem.levels.map(v=><option key={v}>{v}</option>)}</select></div><div className="field"><label htmlFor="f-tz">School timezone</label><select id="f-tz" value={timezone} onChange={e=>setTimezone(e.target.value)}>{selectedSystem.timezones.map(v=><option key={v}>{v}</option>)}</select></div></div>
        <div className="preview"><p className="eyebrow">Experience preview</p><div className="preview-card"><b>{teacherName || 'Your name'}</b><span>{profile.classes.find(c=>c.id===classId)?.name} · {level} · {timezone}</span><p>{intro || 'Your introduction appears here.'}</p></div></div>
        {error&&<div className="form-errors" role="alert"><p>{error}</p></div>}<div className="action-row">{onCancel&&<button type="button" className="btn" onClick={onCancel}>Cancel</button>}<button type="button" className="btn primary big" disabled={busy} onClick={submit}>{busy?'Saving…':'Enter my class'}</button></div>
      </div></section>
    </main>
  </div>
}
