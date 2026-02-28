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
    format='%(asctime)s - %(levelname)s - %(message)s'
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
    for node in getattr(tree, 'body', []):
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

def resolve_slice_dependencies(root_path: str, start_file: str, symbol_name: str) -> Set[str]:
    """
    Given a starting file and a target symbol (class/func), returns a set of absolute file 
    paths of the start file and all internal scripts required by the symbols it uses.
    """
    logging.info(f"\n--- STARTING SLICE RESOLUTION ---")
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
    for node in getattr(tree, 'body', []):
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

        for n in getattr(t, 'body', []):
            try:
                if isinstance(n, ast.Import):
                    for alias in n.names:
                        add_import(alias.asname or alias.name, alias.name)
                        if not alias.asname and '.' in alias.name:
                            add_import(alias.name.split('.')[0], alias.name)
                            
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