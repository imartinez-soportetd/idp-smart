# Guía de Troubleshooting: Extracción Incompleta o NULL

## 🔍 Problemas Reportados y Soluciones

### Problema 1: `simplified_json` Retorna NULL

**Síntomas:**
```json
{
  "task_id": "...",
  "status": "COMPLETED",
  "message": "El JSON simplificado aún no está disponible.",
  "simplified_json": null
}
```

**Causas Posibles y Soluciones:**

| Causa | Síntoma | Solución |
|-------|---------|----------|
| JSON malformado del LLM | `extracted_data` está vacío | Revisar logs: "No se encontró bloque JSON" |
| Documento sin información | Extracción encuentra 0 campos | Verificar que documento contiene datos del formulario |
| LLM cortó la respuesta | JSON incompleto/truncado | Sistema intenta reparar automáticamente |
| Esquema UUID no coincide | UUID en documento ≠ UUID en esquema | Validar UUIDs del formulario |

**Debugging:**
```bash
# Ver logs detallados del worker
docker logs idp_worker | grep -i "error\|failed\|uuid"

# Verificar que el documento se cargó correctamente
docker exec idp_api curl http://localhost:9000/minio-console

# Re-procesar con logs verbosos
# (requiere codigo modificado)
```

---

### Problema 2: Solo 1 Solicitante Extraído (Debería ser 3)

**Síntoma:**
```json
"Generales del Solicitante": [
  {
    "uuid-solicitante-nombre": "ALMA DELIA",
    ...
  }
  // Falta PEDRO UBALDO Y VALERIA CONCEPCIÓN
]
```

**Causa Raíz:**
El LLM solo extrajo la primera instancia. Esto ocurre cuando el template de extracción NO instruye explícitamente a buscar TODAS las instancias.

**Solución:**
✅ IMPLEMENTADA en nueva versión: El template ahora incluye explícitamente:
- "Si hay 3 solicitantes, TODOS deben extraerse"
- "Arrays SIEMPRE para campos repetibles"
- "Si hay múltiples instancias, retorna un ARRAY, no un objeto único"

---

### Problema 3: Titulares con Porcentajes Incompletos

**Síntoma:**
```json
"container-titulares": [
  {
    "uuid-titular-nombre": "ALMA DELIA",
    "uuid-titular-porcentaje": 20
    // ⚠️ Otros titulares no tienen sus porcentajes (50%, 30%)
  }
]
```

**Causa Raíz:**
1. LLM no buscó suficientemente profundo en el documento
2. Porcentajes podrían estar en párrafos de "copropiedad" separados
3. El formato del documento no es evidente (ej: "ALMA DELIA (20%)" vs párrafo aparte)

**Solución:**
El template mejorado ahora incluye:
- "Busca en párrafos de 'copropiedad' o 'dominio'"
- "Suma de porcentajes: si hay 3 titulares, sus % deben sumar 100%"
- "Si faltan datos, BUSCA MÁS PROFUNDAMENTE"

---

### Problema 4: Datos Separados Correctamente por UUID

**Estado Esperado (CORRECTO):**
```json
{
  "uuid-notario-nombre": "VICTOR MANUEL SANTIN CORAL",
  "uuid-notario-estado": "QUINTANA ROO",
  "uuid-notario-notaria": "24",
  "uuid-notario-municipio": "SOLIDARIDAD",
  "uuid-notario-num": "24"
}
```

**Verificación:**
- ✅ Cada campo es un UUID diferente
- ✅ Cada UUID tiene su propio valor
- ✅ No hay mezclas (ej: "VICTOR MANUEL, QUINTANA ROO" en un solo UUID)

**Si ves esto (INCORRECTO):**
```json
{
  "uuid-notario": "VICTOR MANUEL, QUINTANA ROO, NOTARÍA 24..."
}
```
→ El template del LLM necesitaba ser más explícito (✅ ARREGLADO)

---

## 🔧 Validación del Esquema (act_forms_catalog)

Antes de procesar, verifica que tu formulario tenga:

### 1. UUIDs Únicos
```json
❌ MALO: UUID duplicado
{
  "uuid": "abc123",
  "label": "Nombre"
},
{
  "uuid": "abc123",  // ⚠️ DUPLICADO
  "label": "Apellido"
}

✅ CORRECTO: UUIDs únicos
{
  "uuid": "uuid-nombre-001",
  "label": "Nombre"
},
{
  "uuid": "uuid-apellido-001",
  "label": "Apellido"
}
```

### 2. Flag `repetitiva` para Contenedores Repetibles
```json
❌ MALO: Sin marcar repetitiva
{
  "uuid": "container-solicitantes",
  "label": "Solicitantes"
  // Falta "repetitiva": true
}
// → Resultado: Solo extrae 1 solicitante

✅ CORRECTO: Marcado como repetitiva
{
  "uuid": "container-solicitantes",
  "label": "Solicitantes",
  "repetitiva": true
  // → Resultado: Extrae TODOS los solicitantes como array
}
```

### 3. Estructura Consistente
```json
✅ Cada contenedor debe tener:
{
  "uuid": "...",
  "label": "...",
  "repetitiva": true|false,
  "controls": [
    { "uuid": "...", "label": "...", "type": "..." },
    { "uuid": "...", "label": "...", "type": "..." }
  ]
}
```

---

## 🚀 Mejoras Implementadas

### Template de Extracción (agent.py)
- ✅ Instrucción explícita: "Si hay 3 solicitantes, TODOS deben extraerse"
- ✅ Estructura clara de retorno: uuid → value pairs
- ✅ Validación lógica: "Suma de porcentajes: sus % deben sumar 100%"
- ✅ Búsqueda profunda: "Si faltan datos, BUSCA MÁS PROFUNDAMENTE"

### Función create_simplified_json() (agent.py)
- ✅ NUNCA retorna null (garantizado dict válido)
- ✅ Transforma uuid → label automáticamente
- ✅ Preserva arrays y datos repetibles

### Mapper (mapper.py)
- ✅ Respeta estructura exacta del esquema
- ✅ Solo inyecta valores, no modifica forma
- ✅ Manejo simple y robusto de clonación

---

## 📞 Debugging - Si Aún Tienes Problemas

```bash
# 1. Verificar logs del worker
docker logs idp_worker --tail=100

# 2. Procesar manualmente un documento simple
# Subir un PDF de prueba al /v1/process endpoint

# 3. Revisar la respuesta raw del LLM
# (buscar en logs el texto antes del JSON parsing)

# 4. Si JSON está cortado/truncado
# Sistema intenta reparar, pero si falla:
grep "JSON reparado\|fallido" docker logs

# 5. Validar esquema en act_forms_catalog
# Verificar que form_code existe y tiene UUIDs válidos
```

---

## ✅ Checklist Pre-Producción

- [ ] Todos los UUIDs en el esquema son únicos
- [ ] Campos repetibles tienen `repetitiva: true`
- [ ] campos simples tienen `repetitiva: false` (o no incluyen la clave)
- [ ] Documento test contiene todos los datos esperados
- [ ] Primer test retorna `simplified_json` válido (no null)
- [ ] Números de solicitantes/titulares coinciden entre documento y resultado
- [ ] Porcentajes suman 100% (si aplica)
- [ ] Fechas están en formato YYYY-MM-DD
- [ ] Montos sin $ ni comas (ej: 41540)

---

## 📝 Nota Sobre Estructura de Datos

idp-smart funciona con:
- **UUID/Value Pairs:** Estructura interna (lo que retorna `extract_form_data()`)
- **Label/Value Pairs:** Presentación humanizada (lo que ves en `simplified_json`)

Ambas son correctas. La conversión ocurre automáticamente en `create_simplified_json()`.

