from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.home import AlcoveHome
from alcove.usage import UsageRecorder


def handle_usage_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: Callable[[argparse.ArgumentParser, str], int],
) -> int:
    home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
    recorder = UsageRecorder(home)
    if args.usage_command == "summary":
        payload = recorder.write_rollups()
    elif args.usage_command == "prune":
        payload = recorder.prune(retention_days=args.days, now=args.now or None)
    else:
        return argument_error(parser, "the following arguments are required: usage_command")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
