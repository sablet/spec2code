#!/usr/bin/env python3
"""Simple static call graph explorer for the spec2code project.

The script walks the Python sources, builds an approximate call graph,
then reports symbols (functions, methods, and classes) that are not
reachable from a given set of entry points (by default: the ``main``
module).

The analysis is conservative and intentionally simple: dynamic dispatch,
reflection, and many metaprogramming constructs are not resolved.  The
goal is to highlight likely dead code candidates that deserve a manual
review rather than provide mathematically precise results.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, Literal, Optional, Set

DEFAULT_IGNORED_SYMBOLS: Set[str] = {
    "packages.spec2code.engine.Check",
    "packages.spec2code.engine.Check.__class_getitem__",
    "packages.spec2code.engine.ExampleValue",
    "packages.spec2code.engine.ExampleValue.__class_getitem__",
}


@dataclass(frozen=True)
class Definition:
    """Represents a declared symbol."""

    symbol: str
    kind: Literal["module", "class", "function", "method"]
    module: str
    name: str
    filepath: Path
    lineno: int


@dataclass(frozen=True)
class AliasTarget:
    """Tracks import targets for alias resolution."""

    kind: Literal["module", "symbol"]
    target: str


class CallGraphBuilder:
    """Collects symbol definitions and the call graph between them."""

    def __init__(self) -> None:
        self.definitions: Dict[str, Definition] = {}
        self.edges: Dict[str, Set[str]] = defaultdict(set)
        self.class_methods: Dict[str, Set[str]] = defaultdict(set)
        self.class_attribute_types: Dict[str, Dict[str, str]] = defaultdict(dict)

    def add_definition(
        self,
        symbol: str,
        kind: Literal["module", "class", "function", "method"],
        *,
        module: str,
        name: str,
        filepath: Path,
        lineno: int,
    ) -> None:
        if symbol not in self.definitions:
            self.definitions[symbol] = Definition(
                symbol=symbol,
                kind=kind,
                module=module,
                name=name,
                filepath=filepath,
                lineno=lineno,
            )

    def add_edge(self, source: str, target: str) -> None:
        if not source or not target or source == target:
            return
        self.edges[source].add(target)

    def register_method(self, class_symbol: str, method_symbol: str) -> None:
        self.class_methods[class_symbol].add(method_symbol)

    def register_class_attribute(self, class_symbol: str, attribute: str, type_symbol: str) -> None:
        if not class_symbol or not attribute or not type_symbol:
            return
        self.class_attribute_types[class_symbol][attribute] = type_symbol

    def finalize(self) -> None:
        """Add containment edges (class -> method) after parsing."""
        for class_symbol, methods in self.class_methods.items():
            if methods:
                self.edges[class_symbol].update(methods)


class ModuleAnalyzer(ast.NodeVisitor):
    """AST visitor that records symbol definitions and call relations."""

    def __init__(
        self,
        builder: CallGraphBuilder,
        filepath: Path,
        module_name: str,
        tree: ast.Module,
    ) -> None:
        self.builder = builder
        self.filepath = filepath
        self.module = module_name

        self.aliases: Dict[str, AliasTarget] = {}
        self.scope_stack: list[dict[str, str]] = [dict()]
        self.function_stack: list[str] = []
        self.class_stack: list[str] = []
        self.local_types_stack: list[dict[str, str]] = [dict()]

        self.builder.add_definition(
            module_name,
            "module",
            module=module_name,
            name=module_name.rsplit(".", 1)[-1],
            filepath=filepath,
            lineno=1,
        )

        self._prefill_module_scope(tree)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def current_symbol(self) -> str:
        if self.function_stack:
            return self.function_stack[-1]
        if self.class_stack:
            return self.class_stack[-1]
        return self.module

    def current_class_symbol(self) -> Optional[str]:
        return self.class_stack[-1] if self.class_stack else None

    def lookup_symbol(self, name: str) -> Optional[str]:
        for scope in reversed(self.scope_stack):
            if name in scope:
                return scope[name]
        return None

    # ------------------------------------------------------------------
    # Import handling
    # ------------------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            alias_name = alias.asname or alias.name
            self.aliases[alias_name] = AliasTarget("module", alias.name)
            if not alias.asname and "." in alias.name:
                root_name = alias.name.split(".", 1)[0]
                self.aliases.setdefault(root_name, AliasTarget("module", root_name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module_path = resolve_relative_module(self.module, node.module, node.level)
        for alias in node.names:
            if alias.name == "*":
                continue
            alias_name = alias.asname or alias.name
            target = f"{module_path}.{alias.name}" if module_path else alias.name
            self.aliases[alias_name] = AliasTarget("symbol", target)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Definition handling
    # ------------------------------------------------------------------
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_symbol = f"{self.module}.{node.name}"
        self.builder.add_definition(
            class_symbol,
            "class",
            module=self.module,
            name=node.name,
            filepath=self.filepath,
            lineno=node.lineno,
        )
        self.scope_stack[-1][node.name] = class_symbol

        # decorators reference
        for decorator in node.decorator_list:
            for ref in self._collect_symbol_refs(decorator):
                self.builder.add_edge(self.current_symbol(), ref)

        self.class_stack.append(class_symbol)
        self.scope_stack.append(dict())
        self.local_types_stack.append(dict())

        self.generic_visit(node)

        self.local_types_stack.pop()
        self.scope_stack.pop()
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function_like(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function_like(node)

    def _handle_function_like(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        class_symbol = self.current_class_symbol()
        if class_symbol:
            symbol = f"{class_symbol}.{node.name}"
            kind: Literal["function", "method"] = "method"
            self.builder.register_method(class_symbol, symbol)
        else:
            symbol = f"{self.module}.{node.name}"
            kind = "function"

        self.builder.add_definition(
            symbol,
            kind,
            module=self.module,
            name=node.name,
            filepath=self.filepath,
            lineno=node.lineno,
        )
        self.scope_stack[-1][node.name] = symbol

        annotations: list[ast.AST] = []
        args = node.args
        for arg in getattr(args, "posonlyargs", []):
            if arg.annotation:
                annotations.append(arg.annotation)
        for arg in args.args:
            if arg.annotation:
                annotations.append(arg.annotation)
        for arg in args.kwonlyargs:
            if arg.annotation:
                annotations.append(arg.annotation)
        if args.vararg and args.vararg.annotation:
            annotations.append(args.vararg.annotation)
        if args.kwarg and args.kwarg.annotation:
            annotations.append(args.kwarg.annotation)
        if node.returns:
            annotations.append(node.returns)

        for annotation in annotations:
            for ref in self._collect_symbol_refs(annotation):
                self.builder.add_edge(symbol, ref)

        for decorator in node.decorator_list:
            for ref in self._collect_symbol_refs(decorator):
                self.builder.add_edge(self.current_symbol(), ref)

        self.function_stack.append(symbol)
        self.scope_stack.append(dict())
        self.local_types_stack.append(dict())

        self.generic_visit(node)

        self.local_types_stack.pop()
        self.scope_stack.pop()
        self.function_stack.pop()

    # ------------------------------------------------------------------
    # Calls and symbol references
    # ------------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        target = self._resolve_callable(node.func)
        if target:
            self.builder.add_edge(self.current_symbol(), target)

        for child in itertools_chain(node.args, node.keywords):
            child_value = child.value if isinstance(child, ast.keyword) else child
            for ref in self._collect_symbol_refs(child_value):
                self.builder.add_edge(self.current_symbol(), ref)

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Assignment tracking for simple type inference
    # ------------------------------------------------------------------
    def visit_Assign(self, node: ast.Assign) -> None:
        inferred = self._infer_type(node.value)
        if inferred:
            for target in node.targets:
                self._assign_target(target, inferred)
        owner = self.current_symbol()
        if node.value:
            for ref in self._collect_symbol_refs(node.value):
                self.builder.add_edge(owner, ref)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        inferred = self._infer_type(node.value) if node.value else None
        if inferred:
            self._assign_target(node.target, inferred)
        owner = self.current_symbol()
        if node.value:
            for ref in self._collect_symbol_refs(node.value):
                self.builder.add_edge(owner, ref)
        if node.annotation:
            for ref in self._collect_symbol_refs(node.annotation):
                self.builder.add_edge(owner, ref)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # Augmented assignments usually keep original type; no update needed.
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _assign_target(self, target: ast.expr, inferred: str) -> None:
        if isinstance(target, ast.Name):
            self.local_types_stack[-1][target.id] = inferred
        elif isinstance(target, ast.Attribute):
            class_symbol = self.current_class_symbol()
            if class_symbol and isinstance(target.value, ast.Name) and target.value.id in {"self", "cls"}:
                self.builder.register_class_attribute(class_symbol, target.attr, inferred)
        elif isinstance(target, ast.Tuple):
            for elt in target.elts:
                self._assign_target(elt, inferred)

    def _infer_type(self, node: Optional[ast.AST]) -> Optional[str]:
        if node is None:
            return None
        if isinstance(node, ast.Call):
            callee = self._resolve_callable(node.func)
            if callee and self._is_class_symbol(callee):
                return callee
        symbol = self._resolve_symbol_from_expression(node)
        if symbol and self._is_class_symbol(symbol):
            return symbol
        return None

    def _is_class_symbol(self, symbol: str) -> bool:
        definition = self.builder.definitions.get(symbol)
        return bool(definition and definition.kind == "class")

    def _resolve_symbol_from_expression(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            symbol = self.lookup_symbol(node.id)
            if symbol:
                return symbol
            alias = self.aliases.get(node.id)
            if alias:
                return alias.target
        elif isinstance(node, ast.Attribute):
            base = self._resolve_symbol_from_expression(node.value)
            if base:
                candidate = f"{base}.{node.attr}"
                class_attr_type = self.builder.class_attribute_types.get(base, {}).get(node.attr)
                return class_attr_type or candidate
        return None

    def _resolve_callable(self, func: ast.AST) -> Optional[str]:
        if isinstance(func, ast.Name):
            symbol = self.lookup_symbol(func.id)
            if symbol:
                return symbol
            alias = self.aliases.get(func.id)
            if alias:
                return alias.target
        elif isinstance(func, ast.Attribute):
            base_symbol = self._resolve_attribute_base(func.value)
            if base_symbol:
                candidate = f"{base_symbol}.{func.attr}"
                class_attr_type = self.builder.class_attribute_types.get(base_symbol, {}).get(func.attr)
                if class_attr_type and self._is_class_symbol(class_attr_type):
                    return class_attr_type
                return candidate
        return None

    def _resolve_attribute_base(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            if self.current_class_symbol() and node.id in {"self", "cls"}:
                return self.current_class_symbol()
            var_type = self.local_types_stack[-1].get(node.id)
            if var_type:
                return var_type
            symbol = self.lookup_symbol(node.id)
            if symbol:
                return symbol
            alias = self.aliases.get(node.id)
            if alias:
                return alias.target
        elif isinstance(node, ast.Attribute):
            owner = self._resolve_attribute_base(node.value)
            if owner:
                attr_type = self.builder.class_attribute_types.get(owner, {}).get(node.attr)
                return attr_type or f"{owner}.{node.attr}"
        return None

    def _collect_symbol_refs(self, node: ast.AST) -> Set[str]:
        refs: Set[str] = set()
        if isinstance(node, ast.Name):
            symbol = self.lookup_symbol(node.id)
            if symbol:
                refs.add(symbol)
            else:
                alias = self.aliases.get(node.id)
                if alias:
                    refs.add(alias.target)
        elif isinstance(node, ast.Attribute):
            base_symbol = self._resolve_attribute_base(node)
            if base_symbol:
                refs.add(base_symbol)
        for child in ast.iter_child_nodes(node):
            refs.update(self._collect_symbol_refs(child))
        return refs

    def _prefill_module_scope(self, tree: ast.Module) -> None:
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbol = f"{self.module}.{node.name}"
                self.scope_stack[0][node.name] = symbol
                self.builder.add_definition(
                    symbol,
                    "class",
                    module=self.module,
                    name=node.name,
                    filepath=self.filepath,
                    lineno=node.lineno,
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = f"{self.module}.{node.name}"
                self.scope_stack[0][node.name] = symbol
                self.builder.add_definition(
                    symbol,
                    "function",
                    module=self.module,
                    name=node.name,
                    filepath=self.filepath,
                    lineno=node.lineno,
                )


def resolve_relative_module(current_module: str, module: Optional[str], level: int) -> Optional[str]:
    if level == 0:
        return module
    parts = current_module.split(".")
    if level > len(parts):
        return module
    base_parts = parts[: len(parts) - level]
    if module:
        base_parts.append(module)
    if not base_parts:
        return None
    return ".".join(base_parts)


def iter_python_files(paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_dir():
            for sub_path in sorted(path.rglob("*.py")):
                yield sub_path
        elif path.is_file() and path.suffix == ".py":
            yield path


def path_to_module(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # drop ".py"
    return ".".join(parts)


def gather_sources(root: Path, inputs: Iterable[str]) -> dict[str, Path]:
    module_to_path: dict[str, Path] = {}
    resolved_paths = [root / entry for entry in inputs]
    for file_path in iter_python_files(resolved_paths):
        module_name = path_to_module(root, file_path)
        module_to_path[module_name] = file_path
    return module_to_path


def build_call_graph(root: Path, modules: dict[str, Path]) -> CallGraphBuilder:
    builder = CallGraphBuilder()
    for module_name, file_path in modules.items():
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        tree = ast.parse(source, filename=str(file_path))
        analyzer = ModuleAnalyzer(builder, file_path, module_name, tree)
        analyzer.visit(tree)
    builder.finalize()
    return builder


def compute_reachable(builder: CallGraphBuilder, entries: Iterable[str]) -> Set[str]:
    reachable: Set[str] = set()
    queue: deque[str] = deque(entries)
    while queue:
        symbol = queue.popleft()
        if symbol in reachable:
            continue
        reachable.add(symbol)
        for target in builder.edges.get(symbol, ()):
            if target not in reachable and target in builder.definitions:
                queue.append(target)
    return reachable


def format_definition(defn: Definition) -> str:
    return f"{defn.filepath}:{defn.lineno} - {defn.symbol} ({defn.kind})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=".",
        help="Project root directory (default: current directory).",
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=["main.py", "packages/spec2code"],
        help="Paths (files or directories) to include in the analysis.",
    )
    parser.add_argument(
        "--entry",
        action="append",
        default=["main"],
        help="Entry symbol(s) for reachability (default: module 'main'). Use fully qualified names, e.g. 'main.main'.",
    )
    parser.add_argument(
        "--include-kinds",
        nargs="+",
        choices=["module", "class", "function", "method"],
        default=["class", "function", "method"],
        help="Symbol kinds to include in the unreachable report.",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Symbol(s) to ignore when reporting unreachable definitions. May be specified multiple times.",
    )
    parser.add_argument(
        "--no-default-ignore",
        action="store_true",
        help="Do not skip the built-in ignore list for known dynamic entry points.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    modules = gather_sources(root, args.inputs)
    if not modules:
        raise SystemExit("No Python sources found under the provided inputs.")

    builder = build_call_graph(root, modules)
    for entry in args.entry:
        if entry not in builder.definitions:
            print(f"Warning: entry symbol '{entry}' is not defined in sources.")

    reachable = compute_reachable(builder, args.entry)

    ignored_symbols: Set[str] = set(args.ignore or [])
    if not args.no_default_ignore:
        ignored_symbols.update(DEFAULT_IGNORED_SYMBOLS)
    unreachable_defs = [
        defn
        for defn in builder.definitions.values()
        if defn.kind in args.include_kinds and defn.symbol not in reachable and defn.symbol not in ignored_symbols
    ]
    unreachable_defs.sort(key=lambda d: (str(d.filepath), d.lineno, d.symbol))

    if not unreachable_defs:
        print("== Unreachable symbols ==")
        print("All tracked symbols are reachable from the provided entry points.")
        return
    print("== Unreachable symbols ==")
    for defn in unreachable_defs:
        print(format_definition(defn))
    raise SystemExit(1)


def itertools_chain(*iterables: Iterable[ast.AST]) -> Iterator[ast.AST]:
    for iterable in iterables:
        for item in iterable:
            yield item


if __name__ == "__main__":
    main()
