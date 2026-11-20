const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

async function get(path) {
  const r = await fetch(`${API}${path}`)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${path}`)
  return r.json()
}

export const api = {
  health: () => get('/api/health'),
  buildings: () => get('/api/buildings'),
  building: (id) => get(`/api/buildings/${encodeURIComponent(id)}`),
  element: (gid) => get(`/api/elements/${encodeURIComponent(gid)}`),
  series: (params) => get(`/api/stiffness?${new URLSearchParams(params)}`),
  csvUrl: (params) => `${API}/api/stiffness/export.csv?${new URLSearchParams(params)}`,
  summary: async (building_id) => {
    const r = await fetch(`${API}/api/ai/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ building_id }),
    })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    return r.json()
  },
}

export function wsUrl(path) {
  const base = API || window.location.origin
  return base.replace(/^http/, 'ws') + path
}

export const STATUS = {
  optimo: { label: 'Óptimo', color: '#16a34a' },
  alerta: { label: 'Alerta', color: '#eab308' },
  critico: { label: 'Crítico', color: '#dc2626' },
  referencia: { label: 'Referencia', color: '#64748b' },
  sin_dato: { label: 'Sin dato', color: '#94a3b8' },
}

export const statusColor = (s) => (STATUS[s] || STATUS.sin_dato).color
export const statusLabel = (s) => (STATUS[s] || STATUS.sin_dato).label

export const fmt = {
  k: (v) => (v == null ? '—' : `${Math.round(v).toLocaleString('es-CO')} kN/m`),
  dk: (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(1)} %`),
}
