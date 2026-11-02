import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { formatDate } from '../api'
import { RankedBars, VerificationBar } from './charts'
import { ExternalLink, Stat, StatusChip, TrustBar } from './ui'

const FILTERS = ['all', 'verified', 'partial', 'unverified']

function evidenceSummary(skill) {
  const parts = []
  if (skill.on_resume) parts.push(skill.in_context ? 'Resume, used in project or job' : 'Resume, listed only')
  if (skill.repo_count) parts.push(`${skill.repo_count} GitHub repo${skill.repo_count === 1 ? '' : 's'}`)
  return parts.join(' + ')
}

function SkillRow({ skill }) {
  const [open, setOpen] = useState(false)
  const hasEvidence = skill.evidence.length > 0
  return (
    <>
      <tr>
        <td>
          <span className="font-bold">{skill.name}</span>
          <span className="block font-mono text-xs">{skill.category}</span>
        </td>
        <td>
          <TrustBar score={skill.trust_score} />
        </td>
        <td>
          <StatusChip status={skill.status} />
        </td>
        <td className="min-w-56">
          {hasEvidence ? (
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setOpen(!open)}
              className="flex cursor-pointer items-center gap-1 text-left underline decoration-2 underline-offset-2"
            >
              {evidenceSummary(skill)}
              <ChevronDown aria-hidden size={16} className={open ? 'rotate-180' : ''} />
            </button>
          ) : (
            evidenceSummary(skill)
          )}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={4}>
            <ul className="space-y-1">
              {skill.evidence.map((item) => (
                <li key={item.repo} className="flex flex-wrap items-center gap-2 text-sm">
                  {item.url ? <ExternalLink href={item.url}>{item.repo}</ExternalLink> : <b>{item.repo}</b>}
                  <span className="chip">{item.signal}</span>
                  {item.pushed_at && <span className="font-mono text-xs">pushed {formatDate(item.pushed_at)}</span>}
                </li>
              ))}
            </ul>
          </td>
        </tr>
      )}
    </>
  )
}

function SkillProfile({ skills, counts }) {
  const [filter, setFilter] = useState('all')
  const visible = filter === 'all' ? skills : skills.filter((skill) => skill.status === filter)
  return (
    <section className="card" aria-labelledby="skills-title">
      <h2 id="skills-title" className="section-title">
        Trust-weighted skill profile
      </h2>
      <p className="mt-1 mb-4">
        A skill listed on a resume starts low. Real use in projects and public GitHub activity raise it.
      </p>
      <VerificationBar counts={counts} />
      <div className="mt-5 mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter skills by status">
        {FILTERS.map((name) => (
          <button
            key={name}
            type="button"
            aria-pressed={filter === name}
            onClick={() => setFilter(name)}
            className={`btn btn-small ${filter === name ? '' : 'btn-secondary'}`}
          >
            {name}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto border-[3px] border-black">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Skill</th>
              <th scope="col">Trust</th>
              <th scope="col">Status</th>
              <th scope="col">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((skill) => (
              <SkillRow key={skill.name} skill={skill} />
            ))}
            {!visible.length && (
              <tr>
                <td colSpan={4}>No skills with this status.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function SourceNote({ market }) {
  if (market.source === 'sample') {
    return (
      <p className="mt-1 mb-4">
        <span className="chip chip-solid mr-2">Sample data</span>
        The live job feed is unavailable, so these numbers come from built-in sample postings.
      </p>
    )
  }
  return (
    <p className="mt-1 mb-4">
      From {market.total_jobs} live postings on <ExternalLink href={market.source_url}>Himalayas</ExternalLink>, updated{' '}
      {formatDate(market.fetched_at)}.
    </p>
  )
}

function MarketDemand({ role, market }) {
  return (
    <section className="card" aria-labelledby="market-title">
      <h2 id="market-title" className="section-title">
        What the market wants
      </h2>
      <p className="eyebrow mt-1">{role}</p>
      <SourceNote market={market} />
      {market.skills.length ? (
        <RankedBars
          data={market.skills.slice(0, 15)}
          nameKey="name"
          valueKey="share"
          format={(value, row) => `${value}% of postings (${row.count})`}
          columns={['Skill', 'Share of postings', 'Postings']}
          tableRows={market.skills.slice(0, 15).map((row) => [row.name, `${row.share}%`, row.count])}
        />
      ) : (
        <p>Not enough postings to measure demand for this role yet.</p>
      )}
    </section>
  )
}

function GapList({ items, empty, describe }) {
  if (!items.length) return <p className="mt-3">{empty}</p>
  return (
    <ul className="mt-3 space-y-4">
      {items.map((item) => (
        <li key={item.name} className="border-t-[3px] border-black pt-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h4 className="text-lg font-bold">{item.name}</h4>
            <span className="font-mono text-sm">{describe(item)}</span>
          </div>
          <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {item.resources.map((resource) => (
              <li key={resource.url}>
                <ExternalLink href={resource.url}>{resource.title}</ExternalLink>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  )
}

function SkillGaps({ gaps }) {
  return (
    <section aria-labelledby="gaps-title">
      <h2 id="gaps-title" className="section-title mb-4">
        Close the gaps
      </h2>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h3 className="text-xl font-bold uppercase">Missing skills</h3>
          <p>Employers ask for these and they are not on the profile.</p>
          <GapList
            items={gaps.missing}
            empty="None of the most requested skills are missing."
            describe={(item) => `in ${item.share}% of jobs`}
          />
        </div>
        <div className="card">
          <h3 className="text-xl font-bold uppercase">Prove these</h3>
          <p>Claimed, but not verified. A public project using the skill raises its trust score.</p>
          <GapList
            items={gaps.weak}
            empty="Every requested skill on the profile is verified."
            describe={(item) => `trust ${item.trust_score} / in ${item.share}% of jobs`}
          />
        </div>
      </div>
    </section>
  )
}

function SkillChips({ label, skills, className }) {
  if (!skills.length) return null
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="eyebrow w-20">{label}</span>
      {skills.map((skill) => (
        <span key={skill} className={className}>
          {skill}
        </span>
      ))}
    </div>
  )
}

function JobCard({ job }) {
  return (
    <li className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg leading-snug font-bold">{job.title}</h3>
          <p>
            {job.company}
            {job.location && ` / ${job.location}`}
          </p>
          {job.seniority && <span className="chip mt-1">{job.seniority}</span>}
        </div>
        <div className="border-[3px] border-black bg-black px-3 py-2 text-center text-white">
          <p className="text-3xl leading-none font-bold">{job.match_score}%</p>
          <p className="eyebrow mt-1">Match</p>
        </div>
      </div>
      <SkillChips label="Proven" skills={job.matched} className="chip chip-solid" />
      <SkillChips label="Unproven" skills={job.unproven} className="chip chip-dashed" />
      <SkillChips label="Missing" skills={job.missing} className="chip" />
      {job.source === 'sample' ? (
        <p className="mt-3">
          <span className="chip chip-solid">Sample posting</span>
        </p>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-4">
          {job.apply_url && (
            <ExternalLink href={job.apply_url} className="btn btn-small">
              Apply
            </ExternalLink>
          )}
          <span className="text-sm">
            Source:{' '}
            <ExternalLink href={job.source_url}>Himalayas</ExternalLink>
          </span>
        </div>
      )}
    </li>
  )
}

export default function StudentReport({ report }) {
  const { skills, status_counts: counts, scores, market, gaps, jobs, target_role: role } = report
  const unproven = scores ? scores.coverage - scores.readiness : 0

  return (
    <div className="space-y-8">
      {scores && (
        <section aria-label="Scores" className="grid gap-6 md:grid-cols-3">
          <Stat
            inverse
            label="Job-market readiness"
            value={`${scores.readiness}%`}
            note={`Backed by evidence, for ${role}.`}
          />
          <Stat label="Skills claimed" value={`${scores.coverage}%`} note="Of market demand, at face value." />
          <Stat label="Unproven gap" value={`${unproven} pts`} note="Claimed on paper, not yet shown in evidence." />
        </section>
      )}

      {skills.length > 0 && <SkillProfile skills={skills} counts={counts} />}
      {market && <MarketDemand role={role} market={market} />}
      {gaps && <SkillGaps gaps={gaps} />}

      {jobs.length > 0 && (
        <section aria-labelledby="jobs-title">
          <h2 id="jobs-title" className="section-title mb-4">
            Best job matches
          </h2>
          <ul className="grid gap-6 lg:grid-cols-2">
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
