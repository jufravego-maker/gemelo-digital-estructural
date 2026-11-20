import { useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { api, statusColor } from '../api.js'

const RANGES = [
  { hours: 24, label: '24 h' },
  { hours: 168, label: '7 días' },
  { hours: 720, label: '30 días' },
]
const PALETTE = ['#2563eb', '#7c3aed', '#0891b2', '#db2777', '#ea580c', '#65a30d']

function EChart({ option, className }) {
  const ref = useRef(null)
  const chart = useRef(null)
  useEffect(() => {
    chart.current = echarts.init(ref.current)
    const ro = new ResizeObserver(() => chart.current?.resize())
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      chart.current.dispose()
    }
  }, [])
  useEffect(() => {
    if (option) chart.current?.setOption(option, true)
  }, [option])
  return <div ref={ref} className={className} />
}

/** Panel analítico IoT (Apache ECharts): k vs. tiempo y comparación entre edificaciones. */
export default function StiffnessCharts({ buildingId, building, allSensors, selectedSensorId }) {
  const [hours, setHours] = useState(168)
  const [mode, setMode] = useState('dk') // 'dk' (Δk %) o 'k' (kN/m)
  const [data, setData] = useState(null)
  const [thresholds, setThresholds] = useState({ warn_pct: -5, crit_pct: -15 })
  const monitored = building?.is_monitored

  useEffect(() => {
    api.health().then((h) => setThresholds(h.thresholds)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!monitored) {
      setData(null)
      return
    }
    let alive = true
    const load = () =>
      api.series({ building_id: buildingId, hours }).then((d) => alive && setData(d)).catch(() => {})
    load()
    const t = setInterval(load, 60_000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [buildingId, hours, monitored])

  const lineOption = useMemo(() => {
    if (!data) return null
    const idx = mode === 'dk' ? 2 : 1
    const series = data.series.map((s, i) => ({
      name: `${s.sensor_id} · ${s.element_name}`,
      type: 'line',
      showSymbol: false,
      sampling: 'lttb',
      lineStyle: { width: s.sensor_id === selectedSensorId ? 3 : 1.5 },
      emphasis: { focus: 'series' },
      color: PALETTE[i % PALETTE.length],
      data: s.points.map((p) => [p[0], p[idx]]),
    }))
    if (mode === 'dk' && series.length) {
      series[0].markLine = {
        silent: true,
        symbol: 'none',
        data: [
          { yAxis: thresholds.warn_pct, lineStyle: { color: statusColor('alerta'), type: 'dashed' }, label: { formatter: 'Alerta' } },
          { yAxis: thresholds.crit_pct, lineStyle: { color: statusColor('critico'), type: 'dashed' }, label: { formatter: 'Crítico' } },
        ],
      }
    }
    return {
      tooltip: { trigger: 'axis', valueFormatter: (v) => (v == null ? '—' : mode === 'dk' ? `${v.toFixed(2)} %` : `${Math.round(v).toLocaleString('es-CO')} kN/m`) },
      legend: { type: 'scroll', top: 0, textStyle: { fontSize: 11 } },
      grid: { left: 64, right: 24, top: 48, bottom: 56 },
      xAxis: { type: 'time' },
      yAxis: {
        type: 'value',
        name: mode === 'dk' ? 'Δk (%)' : 'k (kN/m)',
        scale: true,
        min: mode === 'dk' ? (v) => Math.floor(Math.min(v.min, thresholds.crit_pct) - 2) : undefined,
        max: mode === 'dk' ? (v) => Math.ceil(Math.max(v.max, 0) + 1) : undefined,
        axisLabel: { formatter: (v) => (mode === 'dk' ? v : Math.round(v).toLocaleString('es-CO')) },
      },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8 }],
      series,
    }
  }, [data, mode, selectedSensorId, thresholds])

  const barOption = useMemo(() => {
    const sensors = [...allSensors].sort((a, b) => a.sensor_id.localeCompare(b.sensor_id))
    if (!sensors.length) return null
    return {
      tooltip: {
        trigger: 'item',
        formatter: (p) => `${p.name}<br/>Δk: <b>${p.value.toFixed(2)} %</b>`,
      },
      grid: { left: 48, right: 16, top: 16, bottom: 56 },
      xAxis: { type: 'category', data: sensors.map((s) => s.sensor_id), axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: { type: 'value', name: 'Δk (%)', max: (v) => Math.ceil(Math.max(v.max, 0) + 1), min: (v) => Math.floor(Math.min(v.min, thresholds.crit_pct) - 2) },
      series: [
        {
          type: 'bar',
          data: sensors.map((s) => ({
            value: s.delta_k_pct ?? 0,
            itemStyle: {
              color: statusColor(s.status),
              opacity: s.building_id === buildingId ? 1 : 0.45,
            },
          })),
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              { yAxis: thresholds.warn_pct, lineStyle: { color: statusColor('alerta'), type: 'dashed' } },
              { yAxis: thresholds.crit_pct, lineStyle: { color: statusColor('critico'), type: 'dashed' } },
            ],
            label: { show: false },
          },
        },
      ],
    }
  }, [allSensors, buildingId, thresholds])

  return (
    <>
      <div className="panel-title flex-wrap">
        <span>Panel analítico IoT · rigidez estructural</span>
        <div className="flex items-center gap-1">
          {RANGES.map((r) => (
            <button key={r.hours} className={`btn ${hours === r.hours ? 'btn-active' : ''}`} onClick={() => setHours(r.hours)}>
              {r.label}
            </button>
          ))}
          <span className="w-2" />
          <button className={`btn ${mode === 'dk' ? 'btn-active' : ''}`} onClick={() => setMode('dk')}>Δk %</button>
          <button className={`btn ${mode === 'k' ? 'btn-active' : ''}`} onClick={() => setMode('k')}>k kN/m</button>
          <span className="w-2" />
          <a
            className={`btn ${monitored ? '' : 'pointer-events-none opacity-50'}`}
            href={api.csvUrl({ building_id: buildingId, hours })}
            download
          >
            Descargar CSV
          </a>
        </div>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-3 flex-1 min-h-0">
        <div className="xl:col-span-2 relative min-h-[340px]">
          {monitored ? (
            <EChart option={lineOption} className="absolute inset-0" />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500 p-6 text-center">
              {building ? `${building.building_id} es la edificación de referencia: no tiene series de rigidez.` : 'Cargando…'}
            </div>
          )}
        </div>
        <div className="relative min-h-[340px] border-t xl:border-t-0 xl:border-l border-slate-200">
          <div className="absolute top-1 left-3 text-xs font-medium text-slate-500">Δk actual · 3 edificaciones</div>
          <EChart option={barOption} className="absolute inset-0 top-5" />
        </div>
      </div>
    </>
  )
}
