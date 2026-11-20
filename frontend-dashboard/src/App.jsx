import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, fmt, statusColor, statusLabel, wsUrl } from './api.js'
import GisMapViewer from './components/GisMapViewer.jsx'
import Bim3DViewer from './components/Bim3DViewer.jsx'
import StiffnessCharts from './components/StiffnessCharts.jsx'
import ElementPanel from './components/ElementPanel.jsx'
import AiAssistant from './components/AiAssistant.jsx'

export default function App() {
  const [health, setHealth] = useState(null)
  const [buildings, setBuildings] = useState(null) // FeatureCollection
  const [buildingId, setBuildingId] = useState('EDIF-03')
  const [detail, setDetail] = useState(null)
  const [selectedGid, setSelectedGid] = useState(null)
  const [liveSensors, setLiveSensors] = useState(null)
  const [wsOk, setWsOk] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(e.message))
    api.buildings().then(setBuildings).catch((e) => setError(e.message))
  }, [])

  // Telemetría en tiempo real por WebSocket (con reconexión)
  useEffect(() => {
    let ws
    let retry
    let closed = false
    const connect = () => {
      ws = new WebSocket(wsUrl('/ws/stiffness'))
      ws.onopen = () => setWsOk(true)
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        if (msg.type !== 'snapshot') return
        setLiveSensors(msg.sensors)
        setBuildings((fc) =>
          fc && {
            ...fc,
            features: fc.features.map((f) => ({
              ...f,
              properties: { ...f.properties, status: msg.buildings[f.properties.building_id] ?? f.properties.status },
            })),
          },
        )
      }
      ws.onclose = () => {
        setWsOk(false)
        if (!closed) retry = setTimeout(connect, 5000)
      }
    }
    connect()
    return () => {
      closed = true
      clearTimeout(retry)
      ws?.close()
    }
  }, [])

  useEffect(() => {
    setDetail(null)
    setSelectedGid(null)
    api.building(buildingId).then(setDetail).catch((e) => setError(e.message))
  }, [buildingId])

  const allSensors = useMemo(() => liveSensors ?? [], [liveSensors])
  const sensors = useMemo(() => {
    if (!detail) return []
    if (!liveSensors) return detail.sensors
    return liveSensors.filter((s) => s.building_id === buildingId)
  }, [detail, liveSensors, buildingId])

  const building = detail?.building
  const props = buildings?.features.map((f) => f.properties) ?? []
  const selectedSensor = sensors.find((s) => s.ifc_global_id === selectedGid)

  const selectBuilding = useCallback((id) => setBuildingId(id), [])

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-slate-900 text-white px-5 py-3 flex flex-wrap items-center gap-4">
        <div className="mr-auto">
          <h1 className="text-lg font-semibold leading-tight">Gemelo Digital Estructural</h1>
          <p className="text-xs text-slate-300">BIM + GIS + IoT · Monitoreo de rigidez estructural (k)</p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${wsOk ? 'bg-green-400' : 'bg-slate-500'}`} />
            {wsOk ? 'Tiempo real' : 'Sin conexión en vivo'}
          </span>
          {health && (
            <span className="rounded bg-slate-700 px-2 py-0.5">
              {health.mode === 'demo' ? 'Modo demo' : 'PostGIS + TimescaleDB'} · v{health.version}
            </span>
          )}
        </div>
      </header>

      {error && (
        <div className="bg-red-50 text-red-700 text-sm px-5 py-2 border-b border-red-200">
          No se pudo conectar con la API: {error}. Verifique que el backend esté en ejecución.
        </div>
      )}

      <main className="flex-1 p-4 grid gap-4 grid-cols-1 lg:grid-cols-12 auto-rows-min">
        {/* Tarjetas de edificaciones */}
        <section className="lg:col-span-12 grid grid-cols-2 md:grid-cols-4 gap-3">
          {props.map((b) => (
            <button
              key={b.building_id}
              onClick={() => selectBuilding(b.building_id)}
              className={`panel text-left p-3 border-l-4 transition ${
                b.building_id === buildingId ? 'ring-2 ring-slate-800' : 'hover:shadow'
              }`}
              style={{ borderLeftColor: statusColor(b.status) }}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-slate-500">{b.building_id}</span>
                <span className="text-xs font-semibold" style={{ color: statusColor(b.status) }}>
                  {statusLabel(b.status)}
                </span>
              </div>
              <div className="font-semibold text-sm mt-0.5">{b.name}</div>
              <div className="text-xs text-slate-500 mt-1">
                {b.is_monitored
                  ? `${b.sensor_count} sensores · peor Δk ${fmt.dk(b.worst_delta_k_pct)}`
                  : 'Sin sensores · línea base BIM/COBie'}
              </div>
            </button>
          ))}
        </section>

        <section className="panel lg:col-span-4 h-[440px]">
          <div className="panel-title">Panel GIS · 4 edificaciones</div>
          <GisMapViewer data={buildings} selectedId={buildingId} onSelect={selectBuilding} />
        </section>

        <section className="panel lg:col-span-5 h-[440px]">
          <div className="panel-title">
            <span>Visor estructural 3D · {building ? `${building.building_id} ${building.name}` : '…'}</span>
            {selectedSensor && (
              <span className="text-xs font-normal">
                {selectedSensor.element_name}: <b>{fmt.dk(selectedSensor.delta_k_pct)}</b>
              </span>
            )}
          </div>
          <Bim3DViewer
            building={building}
            sensors={sensors}
            selectedGid={selectedGid}
            onSelectElement={setSelectedGid}
          />
        </section>

        <section className="panel lg:col-span-3 h-[440px]">
          <div className="panel-title">Elemento · COBie</div>
          <ElementPanel
            gid={selectedGid}
            components={detail?.components ?? []}
            sensors={sensors}
            onSelect={setSelectedGid}
          />
        </section>

        <section className="panel lg:col-span-8 min-h-[420px]">
          <StiffnessCharts
            buildingId={buildingId}
            building={building}
            allSensors={allSensors}
            selectedSensorId={selectedSensor?.sensor_id}
          />
        </section>

        <section className="panel lg:col-span-4 min-h-[420px]">
          <div className="panel-title">Asistente IA · resumen ejecutivo</div>
          <AiAssistant buildingId={buildingId} provider={health?.ai} />
        </section>
      </main>

      <footer className="px-5 py-3 text-xs text-slate-500">
        Llaves de vinculación: <code>building_id</code> (GIS) · <code>ifc_global_id</code> (IFC/COBie) ·{' '}
        <code>sensor_id</code> (IoT). Umbrales Δk: alerta ≤ {health?.thresholds.warn_pct ?? -5} %, crítico ≤{' '}
        {health?.thresholds.crit_pct ?? -15} %.
      </footer>
    </div>
  )
}
