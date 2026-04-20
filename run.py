from __future__ import annotations

import argparse
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start FastAPI backend and React frontend dev servers together."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands that would run and exit.",
    )
    return parser.parse_args(argv)


def _resolve_executable(candidates: list[str]) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(str(candidate))
        if resolved:
            return resolved
    return None


def _build_backend_command() -> list[str]:
    uv_exec = _resolve_executable(["uv", "uv.exe"])
    if uv_exec:
        return [uv_exec, "run", "fastapi", "dev", "main.py"]

    # Fallback keeps launcher usable if uv is unavailable in PATH.
    return [sys.executable, "-m", "fastapi", "dev", "main.py"]


def _build_frontend_command() -> list[str]:
    if os.name == "nt":
        npm_exec = _resolve_executable(["npm.cmd", "npm", "npm.exe"])
    else:
        npm_exec = _resolve_executable(["npm"])

    if not npm_exec:
        raise RuntimeError(
            "Could not find npm in PATH. Install Node.js (includes npm) and restart your terminal."
        )

    return [npm_exec, "run", "dev"]


def _launch_process(command: list[str], cwd: Path, name: str) -> subprocess.Popen[str]:
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            text=True,
            creationflags=creationflags,
        )
    except FileNotFoundError as error:
        joined = " ".join(command)
        raise RuntimeError(
            f"Could not start {name} with command '{joined}'. Make sure required tooling is installed."
        ) from error

    print(f"[run.py] Started {name} (pid={process.pid})")
    return process


def _stop_process(process: subprocess.Popen[str], name: str) -> None:
    if process.poll() is not None:
        return

    print(f"[run.py] Stopping {name} (pid={process.pid})")
    if os.name == "nt":
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
        except Exception:
            process.terminate()
    else:
        process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    try:
        backend_cmd = _build_backend_command()
        frontend_cmd = _build_frontend_command()
    except RuntimeError as error:
        print(f"[run.py] {error}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"[run.py] Backend command: {' '.join(backend_cmd)}")
        print(f"[run.py] Frontend command: {' '.join(frontend_cmd)}")
        print(f"[run.py] Backend cwd: {ROOT_DIR}")
        print(f"[run.py] Frontend cwd: {FRONTEND_DIR}")
        return 0

    backend = _launch_process(backend_cmd, ROOT_DIR, "backend")
    frontend: subprocess.Popen[str] | None = None

    try:
        frontend = _launch_process(frontend_cmd, FRONTEND_DIR, "frontend")
    except RuntimeError as error:
        _stop_process(backend, "backend")
        print(f"[run.py] {error}", file=sys.stderr)
        return 1

    try:
        while True:
            backend_code = backend.poll()
            frontend_code = frontend.poll()

            if backend_code is not None:
                print(f"[run.py] Backend exited with code {backend_code}")
                _stop_process(frontend, "frontend")
                return backend_code

            if frontend_code is not None:
                print(f"[run.py] Frontend exited with code {frontend_code}")
                _stop_process(backend, "backend")
                return frontend_code

            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\n[run.py] Interrupt received, shutting down services...")
        _stop_process(frontend, "frontend")
        _stop_process(backend, "backend")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())



