import { useEffect, useState } from 'react'

/* The persistent role entry point: a small circular T / S button that opens a
   right-side drawer over a dimmed scrim. Both entries (teacher / student)
   mount it, and switching roles is a plain navigation between the two pages —
   teacher always lands on school setup first, student on assignments. */
export default function RoleControl({ role }: { role: 'teacher' | 'student' }) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [open])

  const letter = role === 'teacher' ? 'T' : 'S'

  return (
    <>
      <button
        type="button"
        className="role-btn"
        aria-expanded={open}
        aria-controls="role-drawer"
        aria-label={`Choose your view — currently ${role}`}
        onClick={() => setOpen(o => !o)}
      >
        <b>{letter}</b><span className="role-mark" aria-hidden="true" />
      </button>

      <div
        className={'scrim' + (open ? ' on' : '')}
        onClick={() => setOpen(false)}
        aria-hidden="true"
      />
      <aside
        id="role-drawer"
        className={'drawer' + (open ? ' on' : '')}
        role="dialog"
        aria-modal="true"
        aria-label="Choose your view"
      >
        <div className="drawer-head">
          <div>
            <p className="eyebrow">Choose your view</p>
            <h2 className="drawer-title">Who is using this device?</h2>
          </div>
          <button type="button" className="btn drawer-close" aria-label="Close" onClick={() => setOpen(false)}>✕</button>
        </div>

        <a className="role-opt" href="./index.html" onClick={() => setOpen(false)}>
          <span className="role-badge">T</span>
          <span>
            <b>Teacher</b>
            <small>School setup, source materials, packet review and learner follow-up.</small>
          </span>
        </a>
        <a className="role-opt" href="./students.html" onClick={() => setOpen(false)}>
          <span className="role-badge alt">S</span>
          <span>
            <b>Student</b>
            <small>Catch-up assignments, guided practice and help requests.</small>
          </span>
        </a>

        <p className="drawer-note">Demo data is synthetic — no real learner information is used.</p>
      </aside>
    </>
  )
}
