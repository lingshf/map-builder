# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf

"""Pins the default ``style`` option of the CLI and the Blender add-on (design/tasks/S5-STYLE.md: stylized).

Both definitions are read statically with ``ast``, so no Blender install is needed.
"""

from __future__ import annotations

import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(ROOT, "tools", "mbmap_cli.py")
PROPS_PATH = os.path.join(ROOT, "map_builder", "blender", "props.py")
EXPECTED_STYLE = "stylized"


def parse_module(path: str) -> ast.Module:
    with open(path, encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename=path)


def default_keyword(call: ast.Call) -> str:
    """The literal ``default=`` argument of a call."""
    for keyword in call.keywords:
        if keyword.arg == "default":
            return ast.literal_eval(keyword.value)
    raise AssertionError("call has no default= argument")


def is_style_argument(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and bool(node.args) and ast.literal_eval(node.args[0]) == "--style")


def is_style_property(node: ast.AST) -> bool:
    return (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            and node.target.id == "style" and isinstance(node.annotation, ast.Call))


def only(matches: list):
    assert len(matches) == 1, f"expected exactly one definition, found {len(matches)}"
    return matches[0]


class StyleDefaultTest(unittest.TestCase):
    def test_cli_style_flag_defaults_to_stylized(self) -> None:
        call = only([n for n in ast.walk(parse_module(CLI_PATH)) if is_style_argument(n)])
        self.assertEqual(default_keyword(call), EXPECTED_STYLE)

    def test_blender_style_property_defaults_to_stylized(self) -> None:
        prop = only([n for n in ast.walk(parse_module(PROPS_PATH)) if is_style_property(n)])
        self.assertEqual(default_keyword(prop.annotation), EXPECTED_STYLE)


if __name__ == "__main__":
    unittest.main()
