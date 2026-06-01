"""
el_parser.py
============
Core parsing entry-point for DSL-EL.

Loads el_grammar.tx via textX, creates a metamodel, and exposes
a clean parse() function that returns a validated, typed model.

Usage
-----
    from el_parser import parse, ParseResult

    result = parse("my_spec.el")
    if result.ok:
        spec = result.model
    else:
        for err in result.errors:
            print(err)

Dependencies
------------
    pip install textX
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

try:
    from textx import metamodel_from_file
    from textx.exceptions import TextXError, TextXSemanticError, TextXSyntaxError
except ImportError as exc:
    raise ImportError(
        "textX is required: pip install textX"
    ) from exc

# ── Path resolution ──────────────────────────────────────────────────────────

_HERE = Path(__file__).parent
GRAMMAR_PATH = _HERE / "el_grammar.tx"


# ── Result type ──────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    """Holds a parsed model or a list of error strings."""
    model: Optional[Any] = None
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ── Metamodel builder ─────────────────────────────────────────────────────────

def _build_metamodel():
    """
    Build the textX metamodel from the grammar file.

    textX options used:
      auto_init_obj  — textX pre-populates list attributes to []
                        so validators never see None for empty lists.
      global_model_params — exposed to custom obj processors if needed.
    """
    mm = metamodel_from_file(str(GRAMMAR_PATH))
    return mm


_METAMODEL = None   # lazy singleton


def _get_metamodel():
    global _METAMODEL
    if _METAMODEL is None:
        _METAMODEL = _build_metamodel()
    return _METAMODEL


# ── Public API ────────────────────────────────────────────────────────────────

def parse(source: str | Path, *, validate: bool = True) -> ParseResult:
    """
    Parse a DSL-EL specification file.

    Parameters
    ----------
    source   : path to a .el file OR a raw string containing EL text.
    validate : run semantic validation after parsing (recommended).

    Returns
    -------
    ParseResult with .model (EnterpriseSpec) on success, or .errors list.
    """
    mm = _get_metamodel()
    result = ParseResult()

    try:
        if isinstance(source, (str, Path)) and os.path.isfile(str(source)):
            model = mm.model_from_file(str(source))
        else:
            model = mm.model_from_str(str(source))
    except TextXSyntaxError as exc:
        result.errors.append(f"[SYNTAX] {exc}")
        return result
    except TextXSemanticError as exc:
        result.errors.append(f"[SEMANTIC] {exc}")
        return result
    except TextXError as exc:
        result.errors.append(f"[PARSE ERROR] {exc}")
        return result

    result.model = model

    if validate:
        from el_validator import validate_spec
        semantic_errors = validate_spec(model)
        result.errors.extend(semantic_errors)

    return result


def parse_string(text: str, *, validate: bool = True) -> ParseResult:
    """Convenience wrapper for in-memory EL text."""
    return parse(text, validate=validate)


# ── Model introspection helpers ───────────────────────────────────────────────

def collect(model, cls_name: str) -> List[Any]:
    """
    Collect all objects of a given class name from the flat element list.

    Works on an EnterpriseSpec model returned by parse().
    """
    return [
        e for e in model.elements
        if type(e).__name__ == cls_name
    ]


def find_by_name(model, cls_name: str, name: str) -> Optional[Any]:
    """Return the first element of cls_name whose .name == name."""
    for e in collect(model, cls_name):
        if getattr(e, "name", None) == name:
            return e
    return None


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("Usage: python el_parser.py <spec.el>")
        sys.exit(1)

    result = parse(sys.argv[1])
    if result.ok:
        spec = result.model
        print(f"✓ Parsed '{spec.name}' successfully.")
        print(f"  Elements: {len(spec.elements)}")
        counts = {}
        for e in spec.elements:
            t = type(e).__name__
            counts[t] = counts.get(t, 0) + 1
        for t, n in sorted(counts.items()):
            print(f"    {t}: {n}")
    else:
        print("✗ Parse/validation errors:")
        for err in result.errors:
            print(f"  {err}")
        sys.exit(1)
