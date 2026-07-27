#!/usr/bin/env python3
"""Auto-provision a Feishu Base, table, and form for the OKS knowledge loop.

Creates:
  1. A Base (or reuses an existing one via --base-token)
  2. A "每日知识采集" table with 28 fields (6 user-visible + 22 worker control)
  3. A form view exposing only the 6 user-visible fields

Uses ``lark-cli`` under the hood.  Requires a working ``lark-cli auth`` session.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ── lark-cli helper ──────────────────────────────────────────────

_LARK_CLI: str | None = None


def _get_lark_cli() -> str:
    """Lazily resolve and cache the lark-cli path. Never fails at import time."""
    global _LARK_CLI
    if _LARK_CLI is not None:
        return _LARK_CLI
    from _lark_cli import resolve_lark_cli

    _LARK_CLI = str(resolve_lark_cli())
    return _LARK_CLI


def _redact_token(token: str) -> str:
    """Show only the first 6 and last 4 characters of a Base token."""
    if len(token) <= 12:
        return token[:2] + "***" + token[-2:]
    return token[:6] + "***" + token[-4:]


def _redact_text(text: str, token: str | None) -> str:
    """Replace every occurrence of *token* in *text* with its redacted form."""
    if not token:
        return text
    return text.replace(token, _redact_token(token))


def _lark(args: list[str], *, timeout: float = 60.0, redact_token: str | None = None) -> dict[str, Any]:
    """Run a lark-cli JSON command and return the parsed result."""
    cmd = [_get_lark_cli(), *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        detail = _redact_text(detail, redact_token)
        raise RuntimeError(
            f"lark-cli {' '.join(args[:2])} 失败 (exit {result.returncode})\n{detail[-2000:]}"
        )
    try:
        return json.loads(result.stdout)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        return {"_raw": result.stdout}


def _lark_text(args: list[str], *, timeout: float = 60.0, redact_token: str | None = None) -> str:
    """Run a lark-cli command and return raw stdout text."""
    cmd = [_get_lark_cli(), *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        detail = _redact_text(detail, redact_token)
        raise RuntimeError(
            f"lark-cli {' '.join(args[:2])} 失败 (exit {result.returncode})\n{detail[-2000:]}"
        )
    return result.stdout


# ── field schema ──────────────────────────────────────────────────

# User-visible fields (shown in the form)
USER_FIELDS: list[dict[str, Any]] = [
    {"name": "内容", "type": "text"},
    {"name": "附件", "type": "attachment"},
    {"name": "思考", "type": "text"},
    {"name": "希望解决的问题", "type": "text"},
    {"name": "评级", "type": "select", "options": [
        {"name": "紧急核心"}, {"name": "重要"}, {"name": "普通参考"}, {"name": "暂不处理"},
    ]},
    {"name": "知识域", "type": "text"},
]

# Worker control fields (hidden from the form)
WORKER_FIELDS: list[dict[str, Any]] = [
    {"name": "运行状态", "type": "select", "options": [
        {"name": "待处理"}, {"name": "探针中"}, {"name": "采集中"}, {"name": "待审核"},
        {"name": "已接受"}, {"name": "已拒绝"}, {"name": "已延迟"}, {"name": "失败"},
        {"name": "跳过"}, {"name": "已完成"},
    ]},
    {"name": "运行ID", "type": "text"},
    {"name": "来源哈希", "type": "text"},
    {"name": "重试", "type": "number"},
    {"name": "租约所有者", "type": "text"},
    {"name": "租约到期", "type": "text"},
    {"name": "Raw Bundle", "type": "text"},
    {"name": "Wiki状态", "type": "select", "options": [
        {"name": "未提交"}, {"name": "草稿中"}, {"name": "已晋升"}, {"name": "不再晋升"},
    ]},
    {"name": "候选ID", "type": "text"},
    {"name": "候选内容", "type": "text"},
    {"name": "审核动作", "type": "select", "options": [
        {"name": "accept"}, {"name": "edit"}, {"name": "reject"}, {"name": "defer"},
    ]},
    {"name": "审核意见", "type": "text"},
    {"name": "修改类型", "type": "text"},
    {"name": "审核时间", "type": "text"},
    {"name": "Wiki路径", "type": "text"},
    {"name": "错误码", "type": "text"},
    {"name": "错误说明", "type": "text"},
    {"name": "采集模式", "type": "select", "options": [
        {"name": "quick"}, {"name": "forensic"},
    ]},
    {"name": "质量状态", "type": "select", "options": [
        {"name": "passed"}, {"name": "partial"}, {"name": "failed"},
    ]},
    {"name": "总结", "type": "text"},
    {"name": "状态", "type": "select", "options": [
        {"name": "active"}, {"name": "archived"},
    ]},
]


# ── main setup logic ──────────────────────────────────────────────

def setup(args: argparse.Namespace) -> int:
    base_token = args.base_token or os.environ.get("OKS_FEISHU_BASE_TOKEN")
    table_name = args.table_name or "每日知识采集"
    show_credentials = bool(args.show_credentials)

    # ── Step 1: create or reuse Base ──
    if base_token:
        print(f"[1/4] 使用已有 Base: {_redact_token(base_token)}")
        _existing = _lark(["base", "+base-get", "--base-token", base_token], redact_token=base_token)
        base_name = _existing.get("name", "OKS Base")
    else:
        base_name = args.base_name or "Open Knowledge Studio"
        print(f"[1/4] 创建 Base: {base_name}")
        result = _lark([
            "base", "+base-create",
            "--name", base_name,
            "--table-name", table_name,
            "--fields", json.dumps(USER_FIELDS[:2], ensure_ascii=False),  # first 2 fields as bootstrap
            "--time-zone", "Asia/Shanghai",
            "--format", "json",
        ])
        base_token = result.get("base_token") or result.get("base", {}).get("base_token")
        if not base_token:
            raise RuntimeError(f"无法获取 base_token: {json.dumps(result, ensure_ascii=False)}")
        permission = result.get("permission_grant", "")
        if permission:
            print(f"  权限提示: {permission}")

    if not base_token:
        raise RuntimeError("无法确定 Base token")

    # ── Step 2: find or create the capture table ──
    print(f"[2/4] 定位/创建采集表: {table_name}")
    tables = _lark(["base", "+table-list", "--base-token", base_token], redact_token=base_token)
    table_list = tables if isinstance(tables, list) else (
        tables.get("data", {}).get("tables", []) or tables.get("items", [])
    )
    table_id = None
    for t in table_list:
        if isinstance(t, dict) and t.get("name") == table_name:
            table_id = t.get("id") or t.get("table_id")
            break

    if table_id:
        print(f"  表已存在: {table_id}")
        existing_fields = _lark([
            "base", "+field-list", "--base-token", base_token, "--table-id", table_id,
        ], redact_token=base_token)
        field_list = existing_fields if isinstance(existing_fields, list) else (
            existing_fields.get("data", {}).get("fields", []) or existing_fields.get("items", [])
        )
        existing_names = {
            f.get("name") or f.get("field_name", "")
            for f in field_list
        }
    else:
        # Create table with initial fields
        result = _lark([
            "base", "+table-create",
            "--base-token", base_token,
            "--name", table_name,
            "--fields", json.dumps(USER_FIELDS[:6], ensure_ascii=False),
            "--format", "json",
        ], redact_token=base_token)
        table_id = result.get("table_id")
        if not table_id:
            raise RuntimeError(f"无法获取 table_id: {json.dumps(result, ensure_ascii=False)}")
        print(f"  表已创建: {table_id}")
        existing_names = {f["name"] for f in USER_FIELDS[:6]}

    # ── Step 3: ensure all 28 fields exist ──
    print("[3/4] 确保 28 个控制字段...")
    all_fields = USER_FIELDS + WORKER_FIELDS
    created = 0
    for field in all_fields:
        if field["name"] in existing_names:
            continue
        field_json = dict(field)
        if "description" in field_json:
            del field_json["description"]  # not in field-create
        try:
            _lark([
                "base", "+field-create",
                "--base-token", base_token,
                "--table-id", table_id,
                "--json", json.dumps(field_json, ensure_ascii=False),
            ], redact_token=base_token)
            created += 1
            print(f"  + {field['name']}")
        except RuntimeError as exc:
            print(f"  ! {field['name']}: {_redact_text(str(exc), base_token)}")
    if created:
        print(f"  新增 {created} 个字段")
    else:
        print("  所有字段已就绪")

    # ── Step 4: create form ──
    print("[4/4] 创建表单视图...")
    form_result = _lark([
        "base", "+form-create",
        "--base-token", base_token,
        "--table-id", table_id,
        "--name", f"{table_name} - 采集表单",
        "--description", "[OKS 知识采集] 提交链接或内容，Agent 会自动解析并汇报。",
        "--format", "json",
    ], redact_token=base_token)
    form_data = form_result.get("data", {}) or form_result
    form_id = form_data.get("form_id") or form_data.get("id") or form_result.get("form_id", "")

    # ── output configuration ──
    display_token = base_token if show_credentials else _redact_token(base_token)
    print()
    print("=" * 60)
    print("飞书配置完成。请将以下内容设置为环境变量：")
    print()
    print(f"  $env:OKS_FEISHU_BASE_TOKEN = \"{display_token}\"")
    print(f"  $env:OKS_FEISHU_TABLE_ID   = \"{table_id}\"")
    if form_id:
        print(f"  # Form ID: {form_id}")
    print()
    print("或写入 ~/.oks/config.json:")
    print(json.dumps({
        "feishu": {
            "base_token": display_token,
            "table_id": table_id,
            "table_name": table_name,
            "form_id": form_id,
        }
    }, ensure_ascii=False, indent=2))
    if not show_credentials:
        print()
        print("  [提示] 使用 --show-credentials 查看完整 Base token。")
    print("=" * 60)

    return 0


# ── CLI ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oks feishu setup",
        description="自动创建飞书 Base、采集表和表单，用于 OKS 知识闭环。",
    )
    parser.add_argument("--base-token", help="已有 Base token（跳过创建 Base）")
    parser.add_argument("--base-name", default="Open Knowledge Studio", help="新建 Base 的名称")
    parser.add_argument("--table-name", default="每日知识采集", help="采集表名称")
    parser.add_argument("--time-zone", default="Asia/Shanghai")
    parser.add_argument(
        "--show-credentials",
        action="store_true",
        help="Display the full Base token in output instead of the default redacted form",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(setup(build_parser().parse_args()))
