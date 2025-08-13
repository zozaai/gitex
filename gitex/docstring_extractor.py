import ast
from pathlib import Path
from typing import Optional, List

def extract_docstrings(file_path: Path, symbol_path: Optional[str] = None, include_empty_classes: bool = False) -> str:
    """
    Extracts module, class, and function docstrings and signatures from a Python file,
    preserving the code structure. If a symbol_path is provided, it extracts
    documentation only for that specific symbol.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return f"Could not decode file: {file_path}\n"

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return f"Could not parse file: {file_path} (SyntaxError: {e})\n"

    output = []

    def _process_node(node, indent_level=0, is_target_node=False):
        nonlocal output
        indent = "    " * indent_level
        
        # Determine if the current node is a direct child of the target class
        parent_is_target = hasattr(node, 'parent') and getattr(node, 'parent_is_target', False)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # If we are in a class that is not the target, we don't want to process its methods.
            if hasattr(node, 'parent') and isinstance(node.parent, ast.ClassDef) and not getattr(node.parent, 'is_target_node', False):
                 if not is_target_node:
                    return

            decorator_list = [f"@{ast.unparse(d)}" for d in node.decorator_list]
            
            if decorator_list:
                output.append(f"{indent}" + f"\n{indent}".join(decorator_list))

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args_str = ast.unparse(node.args).replace('=', ' = ')
                args_str = ' '.join(args_str.split())
                return_type = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                signature = f"def {node.name}({args_str}){return_type}:"
                output.append(f"{indent}{signature}")
            else: # ClassDef
                signature = f"class {node.name}"
                if node.bases:
                    bases = ", ".join(ast.unparse(b) for b in node.bases)
                    signature += f"({bases})"
                signature += ":"
                output.append(f"{indent}{signature}")

            docstring = ast.get_docstring(node)
            if docstring:
                output.append(f'{indent}    """{docstring}"""')
            elif not include_empty_classes:
                # Remove the signature we just added if no docstring and not including empty classes
                output.pop()
                return

            # If it's a class, process its body
            if isinstance(node, ast.ClassDef):
                node.is_target_node = is_target_node
                for sub_node in node.body:
                    sub_node.parent = node
                    _process_node(sub_node, indent_level + 1, is_target_node=is_target_node)


    if not symbol_path:
        module_docstring = ast.get_docstring(tree)
        if module_docstring:
            output.append(f'"""{module_docstring}"""\n')
        for node in tree.body:
            _process_node(node)
    else:
        path_parts = symbol_path.split('.')
        
        # Try to find the file path part of the symbol
        file_path_part = ""
        for i in range(len(path_parts), 0, -1):
            potential_path = "/".join(path_parts[:i]) + ".py"
            if str(file_path).endswith(potential_path):
                file_path_part = ".".join(path_parts[:i])
                break
        
        symbol_name_parts = symbol_path[len(file_path_part):].lstrip('.').split('.')

        current_nodes = tree.body
        target_node = None

        for i, part in enumerate(symbol_name_parts):
            if not part: continue
            found_node = None
            for node in current_nodes:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == part:
                    if i == len(symbol_name_parts) - 1:
                        target_node = node
                        break
                    else:
                        found_node = node
                        current_nodes = node.body
                        break
            if target_node:
                break
        
        if target_node:
            _process_node(target_node, is_target_node=True)
        elif not symbol_name_parts or (len(symbol_name_parts) == 1 and not symbol_name_parts[0]):
             # It's a module path
            module_docstring = ast.get_docstring(tree)
            if module_docstring:
                output.append(f'"""{module_docstring}"""\n')
            for node in tree.body:
                _process_node(node)
        else:
            return f"Error: Symbol '{symbol_path}' not found in '{file_path.name}'."

    return "\n".join(output)