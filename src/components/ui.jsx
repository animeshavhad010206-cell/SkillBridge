import { TriangleAlert } from 'lucide-react'

const STATUS = {
  verified: { label: 'Verified', className: 'chip chip-solid' },
  partial: { label: 'Partial', className: 'chip' },
  unverified: { label: 'Unverified', className: 'chip chip-dashed' },
}

export function StatusChip({ status }) {
  const { label, className } = STATUS[status]
  return <span className={className}>{label}</span>
}

export function ErrorBox({ children }) {
  if (!children) return null
  return (
    <p role="alert" className="flex items-start gap-2 border-[3px] border-black p-3 font-bold">
      <TriangleAlert aria-hidden size={20} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  )
}

export function Field({ label, children }) {
  return (
    <label className="block">
      <span className="eyebrow mb-1.5 block">{label}</span>
      {children}
    </label>
  )
}

export function Stat({ label, value, note, inverse }) {
  return (
    <div className={inverse ? 'card-inverse' : 'card'}>
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-5xl leading-none font-bold">{value ?? '-'}</p>
      {note && <p className="mt-2 text-sm">{note}</p>}
    </div>
  )
}

export function TrustBar({ score }) {
  return (
    <div className="flex items-center gap-2">
      <div
        role="meter"
        aria-label="Trust score"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-3.5 w-10 border-2 border-black bg-white sm:w-24"
      >
        <div className="h-full bg-black" style={{ width: `${score}%` }} />
      </div>
      <span className="font-mono text-sm tabular-nums">{score}</span>
    </div>
  )
}

export function ExternalLink({ href, children, className = 'link' }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
    </a>
  )
}
