from __future__ import annotations

from typing import Any


TASK_HEALTH_NOTIFICATION_VERSION = 3


def build_task_health_summary(payload: dict[str, Any]) -> dict[str, Any]:
    checks = [
        _module_health(
            module="connectors",
            payload=_dict_value(payload.get("connectors")),
            metrics=("refreshed", "skipped", "errors"),
            error_key="errors",
        ),
        _module_health(
            module="watchers",
            payload=_dict_value(payload.get("watchers")),
            metrics=("checked", "changed", "errors"),
            error_key="errors",
        ),
        _module_health(
            module="blogs",
            payload=_dict_value(payload.get("blogs")),
            metrics=("checked", "new", "errors"),
            error_key="errors",
        ),
        _module_health(
            module="radars",
            payload=_dict_value(payload.get("radars")),
            metrics=("ran", "skipped", "errors"),
            error_key="errors",
        ),
        _module_health(
            module="automations",
            payload=_dict_value(payload.get("automations")),
            metrics=("ran", "skipped", "failed"),
            error_key="failed",
        ),
        _module_health(
            module="publishers",
            payload=_dict_value(payload.get("publishers")),
            metrics=("ran", "updated", "errors"),
            error_key="errors",
        ),
        _module_health(
            module="mounts",
            payload=_dict_value(payload.get("mounts")),
            metrics=("checked", "refreshed", "skipped"),
            error_key="errors",
        ),
        _health_module_summary(_dict_value(payload.get("health"))),
    ]
    failed = [check for check in checks if check["status"] == "failed"]
    skipped = [check for check in checks if check["status"] == "skipped"]
    return {
        "status": "failed" if failed else "success",
        "checked": len(checks),
        "failed": len(failed),
        "skipped": len(skipped),
        "checks": checks,
    }


def task_health_notification_text(task_health: dict[str, Any], *, day: str) -> str:
    status_label = _task_health_status_label(str(task_health.get("status") or "unknown"))
    lines = [
        f"Alcove 任务健康 · {day}",
        "",
        f"整体状态：{status_label}",
        f"已检查模块：{_int_value(task_health.get('checked'))} 个；失败：{_int_value(task_health.get('failed'))} 个；跳过：{_int_value(task_health.get('skipped'))} 个。",
        "",
        "模块结果：",
    ]
    for check in task_health.get("checks", []):
        if not isinstance(check, dict):
            continue
        lines.append(_task_health_check_line(check))
    return "\n".join(lines)


def task_health_notification_was_sent_today(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        value.get("status") == "sent"
        and _int_value(value.get("version")) == TASK_HEALTH_NOTIFICATION_VERSION
    )


def task_health_notification_should_send(value: Any, task_health: dict[str, Any]) -> bool:
    if not task_health_notification_was_sent_today(value):
        return True
    if not isinstance(value, dict):
        return True
    previous_status = str(value.get("task_health_status") or "")
    current_status = str(task_health.get("status") or "unknown")
    return bool(previous_status and current_status and previous_status != current_status)


def _module_health(
    *,
    module: str,
    payload: dict[str, Any],
    metrics: tuple[str, ...],
    error_key: str,
) -> dict[str, Any]:
    status = str(payload.get("status") or "unknown")
    error_count = _int_value(payload.get(error_key))
    task_status = "skipped" if status == "skipped" else "failed" if error_count > 0 else "success"
    if (
        module == "radars"
        and task_status == "success"
        and _int_value(payload.get("ran")) == 0
        and _int_value(payload.get("skipped")) > 0
    ):
        task_status = (
            "skipped"
            if not isinstance(payload.get("radars"), list)
            or not payload["radars"]
            or _skipped_radars_without_last_success(payload)
            else "success"
        )
    skipped_without_success = (
        _skipped_radars_without_last_success(payload) if module == "radars" else 0
    )
    if skipped_without_success:
        task_status = "failed"
    summary = " ".join(f"{key}={_int_value(payload.get(key))}" for key in metrics)
    record: dict[str, Any] = {
        "module": module,
        "status": task_status,
        "summary": summary,
    }
    if task_status == "failed":
        if skipped_without_success:
            details = _radar_skip_errors(payload)
            record["error"] = (
                f"radars skipped without last successful run: {skipped_without_success}"
            )
            if details:
                record["error"] += f" ({details})"
        else:
            record["error"] = f"{module} reported {error_key}={error_count}"
    return record


def _health_module_summary(payload: dict[str, Any]) -> dict[str, Any]:
    issue_count = _int_value(payload.get("issue_count"))
    action_count = _int_value(payload.get("action_count"))
    status = "failed" if issue_count > 0 else "success"
    record: dict[str, Any] = {
        "module": "health",
        "status": status,
        "summary": f"issues={issue_count} actions={action_count}",
    }
    if status == "failed":
        record["error"] = f"health reported issue_count={issue_count}"
    return record


def _task_health_status_label(status: str) -> str:
    labels = {
        "success": "健康",
        "failed": "需要处理",
        "skipped": "已跳过",
    }
    return labels.get(status, status or "未知")


def _task_health_check_line(check: dict[str, Any]) -> str:
    module_key = str(check.get("module") or "module")
    module = _task_health_module_label(module_key)
    status = str(check.get("status") or "unknown")
    status_label = {
        "success": "正常",
        "failed": "异常",
        "skipped": "跳过",
    }.get(status, status or "未知")
    if module_key == "radars":
        line = (
            f"- {module}：{status_label} · "
            f"{_radar_task_health_summary(status, str(check.get('summary') or ''))}"
        )
        if status == "failed" and check.get("error"):
            line += f" · {check['error']}"
        return line

    if status == "skipped":
        return f"- {module}：{status_label}"

    detail = _task_health_summary_text(str(check.get("summary") or ""))
    return f"- {module}：{status_label}{f' · {detail}' if detail else ''}"


def _task_health_module_label(module: str) -> str:
    labels = {
        "connectors": "连接器",
        "watchers": "监听器",
        "blogs": "博客监控",
        "radars": "雷达",
        "automations": "自动化",
        "publishers": "发布器",
        "mounts": "挂载索引",
        "health": "健康检查",
    }
    return labels.get(module, module)


def _task_health_summary_text(summary: str) -> str:
    labels = {
        "refreshed": "已刷新",
        "skipped": "跳过",
        "errors": "错误",
        "checked": "已检查",
        "changed": "变更",
        "new": "新增",
        "ran": "运行",
        "failed": "失败",
        "updated": "更新",
        "issues": "问题",
        "actions": "修复动作",
    }
    values = _task_health_summary_values(summary)
    return "；".join(
        f"{labels.get(key, key)} {_int_value(value)} 个" for key, value in values.items()
    )


def _radar_task_health_summary(status: str, summary: str) -> str:
    values = _task_health_summary_values(summary)
    errors = _int_value(values.get("errors"))
    ran = _int_value(values.get("ran"))
    skipped = _int_value(values.get("skipped"))
    if status == "skipped":
        return f"本轮未执行；本轮运行 {ran} 个；跳过 {skipped} 个；错误 {errors} 个"
    run_state = "本轮运行异常" if status == "failed" or errors > 0 else "本轮运行成功"
    return f"{run_state}；本轮运行 {ran} 个；错误 {errors} 个"


def _task_health_summary_values(summary: str) -> dict[str, str]:
    values = {}
    for item in summary.split():
        key, separator, value = item.partition("=")
        if separator != "=":
            continue
        values[key] = value
    return values


def _skipped_radars_without_last_success(payload: dict[str, Any]) -> int:
    rows = payload.get("radars")
    if not isinstance(rows, list):
        return 0
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") != "skipped":
            continue
        if row.get("last_run_success") is not False:
            continue
        count += 1
    return count


def _radar_skip_errors(payload: dict[str, Any]) -> str:
    rows = payload.get("radars")
    if not isinstance(rows, list):
        return ""
    details = []
    for row in rows:
        if not isinstance(row, dict) or row.get("last_run_success") is not False:
            continue
        radar_id = str(row.get("id") or "radar")
        if not row.get("last_run_error"):
            continue
        error = str(row["last_run_error"])
        details.append(f"{radar_id}: {error}")
    return "; ".join(details)


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
