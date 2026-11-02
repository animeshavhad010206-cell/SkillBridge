function errorMessage(data, status) {
  if (typeof data?.detail === 'string') return data.detail
  if (Array.isArray(data?.detail)) return data.detail[0].msg.replace(/^Value error, /, '')
  return status >= 500 ? 'The server had a problem. Try again in a moment.' : 'Something went wrong.'
}

export async function api(path, { method = 'GET', body, form } = {}) {
  let response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: form ?? (body ? JSON.stringify(body) : undefined),
    })
  } catch {
    throw new Error('Could not reach the server. Is the backend running?')
  }

  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errorMessage(data, response.status))
  return data
}

// The API sends UTC without a timezone suffix.
export function formatDate(value) {
  if (!value) return 'Unknown'
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
