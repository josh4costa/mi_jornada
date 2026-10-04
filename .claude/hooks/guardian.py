#!/usr/bin/env python3
"""Hook PreToolUse (Bash) del kit: bloquea comandos que mostrarían secretos o que suben a main.

Bloquea (exit 2, el motivo le llega a Claude):
- Leer .env (o .env.local, .env.prod…) o llaves (*.pem, *.key, ~/.ssh, id_rsa…) con cat, grep, sed, cp…
  .env.example sí se puede leer y editar.
- `grep -r` sin excluir .env, `docker compose config` sin --services/-q (imprime los secretos),
  printenv/env dentro de contenedores, `docker inspect` sin --format.
- `git push` estando en main, hacia main (main, HEAD:main, …:main), --all/--mirror, y cualquier forzado
  (--force, -f, --force-with-lease, +rama).
Es una barrera contra errores, no un aislamiento completo: un programa puede leer .env por su cuenta.
"""

import json
import os
import re
import shlex
import subprocess
import sys

LECTORES = {
    "cat",
    "tac",
    "less",
    "more",
    "head",
    "tail",
    "grep",
    "egrep",
    "fgrep",
    "rg",
    "ag",
    "sed",
    "awk",
    "gawk",
    "bat",
    "batcat",
    "strings",
    "xxd",
    "od",
    "hexdump",
    "base64",
    "nl",
    "cut",
    "sort",
    "uniq",
    "diff",
    "cmp",
    "vi",
    "vim",
    "view",
    "nano",
    "source",
    ".",
    "cp",
    "mv",
    "scp",
    "rsync",
    "tar",
    "zip",
    "curl",
    "wget",
    "openssl",
    "column",
    "paste",
    "tee",
    "jq",
    "yq",
    "python",
    "python3",
}
PERMITIDOS_ENV = {".env.example", ".env.sample", ".env.template"}
SEPARADORES = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;"}
PREFIJOS = {"sudo", "env", "nohup", "time", "command", "exec", "xargs", "nice", "timeout", "stdbuf"}


def es_env(token: str) -> bool:
    if token.startswith(("--exclude", "--ignore", "--glob=!")):  # grep --exclude='.env*' protege, no lee
        return False
    for parte in re.split(r"[=:@]", token):  # --env-file=.env, curl -d @.env
        base = os.path.basename(parte.strip("'\"").rstrip("/"))
        if base in PERMITIDOS_ENV:
            continue
        if base == ".env" or base.startswith(".env.") or (re.search(r"[*?\[]", base) and base.startswith(".env")):
            return True
    return False


def es_llave(token: str) -> bool:
    t = token.strip("'\"")
    base = os.path.basename(t.rstrip("/"))
    if base.endswith(".pub"):
        return False
    return (
        bool(re.search(r"(^|/)\.ssh(/|$)", t))
        or base.endswith((".pem", ".key", ".p12", ".pfx"))
        or bool(re.match(r"id_(rsa|dsa|ecdsa|ed25519)", base))
    )


def comandos(cmd: str) -> list[list[str]]:
    """Parte el texto en comandos simples (por línea y por ; && || | etc.)."""
    salida: list[list[str]] = []
    for linea in cmd.splitlines():
        try:
            lx = shlex.shlex(linea, posix=True, punctuation_chars=True)
            lx.whitespace_split = True
            tokens = list(lx)
        except ValueError:
            tokens = linea.split()
        actual: list[str] = []
        for t in tokens:
            if t in SEPARADORES or set(t) <= set(";&|()"):
                if actual:
                    salida.append(actual)
                actual = []
            else:
                actual.append(t.lstrip("$`").rstrip("`"))
        if actual:
            salida.append(actual)
    return salida


def sin_prefijos(c: list[str]) -> list[str]:
    i = 0
    while i < len(c) and (
        c[i] in PREFIJOS
        or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", c[i])
        or c[i].startswith("-")
        or re.fullmatch(r"[0-9.]+[smhd]?", c[i])
    ):
        i += 1
    return c[i:]


def rama_actual(cwd: str) -> str:
    try:
        r = subprocess.run(  # noqa: S603
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def revisar_push(args: list[str], cwd: str) -> str | None:
    opciones = [a for a in args if a.startswith("-")]
    resto = [a for a in args if not a.startswith("-")]
    for o in opciones:
        if (
            o in ("-f", "--force", "--mirror", "--all", "--force-if-includes")
            or o.startswith("--force-with-lease")
            or (re.fullmatch(r"-[a-zA-Z]+", o) and "f" in o)
        ):
            return f"git push con {o} está prohibido (forzar o subir todas las ramas). Sube solo tu rama, sin forzar."
    refspecs = resto[1:]  # resto[0] es el remoto
    for r in refspecs:
        destino = r.split(":")[-1].removeprefix("refs/heads/")
        if r.startswith("+"):
            return "git push con +rama fuerza el envío: prohibido."
        if destino in ("main", "master"):
            return "No se sube a main. Sube tu rama y abre un PR (gh pr create); el merge lo aprueba Josué."
    if not refspecs or any(r.split(":")[0] == "HEAD" and ":" not in r for r in refspecs):
        if rama_actual(cwd) in ("main", "master"):
            return "Estás en main: no se sube desde aquí. Crea una rama (git switch -c funcion/<nombre>) y súbela."
    return None


def hay_env_en(directorio: str) -> bool:
    """¿Hay un .env con secretos en esa carpeta o debajo (hasta 3 niveles)?"""
    raiz = directorio.rstrip("/") or "/"
    for actual, carpetas, archivos in os.walk(raiz):
        carpetas[:] = [d for d in carpetas if d not in (".git", ".venv", "node_modules", "__pycache__")]
        if actual.count(os.sep) - raiz.count(os.sep) >= 3:
            carpetas[:] = []
        if any(es_env(a) for a in archivos):
            return True
    return False


def grep_recursivo_con_env(args: list[str], cwd: str) -> bool:
    if not any(a in ("-r", "-R", "--recursive") or re.fullmatch(r"-[a-zA-Z]*[rR][a-zA-Z]*", a) for a in args):
        return False
    if any(a.startswith("--exclude") and ".env" in a for a in args):
        return False
    posicionales = [a for a in args if not a.startswith("-")]
    con_patron = any(a in ("-e", "-f") or a.startswith(("--regexp", "--file")) for a in args)
    rutas = posicionales if con_patron else posicionales[1:]
    rutas = rutas or ["."]
    return any(hay_env_en(os.path.join(cwd, r)) for r in rutas if os.path.isdir(os.path.join(cwd, r)))


def revisar(c: list[str], cwd: str) -> str | None:
    if c and os.path.basename(c[0]) == "env" and len(c) == 1:
        return "No muestres todas las variables de entorno."
    c = sin_prefijos(c)
    if not c:
        return None
    prog = os.path.basename(c[0])
    args = c[1:]
    # git (también git -C ruta push …)
    if prog == "git":
        i = 0
        while i < len(args) and args[i].startswith("-"):
            i += 2 if args[i] in ("-C", "-c") else 1
        if i < len(args) and args[i] == "push":
            return revisar_push(args[i + 1 :], cwd)
        if i < len(args) and args[i] in ("show", "log", "diff") and any(es_env(a) for a in args[i + 1 :]):
            return "No leas .env desde git (tiene secretos)."
        return None
    # docker compose config / exec / inspect
    if prog in ("docker", "docker-compose"):
        palabras = [a for a in args if not a.startswith("-")]
        if "config" in palabras and (prog == "docker-compose" or "compose" in palabras):
            despues = args[args.index("config") + 1 :]
            if not any(a in ("--services", "-q", "--quiet", "--volumes", "--images", "--profiles") for a in despues):
                return (
                    "docker compose config imprime los secretos del .env. Usa `docker compose config --services` "
                    "o `docker compose config -q` (solo valida)."
                )
        if any(p in palabras for p in ("exec", "run")):
            if (
                any(os.path.basename(a) in ("printenv", "env") for a in args)
                or "environ" in " ".join(args)
                or re.search(r"\bexport\s+-p\b", " ".join(args))
            ):
                return "No muestres las variables de entorno del contenedor (tienen secretos)."
        if "inspect" in palabras:
            formato = " ".join(args)
            if not re.search(r"(--format|-f)[ =]", formato) or "Env" in formato or "json" in formato:
                return (
                    "docker inspect sin --format muestra las variables (secretos). "
                    "Usa --format con el campo que necesitas."
                )
        return None
    if prog in ("printenv",) or (prog == "env" and not args):
        return "No muestres todas las variables de entorno."
    if prog in LECTORES:
        origen = args[:-1] if prog in ("cp", "mv", "scp", "rsync") else args  # el destino puede ser .env
        if any(es_env(a) for a in origen):
            return "No leas .env ni copias de él (tiene secretos). Usa .env.example para ver qué variables existen."
        if any(es_llave(a) for a in args):
            return "No leas llaves privadas ni ~/.ssh."
        if prog in ("grep", "egrep", "fgrep") and grep_recursivo_con_env(args, cwd):
            return "grep -r leería .env. Agrega --exclude='.env*' (o usa la herramienta Grep)."
    return None


def main() -> None:
    try:
        datos = json.load(sys.stdin)
    except Exception:
        return
    if datos.get("tool_name") != "Bash":
        return
    cmd = (datos.get("tool_input") or {}).get("command") or ""
    cwd = datos.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or "."
    pendientes = [cmd]
    # bash -c '…' / sh -c "…": revisa también lo de adentro
    pendientes += [m.group(2) for m in re.finditer(r"\b(?:ba|z|da)?sh\s+-c\s+(['\"])(.*?)\1", cmd, re.S)]
    for texto in pendientes:
        for c in comandos(texto):
            motivo = revisar(c, cwd)
            if motivo:
                print(f"Bloqueado por el guardián del kit: {motivo}", file=sys.stderr)
                sys.exit(2)


main()
