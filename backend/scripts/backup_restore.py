"""Cross-platform Database Backup and Restore Utility for CareerConnect.

Works on Windows, Linux, Docker, and Kubernetes environments.
Supports PostgreSQL binary format (via pg_dump/pg_restore) and Django logical JSON format.

Usage:
    python scripts/backup_restore.py backup [--dir ./backups] [--format json|dump]
    python scripts/backup_restore.py restore <backup_file> [--force]
"""
import argparse
import datetime
import os
from pathlib import Path
import subprocess
import sys


def get_base_dir() -> Path:
    p = Path(__file__).resolve().parent.parent
    if (p / "manage.py").exists():
        return p
    return p / "backend"


def run_cmd(cmd: list[str], env: dict[str, str] | None = None) -> int:
    proc = subprocess.run(cmd, env=env, text=True)
    return proc.returncode


def backup(backup_dir: Path, fmt: str = "auto") -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    manage_py = get_base_dir() / "manage.py"

    db_url = os.getenv("DATABASE_URL", "")

    use_dump = (fmt == "dump") or (fmt == "auto" and db_url.startswith("postgres"))

    if use_dump:
        out_file = backup_dir / f"careerconnect_pg_{ts}.dump"
        print(f"[*] Starting PostgreSQL binary backup to: {out_file}")
        cmd = ["pg_dump", "-Fc", "--no-owner", "--no-acl"]
        if db_url:
            cmd += ["-d", db_url]
        cmd += ["-f", str(out_file)]
        try:
            code = run_cmd(cmd)
            if code == 0 and out_file.exists() and out_file.stat().st_size > 0:
                print(f"[+] Backup successfully created ({out_file.stat().st_size} bytes)")
                return out_file
        except FileNotFoundError:
            print("[!] pg_dump not installed in PATH; falling back to Django logical dump...")

    out_file = backup_dir / f"careerconnect_data_{ts}.json"
    print(f"[*] Starting Django JSON dump to: {out_file}")
    with open(out_file, "w", encoding="utf-8") as f:
        proc = subprocess.run(
            [
                sys.executable,
                str(manage_py),
                "dumpdata",
                "--natural-foreign",
                "--natural-primary",
                "-e", "contenttypes",
                "-e", "auth.Permission",
                "--indent", "2",
            ],
            stdout=f,
            text=True,
            check=True,
        )
    print(f"[+] Logical backup created ({out_file.stat().st_size} bytes): {out_file}")
    return out_file


def restore(backup_file: Path, force: bool = False) -> None:
    if not backup_file.exists():
        sys.exit(f"Error: Backup file {backup_file} does not exist.")

    if not force:
        confirm = input(f"WARNING: Overwrite existing database from {backup_file.name}? (y/N): ")
        if confirm.strip().lower() not in ("y", "yes"):
            print("Restore aborted by user.")
            return

    manage_py = get_base_dir() / "manage.py"
    db_url = os.getenv("DATABASE_URL", "")

    if backup_file.suffix == ".dump":
        print("[*] Restoring from PostgreSQL binary dump...")
        cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-acl"]
        if db_url:
            cmd += ["-d", db_url]
        cmd.append(str(backup_file))
        run_cmd(cmd)
    elif backup_file.suffix == ".json":
        print("[*] Restoring from Django JSON fixture...")
        subprocess.run(
            [sys.executable, str(manage_py), "loaddata", str(backup_file)],
            check=True,
        )
    else:
        sys.exit("Error: Unknown backup file extension. Must be .dump or .json")

    print("[*] Reconciling schema migrations...")
    subprocess.run([sys.executable, str(manage_py), "migrate"], check=True)
    print("[+] Restore completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="CareerConnect Backup & Restore CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    b_parser = sub.add_parser("backup", help="Create database backup")
    b_parser.add_argument("--dir", default="./backups", help="Target backup directory")
    b_parser.add_argument("--format", default="auto", choices=["auto", "dump", "json"], help="Backup format")

    r_parser = sub.add_parser("restore", help="Restore database from backup")
    r_parser.add_argument("file", help="Path to backup file")
    r_parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    if args.command == "backup":
        backup(Path(args.dir), args.format)
    elif args.command == "restore":
        restore(Path(args.file), args.force)


if __name__ == "__main__":
    main()
