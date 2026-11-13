#!/usr/bin/env python3
"""Check (or ensure) Ollama is running with the pinned models pulled.

Default mode is a read-only **preflight check**: it fails fast with an
actionable message so a missing server or un-pulled model is reported up front
rather than as a confusing error partway through a run.

With ``--ensure`` it will actively *bring the environment up*: start the Ollama
server if it isn't running (via ``brew services`` when available, else a
backgrounded ``ollama serve``), wait for it to answer, and ``ollama pull`` any
missing pinned models.

Exit code 0 when the server is reachable and both pinned models are available;
non-zero otherwise.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.lib.models import (  # noqa: E402
    GENERATION_MODEL,
    JUDGE_MODEL,
    ollama_base_url,
)

PINNED_MODELS = (GENERATION_MODEL, JUDGE_MODEL)


def _installed_models(base_url: str) -> list[str]:
    url = f"{base_url}/api/tags"
    with urllib.request.urlopen(url, timeout=3.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m.get("name", "") for m in (data or {}).get("models", [])]


def _server_reachable(base_url: str) -> bool:
    try:
        _installed_models(base_url)
        return True
    except Exception:
        return False


def _matches(installed: list[str], wanted: str) -> bool:
    # Require an exact tag match so the pinned model is honoured (we do not
    # loosen the tag on purpose).
    return wanted in installed


def _ollama_cli() -> str | None:
    return shutil.which("ollama")


def _start_server(base_url: str) -> bool:
    """Best-effort start of the Ollama server; return True once reachable."""
    cli = _ollama_cli()
    if cli is None:
        print(
            "Ollama CLI not found on PATH. Install it from https://ollama.com "
            "or start the Ollama app, then retry.",
            file=sys.stderr,
        )
        return False

    # Prefer a managed background service on macOS/Homebrew; fall back to a
    # detached `ollama serve`.
    started = False
    brew = shutil.which("brew")
    if brew is not None:
        try:
            subprocess.run(
                [brew, "services", "start", "ollama"],
                check=False,
                capture_output=True,
                text=True,
            )
            started = True
        except Exception:
            started = False

    if not started:
        try:
            # Detached: let it keep running after this script exits.
            subprocess.Popen(
                [cli, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            print(f"Could not start `ollama serve`: {exc}", file=sys.stderr)
            return False

    # Wait for the server to answer.
    print("Starting Ollama server…")
    for _ in range(30):  # up to ~30s
        if _server_reachable(base_url):
            return True
        time.sleep(1.0)
    print("Ollama server did not become reachable in time.", file=sys.stderr)
    return False


def _pull_model(model: str) -> bool:
    cli = _ollama_cli()
    if cli is None:
        return False
    print(f"Pulling {model} (first time only; this may take a while)…")
    result = subprocess.run([cli, "pull", model], check=False)
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ensure",
        action="store_true",
        help="start the server and pull missing pinned models (not just check)",
    )
    args = parser.parse_args(argv)

    base_url = ollama_base_url()

    # 1. Server reachability.
    if not _server_reachable(base_url):
        if not args.ensure:
            print(
                f"Ollama is not reachable at {base_url}.\n"
                f"Start it (e.g. `ollama serve`, `brew services start ollama`, "
                f"or open the Ollama app), or run `make ollama-up`, then retry.",
                file=sys.stderr,
            )
            return 1
        if not _start_server(base_url):
            return 1

    # 2. Pinned models present.
    installed = _installed_models(base_url)
    missing = [m for m in PINNED_MODELS if not _matches(installed, m)]
    if missing:
        if not args.ensure:
            print(
                "Ollama is running but these pinned models are not pulled: "
                + ", ".join(missing)
                + "\nPull them with:\n"
                + "\n".join(f"    ollama pull {m}" for m in missing)
                + "\n(or run `make ollama-up`).",
                file=sys.stderr,
            )
            return 1
        for m in missing:
            if not _pull_model(m):
                print(f"Failed to pull {m}.", file=sys.stderr)
                return 1

    print(
        f"Ollama ready at {base_url}: {GENERATION_MODEL} (generation) and "
        f"{JUDGE_MODEL} (judge) are available."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
