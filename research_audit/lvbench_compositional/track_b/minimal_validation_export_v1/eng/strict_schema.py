#!/usr/bin/env python3
"""Minimal Draft-2020-12 subset validator used when the jsonschema package is absent.

Supports: type, properties, required, items, minItems/maxItems, minLength,
additionalProperties, enum, const, pattern, minimum/maximum, $ref (local #/),
anyOf/oneOf, boolean schemas. Uniqueness / join checks live outside this module.
"""
from __future__ import annotations

import re
from typing import Any


class SchemaError(Exception):
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def _type_ok(value: Any, declared: str | list) -> bool:
    types = declared if isinstance(declared, list) else [declared]
    for t in types:
        if t == "object" and isinstance(value, dict):
            return True
        if t == "array" and isinstance(value, list):
            return True
        if t == "string" and isinstance(value, str):
            return True
        if t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if t == "boolean" and isinstance(value, bool):
            return True
        if t == "null" and value is None:
            return True
    return False


def _resolve_ref(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise SchemaError("$ref", f"only local refs supported, got {ref}")
    cur: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        cur = cur[part]
    return cur


def validate(instance: Any, schema: dict, root: dict | None = None, path: str = "$") -> None:
    if root is None:
        root = schema
    if schema is True:
        return
    if schema is False:
        raise SchemaError(path, "false schema rejects all values")
    if not isinstance(schema, dict):
        raise SchemaError(path, "schema must be object or boolean")

    if "$ref" in schema:
        validate(instance, _resolve_ref(root, schema["$ref"]), root, path)
        return

    if "const" in schema and instance != schema["const"]:
        raise SchemaError(path, f"const mismatch: expected {schema['const']!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaError(path, f"value not in enum {schema['enum']}")

    if "type" in schema and not _type_ok(instance, schema["type"]):
        raise SchemaError(path, f"type {schema['type']} mismatch for {type(instance).__name__}")

    if "anyOf" in schema:
        errors = []
        for i, sub in enumerate(schema["anyOf"]):
            try:
                validate(instance, sub, root, f"{path}/anyOf[{i}]")
                break
            except SchemaError as e:
                errors.append(str(e))
        else:
            raise SchemaError(path, "anyOf failed: " + "; ".join(errors[:3]))

    if "oneOf" in schema:
        matched = 0
        for i, sub in enumerate(schema["oneOf"]):
            try:
                validate(instance, sub, root, f"{path}/oneOf[{i}]")
                matched += 1
            except SchemaError:
                pass
        if matched != 1:
            raise SchemaError(path, f"oneOf matched {matched} schemas")

    if isinstance(instance, dict):
        req = schema.get("required") or []
        for key in req:
            if key not in instance:
                raise SchemaError(path, f"missing required property '{key}'")
        props = schema.get("properties") or {}
        addl = schema.get("additionalProperties", True)
        for key, val in instance.items():
            if key in props:
                validate(val, props[key], root, f"{path}.{key}")
            elif addl is False:
                raise SchemaError(path, f"additional property not allowed: {key}")
            elif isinstance(addl, dict):
                validate(val, addl, root, f"{path}.{key}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise SchemaError(path, f"minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise SchemaError(path, f"maxItems {schema['maxItems']}")
        items = schema.get("items")
        if isinstance(items, dict):
            for i, val in enumerate(instance):
                validate(val, items, root, f"{path}[{i}]")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaError(path, f"minLength {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise SchemaError(path, f"pattern {schema['pattern']} failed")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaError(path, f"minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaError(path, f"maximum {schema['maximum']}")


def validate_or_raise(instance: Any, schema: dict) -> None:
    validate(instance, schema, schema, "$")
