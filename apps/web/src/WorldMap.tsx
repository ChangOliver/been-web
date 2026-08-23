import { useMemo } from 'react'
import { geoEqualEarth, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import world from 'world-atlas/countries-110m.json'
import type { Country, PlaceStatus } from './api'

type Props = { countries: Country[]; statuses: PlaceStatus[]; onSelect: (country: Country) => void }

export function WorldMap({ countries, statuses, onSelect }: Props) {
  const countryByNumeric = useMemo(() => new Map(countries.map((country) => [String(Number(country.numeric)), country])), [countries])
  const statusByCode = useMemo(() => new Map(statuses.map((item) => [item.place_code, item.status])), [statuses])
  const collection = useMemo(() => feature(world as never, world.objects.countries as never) as unknown as GeoJSON.FeatureCollection, [])
  const path = useMemo(() => {
    const projection = geoEqualEarth().fitSize([900, 460], collection)
    return geoPath(projection)
  }, [collection])

  return <div className="map-frame" aria-label="Interactive world map">
    <svg viewBox="0 0 900 460" role="img">
      <rect width="900" height="460" rx="20" fill="#0b2a37" />
      {collection.features.map((shape) => {
        const country = countryByNumeric.get(String(Number(shape.id)))
        if (!country) return null
        const status = statusByCode.get(country.code)
        return <path key={country.code} d={path(shape) ?? ''} className={`country-shape ${status ?? ''}`} onClick={() => onSelect(country)} tabIndex={0} role="button" aria-label={country.name} onKeyDown={(event) => { if (event.key === 'Enter') onSelect(country) }} />
      })}
    </svg>
    <div className="map-legend"><span><i className="legend-swatch visited" /> Visited</span><span><i className="legend-swatch lived" /> Lived</span><span><i className="legend-swatch planned" /> Planned</span></div>
  </div>
}

