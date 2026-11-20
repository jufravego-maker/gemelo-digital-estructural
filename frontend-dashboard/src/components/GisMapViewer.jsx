import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { STATUS } from '../api.js'

const BASEMAP = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}

const COLOR_EXPR = [
  'match',
  ['get', 'status'],
  ...Object.entries(STATUS).flatMap(([k, v]) => [k, v.color]),
  STATUS.sin_dato.color,
]

function bbox(fc) {
  const b = [Infinity, Infinity, -Infinity, -Infinity]
  const walk = (c) => {
    if (typeof c[0] === 'number') {
      b[0] = Math.min(b[0], c[0]); b[1] = Math.min(b[1], c[1])
      b[2] = Math.max(b[2], c[0]); b[3] = Math.max(b[3], c[1])
    } else c.forEach(walk)
  }
  fc.features.forEach((f) => walk(f.geometry.coordinates))
  return [[b[0], b[1]], [b[2], b[3]]]
}

/** Panel GIS (MapLibre GL JS): huellas extruidas por número de niveles y coloreadas por estado. */
export default function GisMapViewer({ data, selectedId, onSelect }) {
  const container = useRef(null)
  const mapRef = useRef(null)
  const onSelectRef = useRef(onSelect)
  const fitted = useRef(false)
  const [ready, setReady] = useState(false)
  onSelectRef.current = onSelect

  useEffect(() => {
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP,
      center: [-74.0655, 4.6278],
      zoom: 17,
      pitch: 50,
      bearing: -20,
    })
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 })

    map.on('load', () => {
      map.addSource('buildings', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({
        id: 'b-fill',
        type: 'fill-extrusion',
        source: 'buildings',
        paint: {
          'fill-extrusion-color': COLOR_EXPR,
          'fill-extrusion-height': ['*', ['coalesce', ['get', 'levels'], 1], 3.5],
          'fill-extrusion-opacity': 0.85,
        },
      })
      map.addLayer({
        id: 'b-outline',
        type: 'line',
        source: 'buildings',
        paint: { 'line-color': '#0f172a', 'line-width': 1 },
      })
      setReady(true)
    })
    map.on('click', 'b-fill', (e) => onSelectRef.current?.(e.features[0].properties.building_id))
    map.on('mousemove', 'b-fill', (e) => {
      map.getCanvas().style.cursor = 'pointer'
      const p = e.features[0].properties
      popup.setLngLat(e.lngLat).setHTML(`<b>${p.building_id}</b> · ${p.name}<br/>${p.levels} niveles`).addTo(map)
    })
    map.on('mouseleave', 'b-fill', () => {
      map.getCanvas().style.cursor = ''
      popup.remove()
    })
    mapRef.current = map
    return () => map.remove()
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !data) return
    map.getSource('buildings').setData(data)
    if (!fitted.current && data.features.length) {
      map.fitBounds(bbox(data), { padding: 50, duration: 0, pitch: 50, bearing: -20 })
      fitted.current = true
    }
  }, [ready, data])

  useEffect(() => {
    const map = mapRef.current
    if (!ready) return
    const sel = ['==', ['get', 'building_id'], selectedId ?? '']
    map.setPaintProperty('b-outline', 'line-width', ['case', sel, 4, 1])
    map.setPaintProperty('b-outline', 'line-color', ['case', sel, '#2563eb', '#0f172a'])
  }, [ready, selectedId])

  return (
    <div className="relative flex-1 min-h-0">
      <div ref={container} className="absolute inset-0 rounded-b-xl overflow-hidden" />
      <div className="absolute left-2 bottom-2 bg-white/90 rounded-md shadow px-2 py-1.5 text-[11px] space-y-0.5">
        {['optimo', 'alerta', 'critico', 'referencia'].map((s) => (
          <div key={s} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: STATUS[s].color }} />
            {STATUS[s].label}
          </div>
        ))}
      </div>
    </div>
  )
}
