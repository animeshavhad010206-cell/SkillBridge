import { FileUp, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import ParsedResume from './components/ParsedResume'
import StudentReport from './components/StudentReport'
import { ErrorBox, ExternalLink, Field } from './components/ui'

function DropZone({ onFile, busy, compact }) {
  const input = useRef(null)
  const [dragging, setDragging] = useState(false)

  return (
    <>
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          onFile(event.dataTransfer.files[0])
        }}
        className={`flex w-full cursor-pointer flex-col items-center justify-center gap-2 border-[3px] border-dashed text-center ${
          compact ? 'border-black p-4' : 'min-h-72 border-white p-8'
        } ${dragging ? (compact ? 'bg-black text-white' : 'bg-white text-black') : ''}`}
      >
        <FileUp aria-hidden size={compact ? 24 : 44} />
        <span className={compact ? 'font-bold' : 'text-2xl font-bold uppercase'}>
          {busy ? 'Reading resume...' : compact ? 'Parse another resume' : 'Drop your resume here'}
        </span>
        <span className="font-mono text-sm">PDF or DOCX, up to 5 MB</span>
      </button>
      <input
        ref={input}
        type="file"
        aria-label="Resume file"
        accept=".pdf,.docx"
        hidden
        onChange={(event) => {
          onFile(event.target.files[0])
          event.target.value = ''
        }}
      />
    </>
  )
}

function IdentityChip({ value, yes, no }) {
  if (value == null) return null
  return <span className={value ? 'chip' : 'chip chip-dashed'}>{value ? yes : no}</span>
}

function VerifyPanel({ report, update, busy }) {
  const [roles, setRoles] = useState([])
  const [edited, setEdited] = useState(null)
  const username = edited ?? report.github?.login ?? report.resume.contact.github ?? ''
  const github = report.github

  useEffect(() => {
    api('/roles').then(setRoles).catch(() => {})
  }, [])

  const verify = (event) => {
    event.preventDefault()
    update('github', { github_username: username.trim() })
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="card" aria-labelledby="github-title">
        <h2 id="github-title" className="text-lg font-bold uppercase">
          Verify skills on GitHub
        </h2>
        <p className="mb-3">Optional. Real repositories turn claims into proven skills.</p>
        <form onSubmit={verify} className="space-y-3">
          <Field label="GitHub username">
            <input className="input" maxLength={120} value={username} onChange={(e) => setEdited(e.target.value)} />
          </Field>
          <button className="btn btn-small w-full" disabled={busy === 'github' || !username.trim()}>
            {busy === 'github' ? 'Checking repositories...' : github ? 'Check again' : 'Verify skills'}
          </button>
        </form>
        {github && (
          <div className="mt-3 text-sm">
            <p>
              <ExternalLink href={github.html_url}>{github.login}</ExternalLink>, {github.public_repos} repos,{' '}
              {github.scanned_repos} scanned in depth
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <IdentityChip value={report.identity.resume_links_account} yes="On resume" no="Resume links another account" />
              <IdentityChip value={report.identity.name_matches} yes="Name matches" no="Name differs" />
            </div>
          </div>
        )}
      </section>
      <section className="card" aria-labelledby="role-title">
        <h2 id="role-title" className="text-lg font-bold uppercase">
          Compare with the job market
        </h2>
        <p className="mb-3">Optional. See readiness, skill gaps and matching live jobs.</p>
        <Field label="Target role">
          <select
            className="input"
            disabled={busy === 'role'}
            value={report.target_role ?? ''}
            onChange={(event) => update('role', { target_role: event.target.value || null })}
          >
            <option value="">Select a role</option>
            {roles.map((role) => (
              <option key={role}>{role}</option>
            ))}
          </select>
        </Field>
        {busy === 'role' && <p className="mt-3 text-sm font-bold">Reading live job postings...</p>}
      </section>
    </div>
  )
}

export default function App() {
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(null)

  const run = async (name, action) => {
    setBusy(name)
    setError('')
    try {
      setReport(await action())
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(null)
    }
  }

  const upload = (file) => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    if (report?.github) form.append('github_username', report.github.login)
    if (report?.target_role) form.append('target_role', report.target_role)
    run('resume', () => api('/resume', { method: 'POST', form }))
  }

  const update = (name, changes) =>
    run(name, () =>
      api('/report', {
        method: 'POST',
        body: {
          resume: report.resume,
          github_username: report.github?.login ?? null,
          target_role: report.target_role,
          ...changes,
        },
      }),
    )

  return (
    <div className="flex min-h-svh flex-col">
      <header className="bg-black text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <p className="border-[3px] border-white px-2 py-0.5 text-xl font-bold uppercase">SkillBridge</p>
          {report && (
            <button
              type="button"
              onClick={() => {
                setReport(null)
                setError('')
              }}
              className="flex cursor-pointer items-center gap-2 border-2 border-white px-3 py-1 font-bold uppercase hover:bg-white hover:text-black"
            >
              <RotateCcw aria-hidden size={16} /> Start over
            </button>
          )}
        </div>
      </header>

      {report ? (
        <main className="mx-auto w-full max-w-6xl flex-1 space-y-8 px-4 py-8">
          <ErrorBox>{error}</ErrorBox>
          <ParsedResume resume={report.resume} />
          <VerifyPanel key={report.resume.filename} report={report} update={update} busy={busy} />
          <StudentReport report={report} />
          <div className="card">
            <DropZone compact onFile={upload} busy={busy === 'resume'} />
          </div>
        </main>
      ) : (
        <main className="flex flex-1 items-center bg-black text-white">
          <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-4 py-10 lg:grid-cols-2">
            <div>
              <h1 className="text-5xl leading-none font-bold uppercase xl:text-7xl">
                Prove
                <br />
                what you
                <br />
                know.
              </h1>
              <p className="mt-6 max-w-md text-lg">
                Upload a resume to see its skills, check them against real GitHub work, and compare them with live job
                demand.
              </p>
            </div>
            <div className="space-y-4">
              <DropZone onFile={upload} busy={busy === 'resume'} />
              {error && (
                <div className="bg-white text-black">
                  <ErrorBox>{error}</ErrorBox>
                </div>
              )}
            </div>
          </div>
        </main>
      )}
    </div>
  )
}
