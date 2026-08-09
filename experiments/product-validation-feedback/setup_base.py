"""Create the one-off OKS product-validation feedback Base and form.

This is owner-side experiment setup, intentionally outside the OKS package.
It creates no records and never changes an OKS instance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


BASE_NAME = "OKS 产品验证反馈"
TABLE_NAME = "OKS 产品验证反馈"
FIELDS: tuple[dict[str, Any], ...] = (
    {
        "name": "本次希望 OKS 完成什么",
        "type": "text",
        "required": True,
        "description": "请用自己的话描述这次希望 OKS 帮你完成什么。",
    },
    {
        "name": "Agent 运行信息",
        "type": "text",
        "required": False,
        "description": "可选：可粘贴简短事实；不要包含来源原文、URL、原始查询或凭据。",
    },
    {
        "name": "最终结果是否符合预期",
        "type": "select",
        "required": True,
        "multiple": False,
        "options": [{"name": value} for value in ("符合预期", "部分符合预期", "不符合预期")],
    },
    {
        "name": "Candidate Review 是否可判断",
        "type": "select",
        "required": True,
        "multiple": False,
        "options": [{"name": value} for value in ("能判断", "有点拿不准", "不能判断", "本轮没有 Review")],
    },
    {
        "name": "Guided Decision 体验",
        "type": "select",
        "required": True,
        "multiple": False,
        "options": [{"name": value} for value in ("有帮助", "一般", "有点打扰", "更困惑", "本轮没遇到")],
    },
    {
        "name": "Recall 结果",
        "type": "select",
        "required": True,
        "multiple": False,
        "options": [{"name": value} for value in ("找到且有帮助", "找到但帮助不大", "部分找到", "没找到", "本轮未使用")],
    },
    {
        "name": "其他反馈",
        "type": "text",
        "required": False,
        "description": "可选：最不舒服、最困惑或最希望改进的地方。",
    },
)


def _base_field(field: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in field.items() if key != "required"}


def _collection(payload: dict[str, Any] | list[Any], key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    values = data.get(key) or payload.get(key) or payload.get("items") or []
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def _first_value(payload: dict[str, Any], *keys: str) -> str:
    queue: list[Any] = [payload]
    while queue:
        current = queue.pop(0)
        if not isinstance(current, dict):
            continue
        for key in keys:
            value = current.get(key)
            if isinstance(value, str) and value:
                return value
        queue.extend(value for value in current.values() if isinstance(value, dict))
    raise RuntimeError(f"lark-cli response missing {' / '.join(keys)}")


def _lark_cli(explicit: str | None) -> str:
    if explicit:
        return explicit
    executable = shutil.which("lark-cli.cmd") or shutil.which("lark-cli")
    if not executable:
        raise RuntimeError("找不到 lark-cli；请安装并完成用户授权后再运行。")
    return executable


def _run(executable: str, arguments: list[str]) -> dict[str, Any] | list[Any]:
    environment = os.environ.copy()
    volta = Path(r"C:\Program Files\Volta")
    if volta.is_dir():
        environment["PATH"] = str(volta) + os.pathsep + environment.get("PATH", "")
    environment["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
    environment["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
    completed = subprocess.run(
        [executable, *arguments], capture_output=True, text=True, encoding="utf-8",
        env=environment, check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "lark-cli failed").strip()
        raise RuntimeError(f"lark-cli {' '.join(arguments[:2])} 失败：{detail[-500:]}")
    try:
        result = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("lark-cli 没有返回 JSON") from exc
    if not isinstance(result, (dict, list)):
        raise RuntimeError("lark-cli 返回了不支持的 JSON 结构")
    return result


def _form_question(field: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in field.items()
        if key in {"type", "required", "description", "multiple", "options"}
    } | {"title": field["name"]}


def ensure_form_questions(executable: str, base_token: str, table_id: str, form_id: str) -> None:
    """Make a fresh form expose exactly the seven intended prompts."""
    command = [
        "base", "+form-questions-list", "--base-token", base_token,
        "--table-id", table_id, "--form-id", form_id, "--format", "json",
    ]
    existing = _collection(_run(executable, command), "questions")
    known = {str(question.get("title")): question for question in existing if question.get("title")}
    missing_fields = [field for field in FIELDS if field["name"] not in known]
    table_fields = _collection(_run(executable, [
        "base", "+field-list", "--base-token", base_token,
        "--table-id", table_id, "--format", "json",
    ]), "fields")
    existing_field_names = {str(field.get("name")) for field in table_fields if field.get("name")}
    already_unbound = [field["name"] for field in missing_fields if field["name"] in existing_field_names]
    if already_unbound:
        joined = "、".join(already_unbound)
        raise RuntimeError(
            f"表单缺少已存在的字段：{joined}。lark-cli 新增表单题会另建字段；"
            "为避免重复，请在飞书 UI 将这些字段加入表单后再续跑。"
        )

    missing = [_form_question(field) for field in missing_fields]
    if missing:
        _run(executable, [
            "base", "+form-questions-create", "--base-token", base_token,
            "--table-id", table_id, "--form-id", form_id,
            "--questions", json.dumps(missing, ensure_ascii=False), "--format", "json",
        ])
        existing = _collection(_run(executable, command), "questions")
        known = {str(question.get("title")): question for question in existing if question.get("title")}

    expected_names = {field["name"] for field in FIELDS}
    question_names = set(known)
    if question_names != expected_names:
        raise RuntimeError("表单题目与 7 个产品验证字段不一致，已停止以避免写入额外字段。")

    final_fields = _collection(_run(executable, [
        "base", "+field-list", "--base-token", base_token,
        "--table-id", table_id, "--format", "json",
    ]), "fields")
    final_field_names = {str(field.get("name")) for field in final_fields if field.get("name")}
    if final_field_names != expected_names:
        raise RuntimeError("反馈表字段与 7 个产品验证字段不一致，已停止以避免保留额外字段。")

    updates = [
        {"id": question["id"], "required": bool(field["required"])}
        for field in FIELDS
        if (question := known.get(field["name"]))
        and bool(question.get("required", False)) != bool(field["required"])
    ]
    if updates:
        _run(executable, [
            "base", "+form-questions-update", "--base-token", base_token,
            "--table-id", table_id, "--form-id", form_id,
            "--questions", json.dumps(updates, ensure_ascii=False), "--format", "json",
        ])


def create_base(executable: str) -> dict[str, str]:
    auth = _run(executable, ["auth", "status", "--json", "--verify"])
    if isinstance(auth, dict) and "verified" in auth and auth.get("verified") is not True:
        raise RuntimeError("飞书用户授权未完成；请先完成 lark-cli auth login。")

    created = _run(executable, [
        "base", "+base-create", "--name", BASE_NAME, "--table-name", TABLE_NAME,
        "--fields", json.dumps([_base_field(FIELDS[0])], ensure_ascii=False),
        "--time-zone", "Asia/Shanghai", "--format", "json",
    ])
    if not isinstance(created, dict):
        raise RuntimeError("创建 Base 后没有返回对象响应")
    base_token = _first_value(created, "base_token")

    tables = _collection(_run(executable, ["base", "+table-list", "--base-token", base_token]), "tables")
    table_id = next((str(item.get("table_id") or item.get("id")) for item in tables if item.get("name") == TABLE_NAME), "")
    if not table_id:
        raise RuntimeError("创建后无法定位反馈表")

    form = _run(executable, [
        "base", "+form-create", "--base-token", base_token, "--table-id", table_id,
        "--name", TABLE_NAME, "--description", "OKS 产品验证反馈：请只填写本次真实使用体验。",
        "--format", "json",
    ])
    if not isinstance(form, dict):
        raise RuntimeError("创建表单后没有返回对象响应")
    form_id = _first_value(form, "form_id", "id")
    ensure_form_questions(executable, base_token, table_id, form_id)
    return {"base_token": base_token, "table_id": table_id, "form_id": form_id}


def main() -> int:
    parser = argparse.ArgumentParser(description="创建独立的 OKS 产品验证反馈 Base 和表单。")
    parser.add_argument("--lark-cli", help="可用的 lark-cli 可执行文件路径")
    parser.add_argument("--resume-base-token", help="续跑已创建但未完成的反馈 Base")
    parser.add_argument("--resume-table-id", help="续跑时的反馈表 ID")
    parser.add_argument("--resume-form-id", help="续跑时的表单 ID")
    args = parser.parse_args()
    try:
        executable = _lark_cli(args.lark_cli)
        resume = (args.resume_base_token, args.resume_table_id, args.resume_form_id)
        if any(resume) and not all(resume):
            raise RuntimeError("续跑需要同时提供 --resume-base-token、--resume-table-id 和 --resume-form-id。")
        if all(resume):
            ensure_form_questions(executable, *resume)
            result = {"table_id": args.resume_table_id, "form_id": args.resume_form_id}
        else:
            result = create_base(executable)
    except RuntimeError as exc:
        print(f"初始化失败：{exc}")
        return 2
    print("已创建 OKS 产品验证反馈表和 7 字段表单。")
    print("下一步：在飞书 UI 打开该表单 → 分享 → 开启持链接可填写。")
    print("公开表单链接已配置进 skills/oks-feedback/SKILL.md；如重新生成链接，再更新该文件中的一行。")
    print(json.dumps({"table_id": result["table_id"], "form_id": result["form_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
