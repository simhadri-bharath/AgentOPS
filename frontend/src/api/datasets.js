import { api, apiUpload } from './client'

export function fetchDatasets(params = {}) {
  const qs = new URLSearchParams()
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return api.get(`/api/v1/datasets${query ? `?${query}` : ''}`)
}

export function fetchDataset(datasetId) {
  return api.get(`/api/v1/datasets/${datasetId}`)
}

export function uploadDataset(file, { name, description } = {}) {
  const form = new FormData()
  form.append('file', file)
  if (name) form.append('name', name)
  if (description) form.append('description', description)
  return apiUpload('/api/v1/datasets/upload', form)
}

export function deleteDataset(datasetId) {
  return api.delete(`/api/v1/datasets/${datasetId}`)
}

export function previewSessionDataset(body) {
  return api.post('/api/v1/datasets/from-sessions/preview', body)
}

export function createDatasetFromSessions(body) {
  return api.post('/api/v1/datasets/from-sessions', body)
}

export function setDatasetReviewStatus(datasetId, reviewStatus) {
  return api.patch(`/api/v1/datasets/${datasetId}/review`, { review_status: reviewStatus })
}
