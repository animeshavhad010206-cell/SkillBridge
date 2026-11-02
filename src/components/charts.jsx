import { useState } from 'react'
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

function ChartTooltip({ active, payload, label, format }) {
  if (!active || !payload?.length) return null
  return (
    <div className="border-[3px] border-black bg-white px-3 py-2 shadow-[4px_4px_0_#000]">
      <p className="font-bold">{label}</p>
      <p className="font-mono text-sm">{format(payload[0].value, payload[0].payload)}</p>
    </div>
  )
}

function TableToggle({ columns, rows }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-3">
      <button type="button" className="link text-sm" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? 'Hide table' : 'View as table'}
      </button>
      {open && (
        <div className="mt-2 overflow-x-auto border-[3px] border-black">
          <table className="table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row[0]}>
                  {row.map((cell, index) => (
                    <td key={index}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function RankedBars({ data, nameKey, valueKey, unit = '%', format, columns, tableRows }) {
  const height = data.length * 32 + 8
  const max = unit === '%' ? 100 : Math.max(...data.map((row) => row[valueKey]))
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart layout="vertical" data={data} margin={{ top: 0, right: 44, bottom: 0, left: 0 }} barCategoryGap={6}>
          <XAxis type="number" hide domain={[0, max]} />
          <YAxis
            type="category"
            dataKey={nameKey}
            width={132}
            tickLine={false}
            axisLine={{ stroke: '#000', strokeWidth: 3 }}
            tick={{ fill: '#000', fontSize: 13, fontWeight: 500 }}
            interval={0}
          />
          <Tooltip
            cursor={{ fill: '#000', fillOpacity: 0.08 }}
            content={<ChartTooltip format={format} />}
            isAnimationActive={false}
          />
          <Bar dataKey={valueKey} fill="#000" isAnimationActive={false}>
            <LabelList
              dataKey={valueKey}
              position="right"
              formatter={(value) => `${value}${unit}`}
              style={{ fill: '#000', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <TableToggle columns={columns} rows={tableRows} />
    </div>
  )
}

const SEGMENTS = [
  { key: 'verified', label: 'Verified', className: 'bg-black' },
  { key: 'partial', label: 'Partial', className: 'hatch' },
  { key: 'unverified', label: 'Unverified', className: 'bg-white' },
]

export function VerificationBar({ counts }) {
  const total = SEGMENTS.reduce((sum, { key }) => sum + counts[key], 0)
  if (!total) return <p>No skills recorded yet.</p>
  return (
    <div>
      <div
        role="img"
        aria-label={SEGMENTS.map(({ key, label }) => `${label} ${counts[key]}`).join(', ')}
        className="flex h-12 gap-0.5"
      >
        {SEGMENTS.filter(({ key }) => counts[key]).map(({ key, label, className }) => (
          <div
            key={key}
            title={`${label}: ${counts[key]}`}
            className={`border-[3px] border-black ${className}`}
            style={{ flexGrow: counts[key], flexBasis: 0 }}
          />
        ))}
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {SEGMENTS.map(({ key, label, className }) => (
          <li key={key} className="flex items-center gap-2">
            <span aria-hidden className={`h-5 w-5 border-[3px] border-black ${className}`} />
            <span>
              {label} <b className="font-mono">{counts[key]}</b>{' '}
              <span className="font-mono text-sm">({Math.round((100 * counts[key]) / total)}%)</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
