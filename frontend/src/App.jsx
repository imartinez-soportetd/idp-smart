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
          {progress?.is_waiting && !finished && (
            <span className="time-chip waiting">⏳ Esperando worker…</span>
          )}
          {!progress?.is_waiting && elapsed != null && (
            <span className="time-chip" title={finished ? "Tiempo total" : "Tiempo transcurrido"}>
              ⏱ {fmtTime(elapsed)}
            </span>
          )}
          {!finished && !progress?.is_waiting && remaining != null && (
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

// ── Componente de Historial ──────────────────────────────────────────────────
function HistoryView({ onNavigateBack, onShowProgress }) {
  const [extractions, setExtractions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reprocessing, setReprocessing] = useState({})
  const [deleting, setDeleting] = useState({})

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const { data } = await axios.get(`${API_BASE}/api/v1/extractions`)
      setExtractions(data.extractions || [])
    } catch (err) {
      console.error('History Error:', err)
      setError(`Error: ${err.message || 'No se pudo conectar con la API'}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  const handleReprocess = async (taskId, skipVision = false) => {
    try {
      setReprocessing(prev => ({ ...prev, [taskId]: true }))
      await axios.post(`${API_BASE}/api/v1/reprocess/${taskId}?skip_vision=${skipVision}`)
      setTimeout(fetchHistory, 1500)
    } catch (err) {
      alert(`Error al solicitar re-proceso: ${err.message}`)
    } finally {
      setReprocessing(prev => ({ ...prev, [taskId]: false }))
    }
  }

  const handleDelete = async (taskId) => {
    if (!window.confirm('¿Estás seguro de eliminar este registro del historial?')) return
    try {
      setDeleting(prev => ({ ...prev, [taskId]: true }))
      await axios.delete(`${API_BASE}/api/v1/extractions/${taskId}`)
      setExtractions(prev => prev.filter(ex => ex.task_id !== taskId))
    } catch (err) {
      alert(`Error al eliminar: ${err.message}`)
    } finally {
      setDeleting(prev => ({ ...prev, [taskId]: false }))
    }
  }

  if (loading) return <div className="loading-state">⏳ Cargando historial de extracciones...</div>

  return (
    <div className="history-container">
      <div className="history-header">
        <button onClick={onNavigateBack} className="btn-back">← Volver al inicio</button>
        <h2 className="history-title">Historial de Procesos</h2>
      </div>

      {error && (
        <div className="error-pill" style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
          <span>⚠ {error}</span>
          <button onClick={fetchHistory} className="btn-action-small">⟳</button>
        </div>
      )}

      <div className="history-table-wrap">
        <table className="history-table">
          <thead>
            <tr>
              <th>ID de Tarea</th>
              <th>Acto</th>
              <th>Documento</th>
              <th>Estado / Etapa</th>
              <th>Fecha</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {extractions.map(ex => (
              <tr key={ex.task_id}>
                <td><code className="task-id-small">{ex.task_id?.substring(0,8)}...</code></td>
                <td><span className="badge-gray">{ex.act_type || '—'}</span></td>
                <td className="file-cell" title={ex.pdf_minio_path}>
                   {ex.pdf_minio_path?.split('/').pop() || '—'}
                </td>
                <td>
                  <span className={`status-chip ${(ex.status || 'unknown').toLowerCase()}`}>
                    {ex.stage_current || ex.status || 'En cola'}
                  </span>
                </td>
                <td>{ex.created_at ? ex.created_at.split('.')[0] : '—'}</td>
                <td className="actions-cell">
                   <div className="action-buttons">
                      <button 
                        onClick={() => onShowProgress(ex.task_id, ex.act_type)}
                        className="btn-action-small progress"
                        title="Ver detalle del progreso"
                      >
                        📊
                      </button>
                      <button 
                        onClick={() => handleReprocess(ex.task_id, true)}
                        disabled={reprocessing[ex.task_id]}
                        className="btn-action-small"
                        title="Re-procesar solo IA"
                      >
                        IA
                      </button>
                      <button 
                        onClick={() => handleReprocess(ex.task_id, false)}
                        disabled={reprocessing[ex.task_id]}
                        className="btn-action-small"
                        title="Re-procesar todo"
                      >
                        🔄
                      </button>
                      <button 
                        onClick={() => handleDelete(ex.task_id)}
                        disabled={deleting[ex.task_id]}
                        className="btn-action-small delete"
                        title="Eliminar registro"
                      >
                        🗑️
                      </button>
                      {(ex.status === 'COMPLETED' || ex.status === 'COMPLETADO') && (
                        <>
                          <a href={`${API_BASE}/api/v1/simplified/${ex.task_id}`} target="_blank" className="btn-action-small view" title="Ver JSON Simplificado">S</a>
                          <a href={`${API_BASE}/api/v1/full/${ex.task_id}`} target="_blank" className="btn-action-small view full" title="Ver JSON Completo (Java)">F</a>
                        </>
                      )}
                   </div>
                </td>
              </tr>
            ))}
            {extractions.length === 0 && (
              <tr><td colSpan="6" className="empty-row">No se encontraron extracciones.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Componente principal ─────────────────────────────────────────────────────
export default function App() {
  const [view, setView]             = useState('home') // 'home' | 'history'
  const [files, setFiles]           = useState([])
  const [actTypes, setActTypes]     = useState([])
  const [selectedAct, setSelectedAct] = useState(null)
  const [loadingActs, setLoadingActs] = useState(true)
  const [actError, setActError]     = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [tasks, setTasks]           = useState([])

  const showProgress = (taskId, actLabel) => {
    // Si la tarea ya está en la lista de monitoreo, no la duplicamos
    if (!tasks.some(t => t.taskId === taskId)) {
      setTasks(prev => [{ taskId, actLabel: actLabel || 'Extracción manual' }, ...prev])
    }
  }

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

    // Obtener la configuración real de la forma desde el catálogo (antes era un mock vacío)
    const formSchema = selectedAct.jsconfforma || { containers: [] }
    
    // Aseguramos que el act_type y form_code coincidan con lo seleccionado
    const jsonToUpload = {
      ...formSchema,
      act_type: selectedAct.dsactocorta,
      form_code: selectedAct.form_code,
    }
    
    const jsonBlob = new Blob([JSON.stringify(jsonToUpload)], { type: 'application/json' })

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
          <div onClick={() => setView('home')} style={{cursor:'pointer'}}>
            <div className="logo-name">idp-smart</div>
            <div className="logo-sub">INTELLIGENT NOTARIAL EXTRACTION</div>
          </div>
        </div>
        <div className="header-right">
          <button onClick={() => setView(view === 'home' ? 'history' : 'home')} className="btn-nav">
            {view === 'home' ? '📜 Historial' : '🏠 Nueva Extracción'}
          </button>
          {activeTasks.length > 0 && (
            <span className="tasks-badge">{activeTasks.length} activa{activeTasks.length > 1 ? 's' : ''}</span>
          )}
          <span className="version-chip">IA v1.0</span>
        </div>
      </header>

      <main className="app-main">
        {view === 'history' ? (
          <HistoryView onNavigateBack={() => setView('home')} onShowProgress={showProgress} />
        ) : (
          <>
            {/* Hero */}
            <section className="hero">
              <h1 className="hero-title">
                Procesa expedientes con<br/>
                <span className="hero-accent">Inteligencia Artificial</span>
              </h1>
              <p className="hero-sub">
                Sube escrituras, actas o adendas. El motor extrae el contexto semántico y pre-llena automáticamente las formas registrales.
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
                  <p className="dz-types">PDF · PNG · JPG · DOCX</p>
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
                <button
                  onClick={handleSubmit}
                  disabled={!selectedAct || files.length === 0 || submitting}
                  className="btn-submit"
                >
                  {submitting ? '⟳ Enviando…' : `Iniciar Extracción${files.length > 1 ? ` (${files.length})` : ''}`}
                </button>
              </div>
            </div>

            {/* Panel de tareas activas */}
            {tasks.length > 0 && (
              <div className="tasks-panel">
                <div className="tasks-panel-header">
                  <h2 className="tasks-title">Tareas de Extracción</h2>
                </div>
                <div className="tasks-list">
                  {tasks.map(t => (
                    <TaskCard key={t.taskId} task={t} onDismiss={dismissTask} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
