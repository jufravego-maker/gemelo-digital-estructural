import { useState } from 'react'
import { api } from '../api.js'

/** Asistente embebido: resumen ejecutivo con Gemini API (o por reglas si no hay clave). */
export default function AiAssistant({ buildingId, provider }) {
  const [scope, setScope] = useState('campus')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      setResult(await api.summary(scope === 'campus' ? null : buildingId))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col p-3 gap-2">
      <div className="flex items-center gap-1">
        <button className={`btn ${scope === 'campus' ? 'btn-active' : ''}`} onClick={() => setScope('campus')}>
          Todo el campus
        </button>
        <button className={`btn ${scope === 'building' ? 'btn-active' : ''}`} onClick={() => setScope('building')}>
          {buildingId}
        </button>
        <button className="btn ml-auto bg-blue-600 text-white border-blue-600 hover:bg-blue-500" onClick={run} disabled={loading}>
          {loading ? 'Generando…' : 'Generar resumen'}
        </button>
      </div>
      <div className="text-[11px] text-slate-500">
        Motor: {provider === 'gemini' ? 'Gemini API' : 'reglas locales (defina GEMINI_API_KEY en el backend para usar Gemini)'}
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm whitespace-pre-wrap">
        {error && <span className="text-red-600">{error}</span>}
        {!error && !result && (
          <span className="text-slate-400">
            Genere un resumen del estado de rigidez y alertas de mantenimiento predictivo.
          </span>
        )}
        {result?.warning && <div className="text-xs text-amber-700 mb-2">{result.warning}</div>}
        {result?.text}
      </div>
    </div>
  )
}
