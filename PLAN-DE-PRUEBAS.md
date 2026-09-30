# Plan de pruebas escalonadas — Nortiqa Dev Agent

## Objetivo

Medir, de forma progresiva y reproducible, el **techo de autonomía, calidad y selección de motor** de `nortiqa-dev-agent`.

Cada nivel debe dejar una **herramienta útil real** para un desarrollador que opera desde Telegram y no quiere usar comandos complejos.

La batería está diseñada para comprobar cuatro cosas distintas:

1. Si el pipeline Telegram → agente → rama → diff funciona correctamente.
2. Hasta dónde puede llegar ⚡ `local` (`qwen2.5-coder:7b`) sin degradar calidad.
3. Si `recommend_engine()` detecta correctamente cuándo debe escalar a 🧠 `claude_code`.
4. Hasta dónde Claude Code puede resolver tareas ambiguas de varios pasos sin intervención humana.

---

# 1. Condiciones de prueba

Todas las pruebas deben respetar las barreras reales del agente:

- repositorios únicamente bajo `~/workspaces/sandbox`;
- una rama `bot/<timestamp>` nueva por tarea;
- nunca trabajar directamente sobre `main`;
- nunca hacer commit automático;
- el resultado debe quedar como cambios staged para revisión;
- el motor local puede editar **un solo archivo**;
- el motor local recibe el contenido actual y después **reescribe el archivo completo**;
- Claude Code puede leer, editar y ejecutar varios archivos.

Para evitar contaminación entre pruebas se recomienda usar un repo independiente por nivel:

```text
~/workspaces/sandbox/nivel-00
~/workspaces/sandbox/nivel-01
~/workspaces/sandbox/nivel-02
~/workspaces/sandbox/nivel-03
~/workspaces/sandbox/nivel-04
~/workspaces/sandbox/nivel-05
~/workspaces/sandbox/nivel-06
```

Cada nivel se considera aprobado solamente si cumple su **criterio objetivo**, no porque el resultado "parezca correcto".

---

# 2. Escala esperada

| Nivel | Dificultad | Motor correcto | Qué buscamos |
|---|---|---|---|
| 0 | Un archivo, lógica simple | ⚡ Local | Sanidad del pipeline |
| 1 | Un archivo, casos borde sutiles | ⚡ Local | Techo de calidad local |
| 2 | Dos archivos relacionados | 🧠 Claude | Detectar límite estructural + fallo de heurística |
| 3 | Herramienta multiarchivo | 🧠 Claude | Diseño y coordinación |
| 4 | Diagnóstico de código existente | 🧠 Claude | Debug sin regresiones |
| 5 | Dependencias + entorno | 🧠 Claude | Manejo del entorno |
| 6 | Pedido ambiguo y multi-paso | 🧠 Claude | Autonomía real |

---

# Nivel 0 — Sanidad

## Objetivo

Confirmar que el circuito básico funciona:

```text
Telegram
→ recommend_engine
→ motor local
→ archivo
→ rama nueva
→ staged diff
→ revisión humana
```

No se busca todavía complejidad algorítmica.

## Herramienta

Contador rápido de líneas de un archivo.

Es una utilidad mínima pero real para inspeccionar archivos desde terminal.

| Campo | Definición |
|---|---|
| **Mensaje exacto de Telegram** | `Creá un script que reciba la ruta de un archivo y me diga cuántas líneas tiene. Quiero usarlo así: python solucion.py archivo.txt. Si está bien, que imprima solamente el número.` |
| **Motor esperado** | ⚡ Local |
| **Heurística actual** | ✅ Acierta. Detecta `un script`. |
| **Capacidad medida** | Generación simple de un archivo, interpretación de requisitos y funcionamiento básico del pipeline. |
| **Riesgo buscado** | Ninguno especial. Es la prueba de control. |

### Verificación

```bash
printf 'uno\ndos\ntres\n' > muestra.txt
python solucion.py muestra.txt
```

Salida exacta:

```text
3
```

### Aprobado

```text
PASS si:
- solucion.py existe;
- ejecuta sin traceback;
- devuelve exactamente 3;
- el trabajo quedó en una rama bot/*;
- no hubo commit automático.
```

Si falla este nivel, no continuar: el problema es infraestructura o ejecución básica, no inteligencia.

---

# Nivel 1 — Un archivo con casos borde reales

## Objetivo

Encontrar el primer límite de **calidad** del motor local.

Esta prueba apunta deliberadamente a una debilidad ya observada: en Python `bool` hereda de `int`, por lo que una implementación superficial puede interpretar `True` como `1`.

## Herramienta

Resumen de tiempos de ejecución guardados en JSON.

Es útil para analizar tiempos de builds, scripts, jobs o tareas automáticas.

| Campo | Definición |
|---|---|
| **Mensaje exacto de Telegram** | `Creá un script que lea un JSON con una lista de tiempos y me muestre cuántos tiempos válidos hay y el promedio. Contá enteros y decimales, también negativos, pero ignorá texto, null y booleanos. Quiero usarlo con python solucion.py tiempos.json.` |
| **Motor esperado** | ⚡ Local |
| **Heurística actual** | ✅ Acierta. Detecta `un script`. |
| **Capacidad medida** | Casos borde, tipos Python, validación fina y precisión semántica. |
| **Fallo buscado** | Tratar `true` como número por `isinstance(True, int) == True`. |

### Fixture

```bash
cat > tiempos.json <<'EOF'
[12, 15.5, true, "20", null, -2]
EOF
```

Los únicos valores válidos son:

```text
12
15.5
-2
```

Resultado:

```text
cantidad = 3
promedio = 8.5
```

### Verificación

```bash
python solucion.py tiempos.json
```

Debe producir información equivalente a:

```text
cantidad: 3
promedio: 8.5
```

Puede variar el formato, pero no los valores.

### Aprobado

PASS solamente si:

```text
cantidad == 3
promedio == 8.5
```

## Predicción

**Este es el primer nivel donde se predice un fallo del motor local.**

Probabilidad principal:

```python
isinstance(valor, (int, float))
```

incluye accidentalmente:

```python
True
False
```

La prueba anterior del agente ya mostró exactamente esta clase de error conceptual.

Por lo tanto:

> Nivel 1 = primer techo esperado de CALIDAD del motor local.

Si lo supera, es evidencia nueva de mejora, no motivo para eliminar el nivel.

---

# Nivel 2 — Código + test en archivos separados

## Objetivo

Encontrar el límite **estructural** del motor local y, al mismo tiempo, probar la heurística.

La tarea requiere dos archivos relacionados.

## Herramienta

Resumen de cambios staged de Git para poder revisar desde Telegram cuánto se modificó antes de aprobar.

Debe existir:

```text
diff_resumen.py
test_diff_resumen.py
```

`diff_resumen.py` debe poder interpretar la salida de:

```bash
git diff --cached --numstat
```

y calcular:

```text
archivos
líneas agregadas
líneas eliminadas
```

| Campo | Definición |
|---|---|
| **Mensaje exacto de Telegram** | `Creá un script diff_resumen.py que me resuma los cambios que tengo preparados en git: cantidad de archivos, líneas agregadas y líneas borradas. Agregá un test test_diff_resumen.py que compruebe el cálculo con varios archivos.` |
| **Motor correcto** | 🧠 Claude |
| **Heurística actual** | ❌ Probable fallo. `un script` y `un test` son pistas explícitas de Local y el mensaje no contiene ninguna pista fuerte de Claude. |
| **Capacidad medida** | Multiarchivo, relación implementación/tests y selección correcta de motor. |
| **Fallo buscado** | El local solo puede producir/reemplazar un archivo. |

### Verificación estructural

```bash
test -f diff_resumen.py
test -f test_diff_resumen.py
python -m unittest -v
```

### Caso mínimo que debe cubrir el test

Entrada equivalente:

```text
10	2	app.py
5	0	utils.py
1	4	test_app.py
```

Resultado:

```text
archivos = 3
agregadas = 16
eliminadas = 6
```

### Aprobado

PASS si:

```text
- existen ambos archivos;
- python -m unittest -v termina con exit code 0;
- el cálculo devuelve 3 / 16 / 6.
```

## Predicción

Si la heurística selecciona ⚡ Local:

> **debe considerarse fallo del router aunque el código que genere sea bueno.**

El motor local no tiene capacidad para satisfacer el contrato porque `run_local_single_file()` escribe un único target.

Este es el:

> **primer techo estructural garantizado del motor local.**

### Conclusión esperada de este nivel

La heurística debería incorporar una regla previa a las keywords:

```text
si el pedido implica crear/modificar más de un archivo
→ Claude
```

---

# Nivel 3 — Herramienta multiarchivo usable

## Objetivo

Validar que Claude Code puede transformar un pedido de producto pequeño en una estructura coherente de varios archivos.

## Herramienta

`repo_guard`: chequeo rápido de seguridad Git antes de aprobar cambios desde Telegram.

Debe informar como mínimo:

- rama actual;
- si existen cambios sin guardar;
- cantidad de archivos staged;
- si un `.env` está siendo trackeado por Git;
- resultado general OK / ALERTA.

La arquitectura queda a criterio del agente.

| Campo | Definición |
|---|---|
| **Mensaje exacto de Telegram** | `Armame en este proyecto una herramienta repo_guard para revisar rápido un repo antes de aprobar cambios. Quiero que me diga la rama, si hay cambios pendientes, cuántos archivos tengo preparados y que me avise si por error estoy trackeando un .env. Dejala cómoda para correr con un solo comando y con tests.` |
| **Motor esperado** | 🧠 Claude |
| **Heurística actual** | ✅ Acierta. `proyecto` activa Claude. |
| **Capacidad medida** | Multiarchivo, diseño de CLI, tests, subprocess/Git y organización del código. |

### Verificación

```bash
python -m unittest -v
```

Debe terminar:

```text
OK
```

Después:

```bash
python repo_guard.py
```

o el comando equivalente documentado por el agente.

Debe informar la rama actual.

### Test de seguridad

Crear temporalmente un `.env` trackeado:

```bash
echo 'FAKE_SECRET=123' > .env
git add -f .env
```

Ejecutar nuevamente `repo_guard`.

Debe producir una advertencia inequívoca sobre `.env`.

### Aprobado

PASS si:

```text
- los tests pasan;
- detecta rama;
- detecta staged files;
- detecta un .env trackeado;
- no modifica el repo mientras lo inspecciona.
```

---

# Nivel 4 — Diagnóstico y reparación de un bug existente

## Objetivo

Medir si Claude puede:

```text
observar síntomas
→ localizar causa
→ corregirla
→ conservar comportamiento existente
→ ejecutar regresión
```

No se le debe indicar dónde está el bug.

## Herramienta

Sanitizador de logs que elimina secretos antes de pegar logs en Telegram o enviarlos a una IA.

El fixture del nivel debe contener una implementación existente y tests, con al menos un bug intencional.

Casos que debe proteger:

```text
TOKEN
PASSWORD
SECRET
API_KEY
```

sin destruir datos inocuos.

| Campo | Definición |
|---|---|
| **Mensaje exacto de Telegram** | `Arreglá el sanitizador de logs de este repo. Hay casos donde todavía deja pasar secretos. Fijate qué está mal, corregilo y comprobá que no rompa lo que ya funcionaba.` |
| **Motor esperado** | 🧠 Claude |
| **Heurística actual** | ✅ Acierta. `arreglá` activa Claude. |
| **Capacidad medida** | Diagnóstico, lectura de código existente, debug, regresión y cambios mínimos. |

### Casos obligatorios

Por ejemplo:

```text
TOKEN=abc123
password=hunter2
API_KEY=abc=def=ghi
DEBUG=true
```

La salida no puede contener:

```text
abc123
hunter2
abc=def=ghi
```

pero debe conservar:

```text
DEBUG=true
```

### Verificación

```bash
python -m unittest -v
```

Debe finalizar:

```text
OK
```

Además:

```bash
grep -R "abc123\|hunter2\|abc=def=ghi" salida.log
```

debe devolver cero coincidencias en el resultado sanitizado de prueba.

### Aprobado

PASS si:

```text
- identifica el bug sin recibir la ubicación;
- corrige todos los casos;
- pasan los tests preexistentes;
- no elimina funcionalidades no relacionadas.
```

---

# Nivel 5 — Dependencias y entorno

## Objetivo

Comprobar que el agente puede manejar correctamente:

```text
código
+ dependencia externa
+ entorno virtual
+ instalación
+ ejecución
+ documentación mínima
```

## Herramienta

Inspector simple de workflows YAML.

Debe recibir un archivo YAML de GitHub Actions y listar los nombres de los jobs definidos.

Puede utilizar `PyYAML`.

| Campo | Definición |
|---|---|
| **Mensaje exacto de Telegram** | `Necesito una herramienta para pasarle un workflow YAML de GitHub Actions y que me liste los jobs que tiene. Usá una librería de YAML confiable, instalá lo necesario dentro de un venv del proyecto y dejame un comando simple para usarla.` |
| **Motor esperado** | 🧠 Claude |
| **Heurística actual** | ✅ Acierta. `instalá` activa Claude. |
| **Capacidad medida** | Dependencias, entorno virtual, estructura del proyecto y prueba end-to-end. |

### Fixture

```bash
cat > ejemplo.yml <<'EOF'
name: CI

on:
  push:

jobs:
  test:
    runs-on: ubuntu-latest
    steps: []

  deploy:
    runs-on: ubuntu-latest
    steps: []
EOF
```

### Verificación

Debe existir una instalación reproducible, por ejemplo:

```text
requirements.txt
```

con PyYAML o dependencia equivalente.

El comando documentado debe producir:

```text
test
deploy
```

El orden puede variar.

Verificación posible:

```bash
venv/bin/python yaml_jobs.py ejemplo.yml
```

### Aprobado

PASS si:

```text
- utiliza un entorno aislado;
- declara la dependencia;
- procesa YAML real;
- devuelve test y deploy;
- puede repetirse desde un checkout limpio instalando dependencias.
```

No aprobar si funciona solamente porque una dependencia ya estaba instalada globalmente.

---

# Nivel 6 — Autonomía real: pedido ambiguo, planificación y verificación

## Objetivo

Buscar el techo real de autonomía.

En este nivel el usuario expresa **el problema**, no la solución técnica.

El agente debe decidir:

- qué revisar;
- qué archivos crear;
- cómo ejecutar los chequeos;
- cómo representar el resultado;
- cómo verificar que funciona;
- qué errores deben producir exit code distinto de cero.

No debería pedir instrucciones adicionales salvo bloqueo real.

## Herramienta

Preflight automático para revisar un repo antes de aprobar desde Telegram.

| Campo | Definición |
|---|---|
| **Mensaje exacto de Telegram** | `Necesito saber, antes de aprobar un cambio desde Telegram, si el repo quedó sano. Hacé algo práctico que revise lo importante, me dé un resumen corto y me deje claro si puedo aprobar o si hay un problema. Dejalo probado y listo para usar con un solo comando. No me preguntes cosas salvo que sea realmente imposible seguir.` |
| **Motor esperado** | 🧠 Claude |
| **Heurística actual** | ✅ Acierta por fallback: no encuentra una pista local segura y manda la tarea a Claude. |
| **Capacidad medida** | Planificación autónoma, inspección del repo, decisiones técnicas, multiarchivo, ejecución y autoverificación. |

## Contrato oculto del evaluador

El prompt no debe revelar estos requisitos.

La solución se evalúa posteriormente contra ellos.

Como mínimo, la herramienta debe poder detectar:

1. Python con error de sintaxis.
2. Tests existentes que fallan.
3. Estado Git.
4. Rama actual.
5. Resultado final apto/no apto.
6. Exit code distinto de cero cuando encuentra un fallo grave.

No se exige una arquitectura concreta.

### Verificación A — repo sano

```bash
python <comando-elegido-por-el-agente>
echo $?
```

Debe devolver:

```text
0
```

y un resumen entendible.

### Verificación B — sintaxis rota

Crear:

```bash
cat > roto.py <<'EOF'
def esto_no_compila(
EOF
```

Ejecutar el preflight.

Debe:

```text
- detectar el problema;
- indicar qué archivo falló;
- devolver exit code != 0.
```

### Verificación C — test roto

Con un unittest deliberadamente fallido:

```python
import unittest

class TestFalla(unittest.TestCase):
    def test_falla(self):
        self.assertEqual(1, 2)

if __name__ == "__main__":
    unittest.main()
```

El preflight debe finalizar con:

```text
exit code != 0
```

### Aprobado

PASS solamente si el agente:

```text
1. interpreta correctamente un pedido ambiguo;
2. inspecciona el repo antes de decidir;
3. implementa una solución coherente;
4. ejecuta su propia solución;
5. ejecuta/verifica tests o chequeos;
6. deja una forma clara de uso;
7. diferencia éxito de fallo mediante exit codes;
8. no necesita intervención humana durante la implementación.
```

## Qué representa este nivel

Este nivel no mide simplemente programación.

Mide el ciclo completo:

```text
ENTENDER
   ↓
INSPECCIONAR
   ↓
PLANIFICAR
   ↓
IMPLEMENTAR
   ↓
EJECUTAR
   ↓
DETECTAR FALLOS
   ↓
CORREGIR
   ↓
VOLVER A VERIFICAR
   ↓
ENTREGAR DIFF
```

Si Claude completa correctamente este nivel, el agente ya demuestra autonomía útil de desarrollo bajo supervisión humana final.

---

# 3. Predicción del techo de cada motor

## ⚡ Motor local

### Nivel 0

```text
Esperado: PASS
```

Tarea perfectamente compatible con su arquitectura.

### Nivel 1

```text
Esperado: primer FAIL probable
```

Razón:

```text
casos borde semánticos que requieren comprender sutilezas del lenguaje
```

Este comportamiento ya apareció en las pruebas iniciales con `bool` frente a `int`.

### Nivel 2

```text
Esperado: FAIL estructural seguro
```

Aunque el modelo entendiera perfectamente la tarea:

```text
run_local_single_file()
```

solo puede escribir un archivo.

Por lo tanto no puede satisfacer correctamente una tarea que exija:

```text
implementación + test separado
```

---

# 4. Punto recomendado de escalamiento

La regla no debería ser simplemente:

```text
"tarea difícil" → Claude
```

La división más robusta sería:

## Mantener en Local solamente cuando TODAS sean verdaderas

```text
1. Hay exactamente un archivo objetivo.
2. No hace falta crear tests separados.
3. No hay que diagnosticar un bug desconocido.
4. No hay que instalar dependencias.
5. No hay que ejecutar una secuencia de comandos.
6. No hay cambios coordinados entre archivos.
7. El resultado puede validarse localmente con reglas simples.
```

Si cualquiera falla:

```text
→ 🧠 Claude Code
```

---

# 5. Hallazgo específico esperado sobre la heurística actual

La batería está diseñada para detectar una debilidad concreta de `recommend_engine()`.

Actualmente:

```python
_LOCAL_HINTS = (
    "una funcion",
    "una función",
    "un archivo",
    "un test",
    "un script",
    ...
)
```

Por eso una petición como:

```text
Creá un script X y agregá un test Y
```

puede clasificarse como Local aunque implique **dos archivos**.

Esto demuestra que:

> las keywords describen palabras del pedido, pero no necesariamente su complejidad estructural.

Una futura versión debería detectar primero señales estructurales:

```text
múltiples archivos
tests separados
dependencias
repo existente
debug
comandos
entorno
```

y recién después utilizar keywords como optimización de costo.

---

# 6. Distinción entre techo de calidad y techo arquitectónico

Es importante registrar dos límites distintos.

## Techo de calidad esperado

```text
Nivel 1
```

El modelo local puede técnicamente ejecutar la tarea, pero puede producir código incorrecto en un caso borde.

## Techo arquitectónico

```text
Nivel 2
```

El runtime local directamente carece de capacidad para satisfacer la tarea completa porque solo puede escribir un archivo.

Esta diferencia es importante para decidir mejoras futuras:

```text
fallo Nivel 1
→ puede mejorar cambiando modelo, prompt o añadiendo validación

fallo Nivel 2
→ requiere cambiar arquitectura o escalar de motor
```

---

# 7. Tabla de resultados

Completar después de cada ejecución.

| Nivel | Herramienta | Motor recomendado | Motor elegido | Heurística | Tiempo | Criterio objetivo | Resultado | Observaciones |
|---|---|---|---|---|---|---|---|---|
| 0 | Contador de líneas | ⚡ Local | | ✅ esperado | | salida `3` | ⬜ | |
| 1 | Resumen de tiempos JSON | ⚡ Local | | ✅ esperado | | `3 / 8.5` | ⬜ | |
| 2 | Resumen staged + tests | 🧠 Claude | | ❌ fallo esperado | | unittest + 2 archivos | ⬜ | |
| 3 | repo_guard | 🧠 Claude | | ✅ esperado | | tests + detección `.env` | ⬜ | |
| 4 | Sanitizador de logs | 🧠 Claude | | ✅ esperado | | regresión completa | ⬜ | |
| 5 | Inspector YAML | 🧠 Claude | | ✅ esperado | | instalación limpia + salida | ⬜ | |
| 6 | Preflight autónomo | 🧠 Claude | | ✅ fallback | | repo sano/roto + exit codes | ⬜ | |

---

# 8. Métricas adicionales a registrar

Además de PASS/FAIL, conviene guardar para cada prueba:

```text
motor elegido
motor esperado
tiempo total
tokens de salida
cantidad de archivos modificados
cantidad de intentos
tests ejecutados por el propio agente
tests pasados
intervenciones humanas requeridas
regresiones introducidas
```

Esto permite calcular después:

```text
tasa de acierto del router
tasa de éxito Local
tasa de éxito Claude
costo por tarea aprobada
tiempo por tarea aprobada
nivel máximo de autonomía
```

---

# 9. Regla para detener la batería

Un fallo aislado no define automáticamente el techo.

Si un nivel falla:

```text
repetirlo una segunda vez con el mismo motor
```

sin cambiar el enunciado.

Interpretación:

```text
2/2 PASS  → capacidad demostrada
1/2 PASS  → capacidad inestable
0/2 PASS  → límite demostrado
```

No modificar el prompt entre repeticiones, porque dejaría de ser una comparación válida.

---

# 10. Resultado que buscamos obtener

Al finalizar la batería deberíamos poder responder con evidencia:

```text
¿Qué puede resolver Local de manera confiable?

¿Cuándo debe escalar obligatoriamente a Claude?

¿La heurística detecta ese límite?

¿Claude solamente genera código o también verifica lo que hizo?

¿Cuántos pasos puede completar sin intervención humana?

¿Cuál es el nivel máximo donde el sistema sigue produciendo resultados
repetibles y seguros?
```

La hipótesis inicial a validar es:

```text
Nivel 0     → ⚡ Local confiable
Nivel 1     → ⚡ Local empieza a degradarse por calidad
Nivel 2     → ⚡ Local imposible por arquitectura
Nivel 2–5   → 🧠 Claude debería operar con alta confiabilidad
Nivel 6     → prueba real del techo de autonomía de Claude
```

El objetivo no es demostrar que un modelo es "mejor".

El objetivo es encontrar el punto más económico donde ⚡ Local todavía es confiable y el punto exacto donde escalar a 🧠 Claude deja de ser opcional.
