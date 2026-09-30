# Plan de pruebas escalonadas — plantilla a completar por el revisor

El objetivo es medir, nivel por nivel, la **autonomía** y la **calidad** del agente, y que
cada prueba deje una **herramienta útil real** para el dueño (un desarrollador que opera
todo desde Telegram, en español).

Reglas para el diseño de las pruebas:
- Cada nivel debe tener un **criterio de aprobado objetivo** (tests unitarios, salida esperada, o comando de verificación).
- Cada tarea se enuncia como se la mandaría el dueño **en lenguaje natural** (español rioplatense), tal como la escribiría en Telegram.
- Indicar el **motor esperado** (⚡ local / 🧠 Claude) y si la heurística actual lo elegiría bien.
- Respetar las barreras: repos bajo `~/workspaces/sandbox`, una rama por tarea, sin commits automáticos.

## Niveles sugeridos (a refinar por el revisor)

### Nivel 0 — Sanidad (un archivo, sin bordes)
- Meta: confirmar el pipeline. Motor: ⚡ local.
- (completar tareas + criterio de aprobado)

### Nivel 1 — Un archivo con casos borde
- Meta: medir si el local maneja validaciones finas (tipos, vacíos, unicode, negativos).
- (completar)

### Nivel 2 — Un archivo + sus tests
- Meta: que genere código **y** pruebas que pasen (`python -m unittest`).
- (completar)

### Nivel 3 — Multi-archivo (módulo + CLI)
- Meta: primera herramienta real usable. Motor esperado: 🧠 Claude.
- (completar)

### Nivel 4 — Arreglar/refactorizar código existente
- Meta: dar un repo con un bug y medir si lo diagnostica y corrige sin romper lo demás.
- (completar)

### Nivel 5 — Herramienta con dependencias / entorno
- Meta: instalar y dejar funcionando algo con venv (como ya hizo con Aider).
- (completar)

### Nivel 6 — Autonomía real de varios pasos
- Meta: tarea ambigua que exige planificar, ejecutar y verificar sin intervención.
- (completar)

## Tabla de resultados (a llenar mientras se corre)

| Nivel | Tarea | Motor usado | Tiempo | Aprobó criterio | Observaciones |
|---|---|---|---|---|---|
| | | | | | |
