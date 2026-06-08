import { api } from './client'

export function syncVertexAI() {
  return api.post('/api/v1/discovery/vertex-ai/sync')
}

export function testVertexAI() {
  return api.get('/api/v1/discovery/vertex-ai/test')
}

export function syncCloudRun() {
  return api.post('/api/v1/discovery/cloud-run/sync')
}

export function testCloudRun() {
  return api.get('/api/v1/discovery/cloud-run/test')
}

export function syncAll() {
  return api.post('/api/v1/discovery/sync-all')
}
