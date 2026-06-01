import { API_BASE } from './config'

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

async function parseJson(res) {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return { detail: text }
  }
}

export async function apiRequest(path, options = {}) {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
    ...options,
  })

  const data = await parseJson(res)

  if (!res.ok) {
    const detail =
      typeof data?.detail === 'string'
        ? data.detail
        : data?.message || res.statusText || 'Request failed'
    throw new ApiError(detail, res.status, data)
  }

  return data
}

export async function apiUpload(path, formData) {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    method: 'POST',
    body: formData,
    headers: { Accept: 'application/json' },
  })
  const data = await parseJson(res)
  if (!res.ok) {
    const detail =
      typeof data?.detail === 'string'
        ? data.detail
        : data?.message || res.statusText || 'Upload failed'
    throw new ApiError(detail, res.status, data)
  }
  return data
}

export const api = {
  get: (path) => apiRequest(path),
  post: (path, body) =>
    apiRequest(path, {
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: (path, body) =>
    apiRequest(path, {
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  delete: (path) => apiRequest(path, { method: 'DELETE' }),
}
