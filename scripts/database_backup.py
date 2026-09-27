"""Backup PostgreSQL or verify a restore into a NEW database. Requires Docker Compose."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("file", type=Path)
    restore = commands.add_parser("restore-check")
    restore.add_argument("file", type=Path)
    restore.add_argument("--database", required=True, help="New database name starting with restore_check_")
    args = parser.parse_args()
    compose = ["docker", "compose", "exec", "-T", "db"]
    if args.command == "backup":
        # Exclusive creation: never overwrite an existing backup.
        args.file.parent.mkdir(parents=True, exist_ok=True)
        with args.file.open("xb") as output:
            subprocess.run(compose + ["sh", "-c", 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom'],
                           cwd=ROOT, stdout=output, check=True)
        print(f"Respaldo creado: {args.file.resolve()}")
    else:
        if not re.fullmatch(r"restore_check_[a-z0-9_]{1,40}", args.database):
            parser.error("Usa un nombre nuevo restore_check_ seguido de letras minúsculas, números o guiones bajos")
        with args.file.open("rb") as source:
            # createdb fails if the target exists; never drop or clean an existing database.
            subprocess.run(compose + ["sh", "-c", 'createdb -U "$POSTGRES_USER" "$1"', "restore", args.database], cwd=ROOT, check=True)
            subprocess.run(compose + ["sh", "-c", 'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" -d "$1"', "restore", args.database],
                           cwd=ROOT, stdin=source, check=True)
        print(f"Respaldo restaurado en {args.database}. Valida los datos antes de usarlo para recuperación.")


if __name__ == "__main__":
    main()
