import { ExternalLink } from './ui'

const CONTACT_FIELDS = [
  ['Email', 'email'],
  ['Phone', 'phone'],
  ['GitHub', 'github'],
  ['LinkedIn', 'linkedin'],
]

function contactLink(key, value) {
  if (key === 'github') return `https://github.com/${value}`
  if (key === 'linkedin') return value.startsWith('http') ? value : `https://${value}`
  return null
}

function Section({ title, items }) {
  if (!items.length) return null
  return (
    <div>
      <h3 className="eyebrow mb-2">{title}</h3>
      <ul className="space-y-1">
        {items.map((item, index) => (
          <li key={index} className="break-words">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function ParsedResume({ resume }) {
  const { contact, summary, education, experience, projects, certifications, filename, skills } = resume
  const found = CONTACT_FIELDS.filter(([, key]) => contact[key])

  return (
    <section className="card" aria-labelledby="parsed-title">
      <p className="eyebrow break-words">Parsed from {filename}</p>
      <h1 id="parsed-title" className="mt-1 text-4xl leading-none font-bold uppercase md:text-5xl">
        {contact.name ?? 'Name not found'}
      </h1>

      {found.length > 0 && (
        <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
          {found.map(([label, key]) => {
            const href = contactLink(key, contact[key])
            return (
              <div key={key} className="min-w-0">
                <dt className="eyebrow">{label}</dt>
                <dd className="break-words">
                  {href ? <ExternalLink href={href}>{contact[key]}</ExternalLink> : contact[key]}
                </dd>
              </div>
            )
          })}
        </dl>
      )}

      {summary && <p className="mt-4">{summary}</p>}

      <div className="mt-5 border-t-[3px] border-black pt-4">
        <h3 className="eyebrow mb-2">Skills found ({skills.length})</h3>
        {skills.length ? (
          <ul className="flex flex-wrap gap-1.5">
            {skills.map((skill) => (
              <li key={skill.name} className="chip">
                {skill.name}
              </li>
            ))}
          </ul>
        ) : (
          <p>No known skills were found in this resume.</p>
        )}
      </div>

      <div className="mt-5 grid gap-6 border-t-[3px] border-black pt-4 md:grid-cols-2">
        <Section title="Education" items={education} />
        <Section title="Experience" items={experience} />
        <Section title="Projects" items={projects} />
        <Section title="Certifications" items={certifications} />
      </div>
    </section>
  )
}
