import axios from 'axios'

const api = axios.create({ baseURL: '' })

export const getArtist       = (id)      => api.get(`/artists/${id}`)
export const searchArtists   = (params)  => api.get('/artists/', { params })
export const getMomentum     = (params)  => api.get('/dashboard/momentum', { params })
export const submitFeedback  = (data)    => api.post('/feedback/', data)
export const explainArtist   = (id, model = 'breakout', model_type = 'ebm') =>
  api.get(`/explain/${id}`, { params: { model, model_type } })

export const discoverLofi    = (params) => api.get('/discover/lofi-fit', { params })

export default api
