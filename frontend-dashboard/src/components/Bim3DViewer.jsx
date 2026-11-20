import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STATUS, statusColor } from '../api.js'

/**
 * Visor estructural 3D.
 *
 * v0.1: genera un pórtico paramétrico (niveles × vanos del edificio) y ubica los elementos
 * instrumentados según la tabla maestra (level, grid_x, grid_y), coloreados por Δk.
 * Fase 3: reemplazar buildFrame() por la carga del modelo IFC/GLB real (That Open Engine)
 * y usar el GlobalId de cada malla como userData.gid; el resto del visor no cambia.
 */
const BAY_X = 6
const BAY_Y = 5
const STOREY = 3.5

const BASE_MAT = new THREE.MeshStandardMaterial({ color: '#cbd5e1', transparent: true, opacity: 0.35 })
const SLAB_MAT = new THREE.MeshStandardMaterial({ color: '#94a3b8', transparent: true, opacity: 0.08, depthWrite: false })

function box(w, h, d, mat, x, y, z) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat)
  m.position.set(x, y, z)
  return m
}

function elementMesh(cls, level, gx, gy, mat) {
  const z = gy * BAY_Y
  if (cls === 'IfcColumn') return box(0.55, STOREY, 0.55, mat, gx * BAY_X, (level - 0.5) * STOREY, z)
  if (cls === 'IfcBeam') return box(BAY_X, 0.5, 0.4, mat, (gx + 0.5) * BAY_X, level * STOREY - 0.25, z)
  if (cls === 'IfcWall') return box(BAY_X, STOREY - 0.5, 0.3, mat, (gx + 0.5) * BAY_X, (level - 0.5) * STOREY - 0.25, z)
  return box(0.6, 0.6, 0.6, mat, gx * BAY_X, (level - 0.5) * STOREY, z)
}

function disposeGroup(group) {
  group.traverse((o) => {
    if (o.isMesh || o.isLine) {
      o.geometry.dispose()
      if (o.material !== BASE_MAT && o.material !== SLAB_MAT) o.material.dispose()
    }
  })
  group.clear()
}

function buildFrame(group, building, sensors) {
  disposeGroup(group)
  const nx = building.bays_x ?? 3
  const ny = building.bays_y ?? 2
  const levels = building.levels ?? 4
  const taken = new Set(sensors.map((s) => `${s.ifc_class}:${s.level}:${s.grid_x}:${s.grid_y}`))
  const add = (key, mesh) => !taken.has(key) && group.add(mesh)

  for (let l = 1; l <= levels; l++) {
    for (let i = 0; i <= nx; i++)
      for (let j = 0; j <= ny; j++) add(`IfcColumn:${l}:${i}:${j}`, elementMesh('IfcColumn', l, i, j, BASE_MAT))
    for (let i = 0; i < nx; i++)
      for (let j = 0; j <= ny; j++) add(`IfcBeam:${l}:${i}:${j}`, elementMesh('IfcBeam', l, i, j, BASE_MAT))
    for (let i = 0; i <= nx; i++)
      for (let j = 0; j < ny; j++)
        group.add(box(0.35, 0.5, BAY_Y, BASE_MAT, i * BAY_X, l * STOREY - 0.25, (j + 0.5) * BAY_Y))
    group.add(box(nx * BAY_X, 0.15, ny * BAY_Y, SLAB_MAT, (nx * BAY_X) / 2, l * STOREY, (ny * BAY_Y) / 2))
  }

  const pickables = []
  const byGid = new Map()
  for (const s of sensors) {
    const mat = new THREE.MeshStandardMaterial({ color: statusColor(s.status), emissive: '#000000' })
    const mesh = elementMesh(s.ifc_class, s.level, s.grid_x, s.grid_y, mat)
    mesh.userData = { gid: s.ifc_global_id, sensor_id: s.sensor_id }
    group.add(mesh)
    pickables.push(mesh)
    byGid.set(s.ifc_global_id, mesh)
  }
  group.position.set((-nx * BAY_X) / 2, 0, (-ny * BAY_Y) / 2)
  return { pickables, byGid, size: { w: nx * BAY_X, d: ny * BAY_Y, h: levels * STOREY } }
}

export default function Bim3DViewer({ building, sensors, selectedGid, onSelectElement }) {
  const mountRef = useRef(null)
  const ctx = useRef({})
  ctx.current.onSelect = onSelectElement

  // Escena, cámara, controles y selección por clic (una sola vez)
  useEffect(() => {
    const el = mountRef.current
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#f8fafc')
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 2000)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    scene.add(new THREE.HemisphereLight(0xffffff, 0x94a3b8, 1.4))
    const sun = new THREE.DirectionalLight(0xffffff, 1.6)
    sun.position.set(40, 60, 30)
    scene.add(sun)
    scene.add(new THREE.GridHelper(120, 40, 0xcbd5e1, 0xe2e8f0))
    const group = new THREE.Group()
    scene.add(group)

    const resize = () => {
      const w = el.clientWidth || 1
      const h = el.clientHeight || 1
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(el)
    resize()

    let raf
    const loop = () => {
      controls.update()
      renderer.render(scene, camera)
      raf = requestAnimationFrame(loop)
    }
    loop()

    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    let down = null
    const onDown = (e) => (down = [e.clientX, e.clientY])
    const onUp = (e) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return
      const r = renderer.domElement.getBoundingClientRect()
      pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(pointer, camera)
      const hit = raycaster.intersectObjects(ctx.current.pickables ?? [], false)[0]
      ctx.current.onSelect?.(hit ? hit.object.userData.gid : null)
    }
    renderer.domElement.addEventListener('pointerdown', onDown)
    renderer.domElement.addEventListener('pointerup', onUp)

    Object.assign(ctx.current, { renderer, scene, camera, controls, group })
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      renderer.domElement.removeEventListener('pointerdown', onDown)
      renderer.domElement.removeEventListener('pointerup', onUp)
      controls.dispose()
      disposeGroup(group)
      renderer.dispose()
      el.removeChild(renderer.domElement)
    }
  }, [])

  // Geometría: se reconstruye al cambiar de edificio o de sensores instrumentados
  const geomKey = building
    ? `${building.building_id}|${sensors.map((s) => `${s.sensor_id}:${s.level}:${s.grid_x}:${s.grid_y}`).join(',')}`
    : ''
  useEffect(() => {
    const c = ctx.current
    if (!building || !c.group) return
    const { pickables, byGid, size } = buildFrame(c.group, building, sensors)
    c.pickables = pickables
    c.byGid = byGid
    const dist = Math.max(size.w, size.d, size.h) * 1.7
    c.camera.position.set(dist * 0.9, size.h * 0.9 + 6, dist)
    c.controls.target.set(0, size.h / 2, 0)
    c.controls.update()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geomKey])

  // Colores por estado de rigidez y resaltado de la selección
  useEffect(() => {
    const byGid = ctx.current.byGid
    if (!byGid) return
    for (const s of sensors) {
      const mesh = byGid.get(s.ifc_global_id)
      if (!mesh) continue
      mesh.material.color.set(statusColor(s.status))
      const selected = s.ifc_global_id === selectedGid
      // Resalta sin perder el color de estado: brillo propio + borde azul
      mesh.material.emissive.set(selected ? statusColor(s.status) : '#000000')
      mesh.material.emissiveIntensity = selected ? 0.45 : 0
      mesh.scale.setScalar(selected ? 1.25 : 1)
      let edges = mesh.getObjectByName('sel-edges')
      if (selected && !edges) {
        edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(mesh.geometry),
          new THREE.LineBasicMaterial({ color: '#2563eb' }),
        )
        edges.name = 'sel-edges'
        mesh.add(edges)
      } else if (!selected && edges) {
        mesh.remove(edges)
        edges.geometry.dispose()
        edges.material.dispose()
      }
    }
  }, [sensors, selectedGid, geomKey])

  return (
    <div className="relative flex-1 min-h-0">
      <div ref={mountRef} className="absolute inset-0 rounded-b-xl overflow-hidden" />
      {building && !building.is_monitored && (
        <div className="absolute top-2 left-2 right-2 bg-white/90 rounded-md px-2 py-1 text-xs text-slate-600 shadow">
          Edificación de referencia: sin sensores. Consulte sus componentes en el panel COBie.
        </div>
      )}
      <div className="absolute left-2 bottom-2 bg-white/90 rounded-md shadow px-2 py-1.5 text-[11px] space-y-0.5">
        {['optimo', 'alerta', 'critico'].map((s) => (
          <div key={s} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: STATUS[s].color }} />
            {STATUS[s].label}
          </div>
        ))}
        <div className="text-slate-400 pt-0.5">Pórtico paramétrico · clic en elemento</div>
      </div>
    </div>
  )
}
