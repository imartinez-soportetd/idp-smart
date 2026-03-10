import { useState, useCallback, useEffect, useRef } from 'react'
import { useDropzone } from 'react-dropzone'
import axios from 'axios'
import './index.css'

// URL dinámica: funciona desde localhost y desde la IP real del servidor
const API_BASE = `http://${window.location.hostname}:8000`

// Etapas en orden para la barra de progreso
const STAGE_ORDER = ['INICIO','VISION','SCHEMA_LOAD','AGENT','MAPPER','SIMPLIFY','DB_SAVE','COMPLETADO']

const fmtTime = (s) => {
  if (!s && s !== 0) return '—'
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60), rem = s % 60
  return `${m}m ${rem}s`
}

const fileIcon = (name) => {
  const ext = name.split('.').pop().toLowerCase()
  if (['pdf'].includes(ext)) return '📄'
  if (['png','jpg','jpeg','tif','tiff','webp'].includes(ext)) return '🖼️'
  if (['doc','docx'].includes(ext)) return '📝'
  return '📎'
}

// ── Tarjeta de tarea activa ──────────────────────────────────────────────────
function TaskCard({ task, onDismiss }) {
  const [progress, setProgress] = useState(null)
  const intervalRef = useRef(null)

  const poll = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API_BASE}/api/v1/progress/${task.taskId}`)
      setProgress(data)
      if (data.finished) clearInterval(intervalRef.current)
    } catch { /* network hiccup — retrying */ }
  }, [task.taskId])

  useEffect(() => {
    poll()
    intervalRef.current = setInterval(poll, 4000)
    return () => clearInterval(intervalRef.current)
  }, [poll])

  const pct = progress?.progress_pct ?? 0
  const finished = progress?.finished
  const isError = progress?.status === 'ERROR'
  const stageLabel = progress?.stage_label ?? 'Iniciando…'
  const elapsed = progress?.elapsed_seconds
  const remaining = progress?.estimated_remaining_s

  const stageIdx = STAGE_ORDER.indexOf(progress?.stage_current)

  return (
    <div className={`task-card ${finished ? (isError ? 'task-error' : 'task-done') : 'task-active'}`}>
      <div className="task-header">
        <div className="task-meta">
          <span className={`task-badge ${finished ? (isError ? 'badge-error' : 'badge-done') : 'badge-active'}`}>
            {finished ? (isError ? '✗ Error' : '✓ Completado') : '⟳ En proceso'}
          </span>
          <span className="task-label">{task.actLabel}</span>
        </div>
        <div className="task-times">
          {elapsed != null && (
            <span className="time-chip">⏱ {fmtTime(elapsed)}</span>
          )}
          {!finished && remaining != null && (
            <span className="time-chip est">≈ {fmtTime(remaining)} restante</span>
          )}
          {finished && (
            <button onClick={() => onDismiss(task.taskId)} className="btn-dismiss">✕</button>
          )}
        </div>
      </div>

      {/* Barra de progreso */}
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%`, background: isError ? '#ef4444' : undefined }} />
      </div>

      {/* Etapas */}
      <div className="stages-row">
        {STAGE_ORDER.slice(0, -1).map((s, i) => (
          <div key={s} className={`stage-dot ${i < stageIdx ? 'done' : i === stageIdx ? 'active' : 'pending'}`}
               title={s}/>
        ))}
      </div>

      <p className="stage-label-text">{stageLabel}</p>

      <div className="task-footer">
        <code className="task-id">{task.taskId}</code>
        {finished && !isError && (
          <a href={`${API_BASE}/api/v1/simplified/${task.taskId}`}
             target="_blank" rel="noopener noreferrer" className="btn-result">
            Ver resultado →
          </a>
        )}
      </div>
    </div>
  )
}

// ── Componente principal ─────────────────────────────────────────────────────
export default function App() {
  const [files, setFiles]           = useState([])
  const [actTypes, setActTypes]     = useState([])
  const [selectedAct, setSelectedAct] = useState(null)
  const [loadingActs, setLoadingActs] = useState(true)
  const [actError, setActError]     = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [tasks, setTasks]           = useState([])

  // Cargar catálogo de tipos de acto
  useEffect(() => {
    axios.get(`${API_BASE}/api/v1/forms`)
      .then(({ data }) => {
        setActTypes(data.acts || [])
        if (data.acts?.length) setSelectedAct(data.acts[0])
      })
      .catch(() => setActError('No se pudo conectar con la API para obtener los tipos de acto.'))
      .finally(() => setLoadingActs(false))
  }, [])

  // Dropzone
  const onDrop = useCallback((accepted) => {
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...accepted.filter(f => !names.has(f.name))]
    })
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf':  ['.pdf'],
      'image/*':          ['.png','.jpg','.jpeg','.tif','.tiff','.webp'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    multiple: true,
  })

  const removeFile = (name) => setFiles(prev => prev.filter(f => f.name !== name))

  const handleSubmit = async () => {
    if (!selectedAct || files.length === 0) return
    setSubmitting(true)

    // Crear un JSON mock de forma (en producción vendrá de cfdeffrmpre)
    const mockForm = {
      containers: [],
      act_type: selectedAct.dsactocorta,
      form_code: selectedAct.form_code,
    }
    const jsonBlob = new Blob([JSON.stringify(mockForm)], { type: 'application/json' })

    const results = []
    for (const file of files) {
      const fd = new FormData()
      fd.append('act_type',  selectedAct.dsactocorta)
      fd.append('form_code', String(selectedAct.form_code))
      fd.append('json_form', jsonBlob, 'form.json')
      fd.append('document',  file)
      try {
        const { data } = await axios.post(`${API_BASE}/api/v1/process`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        results.push({
          taskId:   data.task_id,
          fileName: file.name,
          actLabel: selectedAct.display_label,
        })
      } catch (err) {
        console.error(`Error enviando ${file.name}:`, err)
      }
    }

    setTasks(prev => [...results, ...prev])
    setFiles([])
    setSubmitting(false)
  }

  const dismissTask = (taskId) => setTasks(prev => prev.filter(t => t.taskId !== taskId))

  const activeTasks = tasks.filter(t => true) // mostramos todas hasta que el usuario descarte

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <div className="logo-group">
          <div className="logo-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
          </div>
          <div>
            <div className="logo-name">idp-smart</div>
            <div className="logo-sub">INTELLIGENT NOTARIAL EXTRACTION</div>
          </div>
        </div>
        <div className="header-right">
          {activeTasks.length > 0 && (
            <span className="tasks-badge">{activeTasks.length} tarea{activeTasks.length > 1 ? 's' : ''} activa{activeTasks.length > 1 ? 's' : ''}</span>
          )}
          <span className="version-chip">Motor IA · v1.0</span>
        </div>
      </header>

      <main className="app-main">
        {/* Hero */}
        <section className="hero">
          <h1 className="hero-title">
            Procesa expedientes con<br/>
            <span className="hero-accent">Inteligencia Artificial</span>
          </h1>
          <p className="hero-sub">
            Sube escrituras, actas o adendas. El motor extrae el contexto semántico y pre-llena automáticamente las formas registrales.
          </p>
          <p className="hero-hint">
            ✅ Puedes enviar múltiples documentos sin esperar — el sistema procesa en paralelo.
          </p>
        </section>

        {/* Panel de upload */}
        <div className="upload-panel">
          {/* Paso 1 */}
          <div className="step">
            <div className="step-label">PASO 1 — TIPO DE ACTO</div>
            {loadingActs ? (
              <div className="loading-pill">⏳ Cargando catálogo…</div>
            ) : actError ? (
              <div className="error-pill">⚠ {actError}</div>
            ) : (
              <div className="select-wrap">
                <select
                  value={String(selectedAct?.form_code ?? '')}
                  onChange={(e) => {
                    const found = actTypes.find(a => String(a.form_code) === e.target.value)
                    setSelectedAct(found ?? null)
                  }}
                  className="act-select"
                >
                  {actTypes.map(act => (
                    <option key={act.form_code} value={String(act.form_code)}>
                      {act.display_label}
                    </option>
                  ))}
                </select>
                {selectedAct && (
                  <p className="act-sub">{selectedAct.dsactocorta} · {selectedAct.dsacto}</p>
                )}
              </div>
            )}
          </div>

          {/* Paso 2 */}
          <div className="step">
            <div className="step-label">PASO 2 — DOCUMENTOS Y ADENDAS</div>
            <div {...getRootProps()} className={`dropzone ${isDragActive ? 'dz-active' : ''}`}>
              <input {...getInputProps()} />
              <svg className="dz-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <polyline points="16 16 12 12 8 16"/>
                <line x1="12" y1="12" x2="12" y2="21"/>
                <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
              </svg>
              <p className="dz-main"><span className="dz-link">Haz clic</span> o arrastra los archivos aquí</p>
              <p className="dz-types">PDF · Imágenes (PNG, JPG) · Office (DOC, DOCX)</p>
              <p className="dz-note">Los archivos no-PDF serán convertidos automáticamente antes de procesarse</p>
            </div>

            {files.length > 0 && (
              <div className="file-list">
                <div className="file-list-header">ARCHIVOS SELECCIONADOS ({files.length})</div>
                {files.map(f => (
                  <div key={f.name} className="file-row">
                    <span className="file-icon">{fileIcon(f.name)}</span>
                    <div className="file-info">
                      <span className="file-name">{f.name}</span>
                      <span className="file-size">{(f.size / 1024 / 1024).toFixed(2)} MB</span>
                    </div>
                    <button onClick={() => removeFile(f.name)} className="file-remove">✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Botón */}
          <div className="submit-row">
            <p className="submit-hint">
              {tasks.length > 0
                ? `✅ ${tasks.length} envío(s) en proceso — puedes enviar más sin esperar.`
                : 'Selecciona el tipo de acto y adjunta los documentos para comenzar.'}
            </p>
            <button
              onClick={handleSubmit}
              disabled={!selectedAct || files.length === 0 || submitting}
              className="btn-submit"
            >
              {submitting ? '⟳ Enviando…' : `Iniciar Extracción${files.length > 1 ? ` (${files.length} archivos)` : ''}`}
            </button>
          </div>
        </div>

        {/* Panel de tareas activas */}
        {tasks.length > 0 && (
          <div className="tasks-panel">
            <div className="tasks-panel-header">
              <h2 className="tasks-title">Tareas de Extracción</h2>
              <p className="tasks-sub">El sistema procesa en paralelo. Puedes enviar más documentos mientras estas tareas continúan.</p>
            </div>
            <div className="tasks-list">
              {tasks.map(t => (
                <TaskCard key={t.taskId} task={t} onDismiss={dismissTask} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
