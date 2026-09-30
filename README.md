# nortiqa-dev-agent

Agente de desarrollo de código controlado desde Telegram, corriendo en una notebook
HP Victus (WSL2). Su objetivo: que una persona **sin conocimientos de comandos** pueda
pedirle tareas de programación en lenguaje natural y el agente las resuelva de forma
segura, eligiendo solo entre una IA local (barata/rápida) y Claude Code (potente).

Este repo es un **espejo acotado y público** del agente, publicado para que un revisor
externo (ChatGPT) pueda diseñar una batería de pruebas escalonadas. **No** contiene la
infraestructura del bot (SSH, dominios, redes sociales) ni secreto alguno: el token y el
`chat_id` de Telegram se leen de archivos fuera del repo (`~/.nortiqa-bot/`).

---

## Cómo funciona (`engine.py`)

El agente tiene **dos motores** y elige uno automáticamente con una heurística instantánea:

| Motor | Modelo | Para qué | Costo |
|---|---|---|---|
| ⚡ `local` | `qwen2.5-coder:7b` vía Ollama (RTX 4050, 6 GB VRAM) | Tareas acotadas de **un solo archivo** | Gratis, ~10–40 s |
| 🧠 `claude_code` | Claude Code headless (`--dangerously-skip-permissions`) | Multi-archivo, debug, ops, refactor, configuración | Consume API |

### Flujo (`run_task`)
1. `prepare(repo)` — valida la lista blanca, inicializa git si hace falta y crea una **rama nueva** `bot/<timestamp>`.
2. `recommend_engine(task)` — heurística por palabras clave (ver abajo) elige el motor si no se forzó.
3. Corre el motor:
   - `run_local_single_file` — le pasa al modelo la tarea + el contenido actual del archivo objetivo (default `solucion.py`) y **reescribe el archivo completo** con la respuesta.
   - `run_claude_code` — ejecuta Claude Code headless dentro del repo, en la rama ya creada.
4. Devuelve el `diff` (staged) para que el dueño lo apruebe **desde Telegram** con botones ✅ Aplicar / 🗑️ Descartar.

### Barreras de seguridad (guardrails)
- **Lista blanca de repos**: solo `~/workspaces/sandbox` (`ALLOWED_ROOTS`). Fuera de ahí, `PermissionError`.
- **Rama nueva por tarea**: nunca trabaja sobre `main`.
- **Nunca commitea**: deja los cambios en el árbol; el commit lo dispara el dueño tras ver el diff.
- Owner-only en la capa de Telegram (un solo `chat_id` autorizado).

### Heurística de selección de motor (`recommend_engine`)
- Pistas → **Claude Code**: `arregl, refactor, proyecto, instal, configur, bug, falla, error, depura, debug, migra, varios archivos, el repo, docker, deploy, pipeline, test suite, toda la, todo el`.
- Pistas → **Local**: `una función, un archivo, un test, un script, boilerplate, agregá un, escribí una, creá un archivo`.
- Ambiguo → **Claude Code** ("por las dudas el motor potente").

---

## Estado de las pruebas ya corridas (evidencia real)

**Dos** pruebas ejecutadas de punta a punta desde Telegram contra el motor **⚡ local**, y una tercera (comparación con 🧠 Claude) todavía **pendiente**:

| # | Tarea | Resultado | Veredicto |
|---|---|---|---|
| 1 | "función que reciba una lista y devuelva el promedio, ignorando los que no sean números" | Correcta en lógica, **pero pisó una función `validar_cuit` preexistente** (reescribió todo el archivo) | ⚠️ Parcial |
| 2 | Igual, pero "**sin borrar las funciones que ya existen**" y "**ignorando booleanos**" | **Respetó** `validar_cuit` y agregó la nueva ✅, **pero no descartó booleanos** (`isinstance(True, int)` es `True` en Python) | ⚠️ Parcial |
| 3 | (pendiente) misma tarea forzando 🧠 Claude Code, para comparar | — | — |

### Limitaciones ya detectadas del motor local
1. **Reescribe el archivo entero** en cada tarea de "un archivo" → riesgo de pisar código si el archivo ya tiene contenido y no se lo aclara.
2. **Casos borde sutiles** se le escapan (ej. `bool ⊂ int` en Python).
3. Solo maneja **un archivo**; cualquier cosa multi-archivo debe ir a Claude Code.

---

## Objetivo de la revisión externa

Diseñar una **batería de pruebas escalonadas (de menor a mayor dificultad)** que:
- Construya **herramientas útiles reales** (no ejercicios de juguete) que el dueño pueda usar.
- Mida con precisión **hasta dónde llega la autonomía y la calidad** de cada motor.
- Defina, para cada nivel, un **criterio objetivo de aprobado/reprobado** (tests, salidas esperadas).
- Identifique **en qué nivel** conviene que el agente escale solo de ⚡ local a 🧠 Claude.

Ver `PLAN-DE-PRUEBAS.md` para la plantilla que el revisor debe completar.
