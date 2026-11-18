"""Bounded, non-executing reconstruction of simple CPython 3.13 functions."""

from __future__ import annotations

import ast
import dis
import hashlib
import importlib.util
import json
import sys
import types
from dataclasses import dataclass
from typing import Any


class UnsupportedBytecode(ValueError):
    """The supplied code falls outside the explicitly supported subset."""


_MAGIC = bytes.fromhex('f30d0d0a')
_OPERATORS = {'+': ast.Add, '-': ast.Sub, '*': ast.Mult}


@dataclass(frozen=True)
class Reconstruction:
    source: str
    instruction_digest: str
    instruction_count: int
    status: str = 'STRUCTURALLY_RECONSTRUCTED'
    exact_original_source_recovered: bool = False
    execution_authenticated: bool = False


def _runtime_check() -> None:
    if sys.version_info[:2] != (3, 13) or importlib.util.MAGIC_NUMBER != _MAGIC:
        raise UnsupportedBytecode('Only CPython 3.13 bytecode magic f30d0d0a is supported')


def _normalized_instructions(code: types.CodeType) -> tuple[tuple[object, ...], ...]:
    """Compare only the explicitly supported instruction semantics."""
    normalized = []
    for instruction in dis.get_instructions(code, adaptive=False, show_caches=False):
        op = instruction.opname
        if op == 'RESUME':
            normalized.append((op, instruction.arg))
        elif op == 'LOAD_FAST':
            normalized.append((op, instruction.argval))
        elif op == 'LOAD_CONST':
            value = instruction.argval
            normalized.append((op, type(value).__name__, value))
        elif op == 'BINARY_OP':
            normalized.append((op, instruction.argrepr))
        elif op == 'RETURN_VALUE':
            normalized.append((op,))
        else:
            raise UnsupportedBytecode(f'Unsupported round-trip instruction: {op}')
    return tuple(normalized)


def _verify_round_trip(original: types.CodeType, module: ast.Module) -> None:
    """Compile reconstructed AST without executing it; fail closed on mismatch."""
    compiled = compile(module, '<verified-decompiler-roundtrip>', 'exec')
    functions = [value for value in compiled.co_consts if isinstance(value, types.CodeType)]
    if len(functions) != 1:
        raise UnsupportedBytecode('Round-trip did not produce exactly one function')
    rebuilt = functions[0]
    if (original.co_argcount != rebuilt.co_argcount
            or original.co_varnames[:original.co_argcount] != rebuilt.co_varnames[:rebuilt.co_argcount]
            or _normalized_instructions(original) != _normalized_instructions(rebuilt)):
        raise UnsupportedBytecode('Round-trip instruction mismatch')


def reconstruct_function(code: types.CodeType) -> Reconstruction:
    """Reconstruct one simple positional-argument function without executing it.

    This API accepts a code object, not a .pyc file. The digest describes the
    instruction listing, not an authenticated original source artifact.
    """
    _runtime_check()
    if not isinstance(code, types.CodeType):
        raise TypeError('Expected a code object')
    if (code.co_posonlyargcount or code.co_kwonlyargcount or code.co_flags & 0x0C
            or code.co_freevars or code.co_cellvars or code.co_exceptiontable):
        raise UnsupportedBytecode('Unsupported function signature or exception metadata')
    argc = code.co_argcount
    if argc < 1 or argc > 8 or code.co_nlocals != argc:
        raise UnsupportedBytecode('Only 1-8 positional parameters with no extra locals')
    names = code.co_varnames[:argc]
    if len(set(names)) != len(names) or any(not n.isidentifier() for n in names):
        raise UnsupportedBytecode('Invalid parameter names')
    instructions = list(dis.get_instructions(code, adaptive=False, show_caches=False))
    if not instructions or len(instructions) > 64:
        raise UnsupportedBytecode('Instruction count outside supported bounds')
    stack: list[ast.expr] = []
    seen_return = False
    expression: ast.expr | None = None
    for index, instruction in enumerate(instructions):
        op = instruction.opname
        if op == 'RESUME' and index == 0 and instruction.arg == 0:
            continue
        if op == 'LOAD_FAST':
            if instruction.argval not in names:
                raise UnsupportedBytecode('Non-parameter local access')
            stack.append(ast.Name(id=instruction.argval, ctx=ast.Load()))
        elif op == 'LOAD_CONST':
            value = instruction.argval
            if type(value) not in (int, float, bool, str, type(None)):
                raise UnsupportedBytecode('Unsupported constant type')
            if isinstance(value, str) and len(value) > 256:
                raise UnsupportedBytecode('Constant too large')
            stack.append(ast.Constant(value=value))
        elif op == 'BINARY_OP':
            operator = _OPERATORS.get(instruction.argrepr)
            if operator is None or len(stack) < 2:
                raise UnsupportedBytecode('Unsupported binary operation or stack underflow')
            right, left = stack.pop(), stack.pop()
            stack.append(ast.BinOp(left=left, op=operator(), right=right))
        elif op == 'RETURN_VALUE':
            if len(stack) != 1 or index != len(instructions) - 1:
                raise UnsupportedBytecode('Invalid return stack')
            expression = stack.pop()
            seen_return = True
        else:
            raise UnsupportedBytecode(f'Unsupported instruction: {op}')
        if len(stack) > 64:
            raise UnsupportedBytecode('Stack exceeds supported bound')
    if not seen_return or expression is None:
        raise UnsupportedBytecode('Missing return')
    args = ast.arguments(posonlyargs=[], args=[ast.arg(arg=n) for n in names], vararg=None,
                         kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])
    function = ast.FunctionDef(name='reconstructed', args=args, body=[ast.Return(value=expression)],
                               decorator_list=[], returns=None, type_comment=None)
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    _verify_round_trip(code, module)
    source = ast.unparse(module)
    payload = [(i.opname, i.arg, i.argrepr) for i in instructions]
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
    return Reconstruction(source=source, instruction_digest=digest, instruction_count=len(instructions))
