# gitex/slicer.py
import ast
import logging
from pathlib import Path
from typing import Set, Dict, List
import tempfile

# Force the log to system /tmp so it never gets lost or hidden.
log_path = Path(tempfile.gettempdir()) / "gitex_slicer.log"

logging.basicConfig(
    filename=str(log_path),
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def get_symbols_in_file(file_path: str) -> List[str]:
    """Return a list of class and function names defined in the file."""
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(content, filename=file_path)
    except Exception as e:
        logging.error(f"Failed to parse AST for {file_path}: {e}")
        return []

    symbols = []
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(node.name)

    return symbols


def get_used_names(node: ast.AST) -> Set[str]:
    """Recursively collect all variable/class names used inside an AST node."""
    used = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            used.add(child.id)
    return used

def _candidate_module_names(module_name: str) -> List[str]:
    """
    Return exact and suffix candidates.

    Example:
      geometry.shapes.square ->
      [
        "geometry.shapes.square",
        "shapes.square",
        "square",
      ]
    """
    parts = [p for p in module_name.split(".") if p]
    return [".".join(parts[i:]) for i in range(len(parts)) if parts[i:]]


def _match_internal_module(module_name: str, module_to_file: Dict[str, Path]) -> str | None:
    """
    Return the first matching internal module key from module_to_file.
    """
    for candidate in _candidate_module_names(module_name):
        if candidate in module_to_file:
            return candidate
    return None

def _build_module_to_file_map(root: Path) -> Dict[str, Path]:
    """
    Build a flexible mapping from module name -> python file path.

    Example for geometry/shapes/square.py:
      geometry.shapes.square -> .../geometry/shapes/square.py
      shapes.square          -> .../geometry/shapes/square.py
      square                 -> .../geometry/shapes/square.py

    This makes internal import matching robust even if the repo root and the
    import package root are not exactly aligned.
    """
    module_to_file: Dict[str, Path] = {}

    for py_file in root.rglob("*.py"):
        try:
            if py_file.is_symlink() or not py_file.is_file():
                continue

            rel_path = py_file.relative_to(root)
            parts = list(rel_path.with_suffix("").parts)

            if rel_path.name == "__init__.py":
                parts = parts[:-1]

            if not parts:
                continue

            for i in range(len(parts)):
                module_name = ".".join(parts[i:])
                if module_name and module_name not in module_to_file:
                    module_to_file[module_name] = py_file.resolve()

        except Exception as e:
            logging.warning(f"Error mapping file {py_file}: {e}")
            continue

    return module_to_file


def _resolve_import_from_module(file_path: Path, root: Path, module: str | None, level: int) -> str:
    """
    Resolve ImportFrom module into an absolute project module path.

    Example:
      file: benchmark/keypoint/projection.py
      from .metrics import foo   -> benchmark.keypoint.metrics
      from . import metrics      -> benchmark.keypoint
      from ..common import types -> benchmark.common
    """
    rel_parent_parts = list(file_path.relative_to(root).parent.parts)

    if level > 0:
        up = max(level - 1, 0)
        if up > 0:
            rel_parent_parts = rel_parent_parts[:-up] if up <= len(rel_parent_parts) else []

    base = ".".join(rel_parent_parts)
    if module:
        return f"{base}.{module}" if base else module
    return base


def _extract_internal_import_modules(file_path: Path, root: Path, module_to_file: Dict[str, Path]) -> Set[str]:
    """
    Extract internal module dependencies from one Python file.

    For:
      from x import y

    this tries both:
      - x
      - x.y

    and it also supports suffix matching.
    """
    internal_modules: Set[str] = set()

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        logging.warning(f"Failed to parse imports from {file_path}: {e}")
        return internal_modules

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                matched = _match_internal_module(alias.name, module_to_file)
                if matched:
                    internal_modules.add(matched)
                    logging.info(f"[IMPORT] {file_path.name}: {alias.name} -> {matched}")

        elif isinstance(node, ast.ImportFrom):
            base_module = _resolve_import_from_module(file_path, root, node.module, node.level)

            matched_base = _match_internal_module(base_module, module_to_file)
            if matched_base:
                internal_modules.add(matched_base)
                logging.info(f"[FROM] {file_path.name}: {base_module} -> {matched_base}")

            for alias in node.names:
                if alias.name == "*":
                    continue

                candidate = f"{base_module}.{alias.name}" if base_module else alias.name
                matched_candidate = _match_internal_module(candidate, module_to_file)
                if matched_candidate:
                    internal_modules.add(matched_candidate)
                    logging.info(f"[FROM NAME] {file_path.name}: {candidate} -> {matched_candidate}")

    return internal_modules


def resolve_file_dependencies(root_path: str, start_files: List[str]) -> Set[str]:
    """
    Recursively resolve internal Python-file dependencies for the given start files.

    This follows imports across the repo and returns absolute file paths including
    the original start files.

    Example:
      projection.py -> metrics.py -> types.py
    """
    logging.info("\n--- STARTING FILE DEPENDENCY RESOLUTION ---")
    logging.info(f"Start files: {start_files}")

    root = Path(root_path).resolve()
    module_to_file = _build_module_to_file_map(root)
    logging.info(f"Module map keys: {sorted(module_to_file.keys())}")

    selected_files: Set[str] = set()
    queue: List[Path] = []
    visited_files: Set[str] = set()

    for file_path in start_files:
        p = Path(file_path).resolve()
        if p.suffix == ".py" and p.exists():
            queue.append(p)
            selected_files.add(str(p))

    while queue:
        current_file = queue.pop(0)
        current_str = str(current_file)

        if current_str in visited_files:
            continue
        visited_files.add(current_str)

        imported_modules = _extract_internal_import_modules(current_file, root, module_to_file)

        for module_name in imported_modules:
            dep_file = module_to_file.get(module_name)
            if dep_file is None:
                continue

            dep_str = str(dep_file.resolve())
            if dep_str not in selected_files:
                logging.info(f"Adding dependency: {current_file} -> {dep_file}")
                selected_files.add(dep_str)
                queue.append(dep_file.resolve())

    return selected_files


def resolve_slice_dependencies(root_path: str, start_file: str, symbol_name: str) -> Set[str]:
    """
    Given a starting file and a target symbol (class/func), returns a set of absolute file
    paths of the start file and all internal scripts required by the symbols it uses.
    """
    logging.info("\n--- STARTING SLICE RESOLUTION ---")
    logging.info(f"Target symbol: {symbol_name} in {start_file}")

    root = Path(root_path).resolve()
    start = Path(start_file).resolve()

    # Pre-build module to file mapping for the entire repo
    module_to_file = {}
    for py_file in root.rglob("*.py"):
        try:
            if py_file.is_symlink() or not py_file.is_file():
                continue

            rel_path = py_file.relative_to(root)
            parts = list(rel_path.with_suffix("").parts)
            if rel_path.name == "__init__.py":
                parts = parts[:-1]

            full_mod_name = ".".join(parts)
            if full_mod_name:
                module_to_file[full_mod_name] = py_file

            for i in range(1, len(parts)):
                mod_name = ".".join(parts[i:])
                if mod_name and mod_name not in module_to_file:
                    module_to_file[mod_name] = py_file
        except Exception as e:
            logging.warning(f"Error mapping file {py_file}: {e}")
            continue

    selected_files = set()
    queue = []

    try:
        content = start.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(start))
    except Exception as e:
        logging.error(f"Failed to read/parse start file {start}: {e}")
        return {str(start)}

    selected_files.add(str(start))

    target_node = None
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == symbol_name:
                target_node = node
                break

    if not target_node:
        logging.warning(f"Target symbol '{symbol_name}' not found in AST of {start}")
        return selected_files

    used_names = get_used_names(target_node)
    logging.debug(f"Names used inside '{symbol_name}': {used_names}")

    def get_imports(t: ast.AST, fpath: Path) -> Dict[str, List[str]]:
        imports = {}

        def add_import(key: str, val: str):
            if key not in imports:
                imports[key] = []
            imports[key].append(val)

        for n in getattr(t, "body", []):
            try:
                if isinstance(n, ast.Import):
                    for alias in n.names:
                        add_import(alias.asname or alias.name, alias.name)
                        if not alias.asname and "." in alias.name:
                            add_import(alias.name.split(".")[0], alias.name)

                elif isinstance(n, ast.ImportFrom):
                    module = n.module or ""
                    if n.level > 0:
                        try:
                            rel_parts = list(fpath.parent.relative_to(root).parts)
                        except ValueError:
                            rel_parts = []
                        for _ in range(n.level - 1):
                            if rel_parts:
                                rel_parts.pop()
                        base_module = ".".join(rel_parts)
                        if base_module and module:
                            module = f"{base_module}.{module}"
                        elif base_module:
                            module = base_module

                    for alias in n.names:
                        if n.level > 0 and not n.module and module:
                            add_import(alias.asname or alias.name, f"{module}.{alias.name}")
                        add_import(alias.asname or alias.name, module)
            except Exception as e:
                logging.warning(f"Failed to process import node in {fpath}: {e}")
                continue
        return imports

    try:
        start_imports = get_imports(tree, start)
        for name, modules in start_imports.items():
            if name in used_names:
                logging.info(f"Dependency mapped! Name '{name}' linked to internal modules: {modules}")
                queue.extend(modules)
    except Exception as e:
        logging.error(f"Error mapping start imports: {e}")

    processed_modules = set()

    # BFS: resolve linked imports to their actual files
    while queue:
        module = queue.pop(0)
        if module in processed_modules:
            continue
        processed_modules.add(module)

        file_path = module_to_file.get(module)
        if not file_path:
            continue

        if str(file_path) in selected_files:
            continue

        logging.info(f"Adding linked dependency to selection: {file_path}")
        selected_files.add(str(file_path))

        try:
            content = file_path.read_text(encoding="utf-8")
            mod_tree = ast.parse(content, filename=str(file_path))
            mod_imports = get_imports(mod_tree, file_path)
            for mod_list in mod_imports.values():
                queue.extend(mod_list)
        except Exception:
            pass

    return selected_files