from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .scheduler import (
    JOB_HANDLERS,
    create_scheduler_config,
    delete_scheduler_config,
    list_scheduler_configs,
    refresh_scheduler_jobs,
    serialize_scheduler_config,
    update_scheduler_config,
)


def _parse_parameters(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for parameters: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Parameters JSON must be an object")
    return data


def cmd_list(args: argparse.Namespace) -> None:
    configs = [serialize_scheduler_config(cfg) for cfg in list_scheduler_configs()]
    if args.json:
        json.dump(configs, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    if not configs:
        print("No scheduler configs defined.")
        return
    for cfg in configs:
        profile = cfg.get("growth_profile") or {}
        profile_label = profile.get("name") or cfg.get("growth_profile_id") or "-"
        print(
            f"[{cfg['config_id']}] {cfg['job_id']} | cron={cfg['cron']} | "
            f"enabled={cfg['enabled']} | priority={cfg['priority']} | profile={profile_label}"
        )
        if cfg["parameters"]:
            print(f"    params: {json.dumps(cfg['parameters'])}")


def cmd_add(args: argparse.Namespace) -> None:
    params = _parse_parameters(args.parameters)
    cfg = create_scheduler_config(
        job_id=args.job_id,
        name=args.name,
        cron=args.cron,
        enabled=not args.disabled,
        priority=args.priority,
        concurrency_limit=args.concurrency,
        lock_timeout_seconds=args.lock_timeout,
        parameters=params,
        growth_profile_id=args.growth_profile_id,
    )
    print(f"Created scheduler config {cfg.id} for job '{cfg.job_id}'.")


def cmd_update(args: argparse.Namespace) -> None:
    payload: dict[str, Any] = {}
    if args.job_id:
        payload["job_id"] = args.job_id
    if args.name is not None:
        payload["name"] = args.name
    if args.cron:
        payload["cron"] = args.cron
    if args.priority is not None:
        payload["priority"] = args.priority
    if args.concurrency is not None:
        payload["concurrency_limit"] = args.concurrency
    if args.lock_timeout is not None:
        payload["lock_timeout_seconds"] = args.lock_timeout
    if args.enable:
        payload["enabled"] = True
    if args.disable:
        payload["enabled"] = False
    if args.parameters is not None:
        payload["parameters"] = _parse_parameters(args.parameters)
    if args.growth_profile_id is not None:
        payload["growth_profile_id"] = args.growth_profile_id
    if not payload:
        raise SystemExit("No fields provided to update.")
    cfg = update_scheduler_config(args.config_id, **payload)
    if not cfg:
        raise SystemExit(f"Config {args.config_id} not found")
    print(f"Updated scheduler config {cfg.id}.")


def cmd_delete(args: argparse.Namespace) -> None:
    if not delete_scheduler_config(args.config_id):
        raise SystemExit(f"Config {args.config_id} not found")
    print(f"Deleted scheduler config {args.config_id}.")


def cmd_refresh(_: argparse.Namespace) -> None:
    refresh_scheduler_jobs()
    print("Scheduler refresh triggered (if worker is running).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trendspark", description="Trend Spark AI management CLI"
    )
    sub = parser.add_subparsers(dest="command")

    list_cmd = sub.add_parser("scheduler-list", help="List scheduler configs")
    list_cmd.add_argument("--json", action="store_true", help="Output as JSON")
    list_cmd.set_defaults(func=cmd_list)

    add_cmd = sub.add_parser("scheduler-add", help="Create new scheduler config")
    add_cmd.add_argument("job_id", choices=sorted(JOB_HANDLERS.keys()))
    add_cmd.add_argument("cron", help="Cron expression (crontab format)")
    add_cmd.add_argument("--name")
    add_cmd.add_argument("--disabled", action="store_true")
    add_cmd.add_argument("--priority", type=int, default=5)
    add_cmd.add_argument("--concurrency", type=int, default=1)
    add_cmd.add_argument("--lock-timeout", type=int, default=300)
    add_cmd.add_argument("--parameters", help="JSON object with job parameters")
    add_cmd.add_argument(
        "--growth-profile-id", type=int, help="Target growth profile ID"
    )
    add_cmd.set_defaults(func=cmd_add)

    upd_cmd = sub.add_parser("scheduler-update", help="Update existing config")
    upd_cmd.add_argument("config_id", type=int)
    upd_cmd.add_argument("--job-id", choices=sorted(JOB_HANDLERS.keys()))
    upd_cmd.add_argument("--name")
    upd_cmd.add_argument("--cron")
    upd_cmd.add_argument("--priority", type=int)
    upd_cmd.add_argument("--concurrency", type=int)
    upd_cmd.add_argument("--lock-timeout", type=int)
    upd_cmd.add_argument("--enable", action="store_true")
    upd_cmd.add_argument("--disable", action="store_true")
    upd_cmd.add_argument("--parameters", help="JSON object with job parameters")
    upd_cmd.add_argument(
        "--growth-profile-id", type=int, help="Target growth profile ID"
    )
    upd_cmd.set_defaults(func=cmd_update)

    del_cmd = sub.add_parser("scheduler-delete", help="Delete config")
    del_cmd.add_argument("config_id", type=int)
    del_cmd.set_defaults(func=cmd_delete)

    ref_cmd = sub.add_parser("scheduler-refresh", help="Force worker scheduler refresh")
    ref_cmd.set_defaults(func=cmd_refresh)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        parser.exit()
    args.func(args)


if __name__ == "__main__":
    main()
