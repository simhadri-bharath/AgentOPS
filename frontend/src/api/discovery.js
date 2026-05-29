import { api } from './client'

export function syncVertexAI() {
  return api.post('/api/v1/discovery/vertex-ai/sync')
}

export function testVertexAI() {
  return api.get('/api/v1/discovery/vertex-ai/test')
}
