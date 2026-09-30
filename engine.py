"""Motor del agente de desarrollo del bot.
Barreras: solo repos bajo ~/workspaces/sandbox; trabaja en rama nueva; NUNCA commitea
(deja los cambios en el árbol para que Gio apruebe el diff desde Telegram)."""
from __future__ import annotations
import json, os, re, subprocess, time, urllib.request
from pathlib import Path

ALLOWED_ROOTS = [Path.home() / "workspaces" / "sandbox"]
OLLAMA = "http://127.0.0.1:11434/api/generate"
LOCAL_MODEL = "qwen2.5-coder:7b"
SYS_LOCAL = ("Sos un programador Python experto. Cuando te pidan crear o editar UN archivo, "
             "respondé SOLO con el contenido COMPLETO del archivo dentro de un bloque ```python ... ```, "
             "sin explicaciones. Usá solo la biblioteca estándar salvo que se indique lo contrario.")

def _git(repo: Path, *args: str, check=True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout

def _allowed(repo: Path) -> bool:
    repo = repo.resolve()
    return any(str(repo).startswith(str(root.resolve())) for root in ALLOWED_ROOTS)

def prepare(repo: Path) -> str:
    """Valida el repo (allowlist), lo inicializa si hace falta y crea una rama nueva."""
    if not _allowed(repo):
        raise PermissionError(f"Repo fuera de la lista blanca (~/workspaces/sandbox): {repo}")
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        _git(repo, "init", "-q"); _git(repo, "config", "user.email", "bot@local")
        _git(repo, "config", "user.name", "dev-agent"); (repo / ".gitkeep").touch()
        _git(repo, "add", "-A"); _git(repo, "commit", "-qm", "init", check=False)
    branch = f"bot/{time.strftime('%Y%m%d-%H%M%S')}"
    _git(repo, "checkout", "-q", "-b", branch)
    return branch

def _ask_local(prompt: str, usage: dict) -> str:
    body = {"model": LOCAL_MODEL, "system": SYS_LOCAL, "prompt": prompt, "stream": False,
            "think": False, "options": {"temperature": 0.1, "num_ctx": 8192}}
    req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    usage["out"] += int(r.get("eval_count") or 0)
    return r.get("response", "")

def _extract(text: str) -> str:
    blocks = re.findall(r"```(?:\w+)?\s*(.*?)```", text, re.DOTALL)
    return (blocks[-1] if blocks else text).strip()

def run_local_single_file(repo: Path, target: str, task: str) -> dict:
    """Motor local: crea/edita UN archivo con qwen2.5-coder. Barato y rápido."""
    usage = {"out": 0}; t0 = time.time()
    path = (repo / target)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    ctx = f"\n\nContenido actual de {target}:\n```\n{existing}\n```" if existing else ""
    prompt = f"Tarea: {task}\nArchivo objetivo: {target}{ctx}"
    code = _extract(_ask_local(prompt, usage))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    diff = _git(repo, "diff", "--stat", check=False) + "\n" + _git(repo, "add", "-A", check=False) + _git(repo, "diff", "--cached", check=False)
    return {"engine": "local", "target": target, "seconds": round(time.time()-t0,1),
            "out_tokens": usage["out"], "diff": _git(repo, "diff", "--cached", check=False)}

if __name__ == "__main__":
    import sys
    repo = Path(sys.argv[1]); target = sys.argv[2]; task = sys.argv[3]
    branch = prepare(repo)
    res = run_local_single_file(repo, target, task)
    print(f"rama={branch} engine={res['engine']} {res['seconds']}s tok={res['out_tokens']}")
    print("--- diff ---"); print(res["diff"][:2000])

CLAUDE_BIN = "/home/giovany/.vscode-server/extensions/anthropic.claude-code-2.1.283-linux-x64/resources/native-binary/claude"

def run_claude_code(repo, task, timeout=600):
    """Motor Claude Code headless: hace el trabajo real (multi-archivo, ops) en el repo,
    en la rama ya creada. Permite editar/ejecutar; NO commitea (lo dejamos para el OK)."""
    import subprocess, time, json
    from pathlib import Path
    repo = Path(repo); t0 = time.time()
    cmd = [CLAUDE_BIN, "-p", task, "--output-format", "json",
           "--dangerously-skip-permissions"]
    r = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=timeout)
    out = r.stdout.strip()
    result = ""
    try:
        data = json.loads(out); result = data.get("result", "")[:1500]
    except Exception:
        result = out[:1500]
    diff = _git(repo, "add", "-A", check=False) or ""
    diff = _git(repo, "diff", "--cached", check=False)
    return {"engine": "claude_code", "seconds": round(time.time()-t0,1),
            "result": result, "diff": diff, "stderr": r.stderr[-500:]}

# --- Recomendación automática de motor (heurística instantánea) ---
_CC_HINTS = ("arregl", "refactor", "proyecto", "instal", "configur", "bug", "por que", "por qué",
             "falla", "error", "depura", "debug", "migra", "varios archivos", "el repo", "docker",
             "deploy", "pipeline", "test suite", "toda la", "todo el")
_LOCAL_HINTS = ("una funcion", "una función", "un archivo", "un test", "un script", "boilerplate",
                "agrega un", "agregá un", "escribi una", "escribí una", "cre[aá] un archivo")

def recommend_engine(task: str) -> dict:
    t = task.lower()
    if any(h in t for h in _CC_HINTS):
        return {"engine": "claude_code", "why": "parece multi-paso u ops (varios archivos, debug o configuración)"}
    if any(h in t for h in _LOCAL_HINTS) and not any(h in t for h in _CC_HINTS):
        return {"engine": "local", "why": "parece una tarea acotada de un archivo"}
    return {"engine": "claude_code", "why": "por las dudas uso el motor potente (tarea ambigua)"}

def run_task(repo, task, engine=None, target=None):
    """Despachador: prepara rama y corre el motor elegido. Nunca commitea."""
    from pathlib import Path
    repo = Path(repo)
    branch = prepare(repo)
    if engine is None:
        engine = recommend_engine(task)["engine"]
    if engine == "local":
        tgt = target or "solucion.py"
        res = run_local_single_file(repo, tgt, task)
    else:
        res = run_claude_code(repo, task)
    res["branch"] = branch
    return res
