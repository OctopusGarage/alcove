from __future__ import annotations

from typing import Any


def print_install_result(result: dict[str, Any]) -> None:
    if result.get("profile"):
        print(f"profile: {result['profile']}")
    if result.get("home"):
        print(f"home: {result['home']}")
    if result.get("kb"):
        print(f"kb: {result['kb']}")
    if result.get("path"):
        print(f"path: {result['path']}")
    if result.get("workspace"):
        print(f"workspace: {result['workspace']}")
    publisher = result.get("publisher")
    if isinstance(publisher, dict):
        print(f"publisher: {publisher.get('publisher')} | {publisher.get('status')}")
    service = result.get("service")
    if isinstance(service, dict):
        print(f"service: {service.get('status')} | {', '.join(service.get('targets', []))}")
    for file in result.get("files", []):
        action = file.get("action")
        if action is None:
            action = "installed" if file.get("installed") else "not_found"
        target = file.get("target") or "file"
        print(f"{target} | {action} | {file['path']}")
