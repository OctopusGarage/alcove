from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.home import AlcoveHome
from alcove.service import ServiceModule


def handle_service_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: Callable[[argparse.ArgumentParser, str], int],
) -> int:
    home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
    service_module = ServiceModule(home)
    dashboard = bool(getattr(args, "dashboard", False))
    scheduler = bool(getattr(args, "scheduler", False))
    if args.service_command == "install":
        payload = service_module.install(
            dashboard=dashboard,
            scheduler=scheduler,
            host=args.host,
            port=args.port,
            interval_minutes=args.interval_minutes,
            load=args.load,
        )
    elif args.service_command == "uninstall":
        payload = service_module.uninstall(
            dashboard=dashboard,
            scheduler=scheduler,
            unload=args.unload,
        )
    elif args.service_command == "status":
        payload = service_module.status(dashboard=dashboard, scheduler=scheduler)
    elif args.service_command == "start":
        payload = service_module.start(dashboard=dashboard, scheduler=scheduler)
    elif args.service_command == "stop":
        payload = service_module.stop(dashboard=dashboard, scheduler=scheduler)
    elif args.service_command == "restart":
        service_module.stop(dashboard=dashboard, scheduler=scheduler)
        payload = service_module.start(dashboard=dashboard, scheduler=scheduler)
        payload["status"] = "restarted"
    elif args.service_command == "tick":
        payload = service_module.tick(
            retention_days=args.retention_days,
            refresh_connectors=not args.skip_connectors,
            check_watchers=not args.skip_watchers,
            check_blogs=not args.skip_blogs,
            check_radars=not args.skip_radars,
            run_automations=not args.skip_automations,
            run_publishers=not args.skip_publishers,
            refresh_mounts=not args.skip_mounts,
            mount_refresh_days=args.mount_refresh_days,
            fix_health=not args.skip_health_fix,
            today=args.today,
        )
    else:
        return argument_error(parser, "the following arguments are required: service_command")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
