export type Country = { code: string; alpha3: string; numeric: string; name: string; continent?: string }
export type Place = { code: string; place_type: 'region' | 'city' | 'airport' | 'country'; name: string; country_code?: string; region_code?: string; latitude?: number; longitude?: number }
export type PlaceStatus = { id: string; place_type: 'country' | 'region' | 'city' | 'airport'; place_code: string; status: 'visited' | 'lived' | 'planned'; first_visited_on?: string; last_visited_on?: string; notes?: string }
export type Visit = { id: string; place_type: 'country' | 'region' | 'city' | 'airport'; place_code: string; arrived_on?: string; departed_on?: string; trip_id?: string; notes?: string }
export type TripStop = { id: string; place_code: string; arrival_date?: string; departure_date?: string; position: number; notes?: string }
export type Trip = { id: string; name: string; start_date?: string; end_date?: string; status: 'planned' | 'completed' | 'cancelled'; notes?: string; stops: TripStop[] }
export type Statistics = { countries_visited: number; countries_lived: number; countries_planned: number; recognized_countries: number; visited_percentage: number; trips: number; visits: number; travel_days: number; regions_visited: number; regions_total: number; regions_percentage: number; cities_visited: number; airports_visited: number }
export type HealthResponse = { status: string; service: string; timestamp: string }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { headers: { 'Content-Type': 'application/json', ...init?.headers }, ...init })
  if (!response.ok) { const body = await response.json().catch(() => ({})) as { detail?: string }; throw new Error(body.detail ?? `API returned ${response.status}`) }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const getHealth = () => request<HealthResponse>('/health')
export const getCountries = () => request<Country[]>('/countries')
export const getPlaces = (type: 'region' | 'city' | 'airport', countryCode?: string, featured = true) => request<Place[]>(`/places/${type}?limit=50000&featured=${featured}${countryCode ? `&country_code=${countryCode}` : ''}`)
export const searchCountries = (query: string) => request<Country[]>(`/search?q=${encodeURIComponent(query)}`)
export const getStatuses = () => request<PlaceStatus[]>('/place-statuses')
export const saveStatus = (code: string, body: Pick<PlaceStatus, 'status' | 'first_visited_on' | 'last_visited_on' | 'notes'>) => request<PlaceStatus>(`/place-statuses/country/${code}`, { method: 'PUT', body: JSON.stringify(body) })
export const savePlaceStatus = (placeType: string, code: string, body: Pick<PlaceStatus, 'status' | 'first_visited_on' | 'last_visited_on' | 'notes'>) => request<PlaceStatus>(`/place-statuses/${placeType}/${encodeURIComponent(code)}`, { method: 'PUT', body: JSON.stringify(body) })
export const deleteStatus = (code: string) => request<void>(`/place-statuses/country/${code}`, { method: 'DELETE' })
export const deletePlaceStatus = (placeType: string, code: string) => request<void>(`/place-statuses/${placeType}/${encodeURIComponent(code)}`, { method: 'DELETE' })
export const getVisits = () => request<Visit[]>('/visits')
export const createVisit = (body: Omit<Visit, 'id' | 'place_type'> & { place_type?: Visit['place_type'] }) => request<Visit>('/visits', { method: 'POST', body: JSON.stringify(body) })
export const deleteVisit = (id: string) => request<void>(`/visits/${id}`, { method: 'DELETE' })
export const updateVisit = (id: string, body: Omit<Visit, 'id'>) => request<Visit>(`/visits/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const getTrips = () => request<Trip[]>('/trips')
export const createTrip = (body: Omit<Trip, 'id' | 'stops'>) => request<Trip>('/trips', { method: 'POST', body: JSON.stringify(body) })
export const updateTrip = (id: string, body: Omit<Trip, 'id' | 'stops'>) => request<Trip>(`/trips/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const deleteTrip = (id: string) => request<void>(`/trips/${id}`, { method: 'DELETE' })
export const addTripStop = (tripId: string, body: Omit<TripStop, 'id'>) => request<TripStop>(`/trips/${tripId}/stops`, { method: 'POST', body: JSON.stringify(body) })
export const deleteTripStop = (tripId: string, stopId: string) => request<void>(`/trips/${tripId}/stops/${stopId}`, { method: 'DELETE' })
export const getStatistics = () => request<Statistics>('/statistics/summary')
export const exportBackup = () => request<Record<string, unknown>>('/backups/export')
export const importBackup = (backup: Record<string, unknown>) => request<{ statuses: number; trips: number; visits: number }>('/backups/import', { method: 'POST', body: JSON.stringify(backup) })
