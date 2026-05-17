"""Validated execution of deterministic chat tools."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from chat.tool_registry import TOOLS
from db.schema import ToolCall, ToolExecutionResult


def _coerce_arguments(tool_name: str, args: dict) -> dict:
    """Validate and coerce runtime arguments based on the tool schema."""
    definition = TOOLS[tool_name]
    schema = definition.arguments_schema
    out: dict = {}
    for arg_name, arg_spec in schema.items():
        required = bool(arg_spec.get("required", False))
        if arg_name not in args:
            if required and "default" not in arg_spec:
                raise ValueError(f"Missing required argument: {arg_name}")
            if "default" in arg_spec:
                out[arg_name] = arg_spec["default"]
            continue
        raw_value = args[arg_name]
        arg_type = arg_spec.get("type")
        if arg_type == "integer":
            value = int(raw_value)
            if "min" in arg_spec and value < int(arg_spec["min"]):
                raise ValueError(f"Argument {arg_name} must be >= {arg_spec['min']}")
            out[arg_name] = value
        elif arg_type == "number":
            value = float(raw_value)
            if "min" in arg_spec and value < float(arg_spec["min"]):
                raise ValueError(f"Argument {arg_name} must be >= {arg_spec['min']}")
            out[arg_name] = value
        elif arg_type == "string":
            value = str(raw_value)
            if required and not value.strip():
                raise ValueError(f"Argument {arg_name} cannot be empty")
            out[arg_name] = value
        elif arg_type == "array":
            if isinstance(raw_value, str):
                try:
                    value = json.loads(raw_value)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Argument {arg_name} must be an array") from exc
            else:
                value = raw_value
            if not isinstance(value, list):
                raise ValueError(f"Argument {arg_name} must be an array")
            if "min_items" in arg_spec and len(value) < int(arg_spec["min_items"]):
                raise ValueError(f"Argument {arg_name} must have at least {arg_spec['min_items']} items")
            item_type = (arg_spec.get("items") or {}).get("type")
            if item_type == "string":
                value = [str(item) for item in value]
            out[arg_name] = value
        else:
            out[arg_name] = raw_value
    return out


def execute_tool_call(db: Session, tool_call: ToolCall) -> ToolExecutionResult:
    """Execute one registered deterministic tool call."""
    if tool_call.tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {tool_call.tool_name}")
    args = _coerce_arguments(tool_call.tool_name, tool_call.arguments)
    definition = TOOLS[tool_call.tool_name]
    return definition.function(db=db, **args)
