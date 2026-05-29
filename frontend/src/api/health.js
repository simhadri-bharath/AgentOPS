import { api } from './client'

export function fetchHealth() {
  return api.get('/health')
}
