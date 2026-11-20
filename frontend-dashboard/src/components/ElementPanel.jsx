import { useEffect, useState } from 'react'
import { api, fmt, statusColor, statusLabel } from '../api.js'

const COMPONENT_FIELDS = [
  ['type_name', 'Tipo'],
  ['space', 'Espacio'],
  ['description', 'Descripción'],
  ['asset_identifier', 'AssetIdentifier'],
  ['tag_number', 'TagNumber (sensor)'],
  ['installation_date', 'Instalación'],
  ['ext_system', 'Sistema origen'],
]

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-3 py-1 border-b border-slate-100 text-xs">
      <span className="text-slate-500 shrink-0">{label}</span>
      <span className="text-right break-all">{value ?? '—'}</span>
    </div>
  )
}

/** Metadatos COBie del elemento seleccionado (ExtIdentifier = GlobalId) y su sensor. */
export default function ElementPanel({ gid, components, sensors, onSelect }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setData(null)
    setError(null)
    if (!gid) return
    api.element(gid).then(setData).catch((e) => setError(e.message))
  }, [gid])

  const live = sensors.find((s) => s.ifc_global_id === gid) ?? data?.sensor

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
      {!gid && (
        <p className="text-xs text-slate-500">
          Seleccione un elemento instrumentado en el visor 3D o un componente de la lista.
        </p>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}

      {data && (
        <>
          <div>
            <div className="font-semibold text-sm">{data.component.name}</div>
            <div className="text-[11px] font-mono text-slate-500 break-all">
              {data.component.ext_object} · {data.component.ifc_global_id}
            </div>
          </div>

          {live ? (
            <div className="rounded-lg border p-2" style={{ borderColor: statusColor(live.status) }}>
              <div className="flex items-center justify-between text-xs">
                <span className="font-mono">{live.sensor_id}</span>
                <span className="font-semibold" style={{ color: statusColor(live.status) }}>
                  {statusLabel(live.status)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-1.5">
                <div>
                  <div className="text-[10px] text-slate-500">k actual</div>
                  <div className="text-sm font-semibold">{fmt.k(live.k_kn_m)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Δk vs. diseño</div>
                  <div className="text-sm font-semibold" style={{ color: statusColor(live.status) }}>
                    {fmt.dk(live.delta_k_pct)}
                  </div>
                </div>
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                k diseño {fmt.k(live.k_design_kn_m)} · {live.sensor_type?.replace('_', ' ')}
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500 rounded-lg border border-dashed p-2">Elemento sin sensor IoT.</div>
          )}

          <div>
            <div className="text-xs font-semibold text-slate-600 mb-1">COBie · Component</div>
            {COMPONENT_FIELDS.map(([k, label]) => (
              <Row key={k} label={label} value={data.component[k]} />
            ))}
          </div>
          {data.attributes.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-slate-600 mb-1">COBie · Attribute</div>
              {data.attributes.map((a) => (
                <Row key={a.name} label={a.name} value={a.unit ? `${a.value} ${a.unit}` : a.value} />
              ))}
            </div>
          )}
        </>
      )}

      <div>
        <div className="text-xs font-semibold text-slate-600 mb-1">Componentes COBie del edificio</div>
        <div className="flex flex-wrap gap-1">
          {components.map((c) => {
            const s = sensors.find((x) => x.ifc_global_id === c.ifc_global_id)
            return (
              <button
                key={c.ifc_global_id}
                onClick={() => onSelect(c.ifc_global_id)}
                className={`btn flex items-center gap-1 ${c.ifc_global_id === gid ? 'btn-active' : ''}`}
                title={c.ifc_global_id}
              >
                <span className="h-2 w-2 rounded-full" style={{ background: statusColor(s ? s.status : 'referencia') }} />
                {c.name}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
