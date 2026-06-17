#!/usr/bin/env python3
"""Activate / deactivate a Lightning AI GPU for the local Ollama vision route (Route B).

DocIntel's `vision_local` route runs Ollama Llama-3.2-Vision. That model is too slow to be
usable on CPU, so for local/private extraction at speed you attach a GPU. On a free Lightning
plan (limited GPU-hours/month) the right pattern is: **switch to GPU only for the run, then
switch straight back to CPU** so the GPU clock stops. This script automates exactly that.

Auth comes from the environment (never hard-code keys):
    export LIGHTNING_USER_ID=...        # your Lightning user id
    export LIGHTNING_API_KEY=...        # your Lightning API key  (rotate if it leaks)

Usage:
    python scripts/gpu_activate.py list                       # discover studios you can control
    python scripts/gpu_activate.py status   [--name S --teamspace T]
    python scripts/gpu_activate.py gpu T4   [--name S --teamspace T]   # wake + attach a GPU
    python scripts/gpu_activate.py cpu      [--name S --teamspace T]   # switch back to CPU (stop billing)

Run with no --name/--teamspace **from inside a Studio** to auto-detect the current one.
GPU types: T4 (cheapest), L4, A10G, A100. Default GPU is T4 to conserve free GPU-hours.
"""
from __future__ import annotations

import argparse
import os
import sys


def _require_auth() -> None:
    missing = [k for k in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY") if not os.environ.get(k)]
    if missing:
        sys.exit(f"error: missing env var(s): {', '.join(missing)} (see this file's docstring)")


def _machine(sdk, name: str):
    """Resolve a Machine enum from a string like 'T4'/'CPU' (case-insensitive)."""
    from lightning_sdk import Machine
    key = name.strip().upper()
    if not hasattr(Machine, key):
        valid = [m for m in dir(Machine) if m.isupper()]
        sys.exit(f"error: unknown machine '{name}'. Try one of: {', '.join(valid)}")
    return getattr(Machine, key)


def _resolve_studio(sdk, args):
    """Return a Studio handle, either by name/teamspace or auto-detected (inside a Studio)."""
    from lightning_sdk import Studio
    if args.name:
        kw = {"name": args.name}
        if args.teamspace:
            kw["teamspace"] = args.teamspace
        if args.user:
            kw["user"] = args.user
        if args.org:
            kw["org"] = args.org
        return Studio(**kw)
    # No name → assume we're running inside the target Studio (auto-detect).
    return Studio()


def _print_status(s) -> None:
    machine = getattr(s, "machine", "?")
    status = getattr(s, "status", "?")
    print(f"studio={getattr(s, 'name', '?')}  status={status}  machine={machine}")


def cmd_list(sdk, args) -> None:
    """Best-effort discovery of studios this account can control."""
    import lightning_sdk
    try:
        from lightning_sdk import Teamspace, User
        user = User(name=args.user) if args.user else None
        found = False
        # Teamspaces are reachable via the user's owned + member teamspaces.
        teamspaces = []
        if user is not None and hasattr(user, "teamspaces"):
            teamspaces = list(user.teamspaces)
        for ts in teamspaces:
            for st in getattr(ts, "studios", []):
                found = True
                print(f"name={st.name!r}  teamspace={ts.name!r}")
        if not found:
            print("no studios discovered automatically — pass --name/--teamspace explicitly.")
    except Exception as e:  # discovery API varies by SDK version; fail soft with guidance
        print(f"auto-discovery unavailable ({e!r}); pass --name/--teamspace explicitly.")


def cmd_status(sdk, args) -> None:
    _print_status(_resolve_studio(sdk, args))


def cmd_gpu(sdk, args) -> None:
    s = _resolve_studio(sdk, args)
    if getattr(s, "status", None) != "running":
        print("starting studio ...")
        s.start()
    target = _machine(sdk, args.gpu_type)
    if getattr(s, "machine", None) == target:
        print(f"already on {args.gpu_type}")
    else:
        print(f"switching to {args.gpu_type} (this bounces the studio) ...")
        s.switch_machine(target)
    _print_status(s)
    print("REMINDER: run `cpu` as soon as the GPU run finishes to stop GPU billing.")


def cmd_cpu(sdk, args) -> None:
    s = _resolve_studio(sdk, args)
    target = _machine(sdk, "CPU")
    if getattr(s, "machine", None) == target:
        print("already on CPU")
    else:
        print("switching back to CPU ...")
        s.switch_machine(target)
    _print_status(s)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["list", "status", "gpu", "cpu"])
    ap.add_argument("gpu_type", nargs="?", default="T4",
                    help="GPU type for `gpu` (default T4): T4|L4|A10G|A100")
    ap.add_argument("--name", help="Studio name (omit to auto-detect when run inside a Studio)")
    ap.add_argument("--teamspace", help="Teamspace name")
    ap.add_argument("--user", help="Lightning username (for discovery / disambiguation)")
    ap.add_argument("--org", help="Organization name (if the studio is org-owned)")
    args = ap.parse_args()

    _require_auth()
    try:
        import lightning_sdk as sdk
    except ImportError:
        sys.exit("error: lightning_sdk not installed — `pip install lightning-sdk`")

    {"list": cmd_list, "status": cmd_status, "gpu": cmd_gpu, "cpu": cmd_cpu}[args.command](sdk, args)


if __name__ == "__main__":
    main()
