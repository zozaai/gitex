import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import importlib.util


@dataclass
class ImportInfo:
    """Represents an import statement and its details."""
    module: str
    alias: Optional[str] = None
    is_from_import: bool = False
    imported_names: List[str] = field(default_factory=list)
    is_external: bool = True
    line_number: int = 0


@dataclass
class ClassInfo:
    """Represents class definition and inheritance information."""
    name: str
    file_path: str
    bases: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    line_number: int = 0


@dataclass
class FunctionInfo:
    """Represents function definition and call information."""
    name: str
    file_path: str
    calls: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    line_number: int = 0
    is_method: bool = False
    class_name: Optional[str] = None


@dataclass
class DependencyAnalysis:
    """Complete dependency analysis results."""
    imports: Dict[str, List[ImportInfo]] = field(default_factory=dict)
    classes: Dict[str, ClassInfo] = field(default_factory=dict)
    functions: Dict[str, FunctionInfo] = field(default_factory=dict)
    file_dependencies: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    inheritance_tree: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    function_call_graph: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))


class DependencyMapper:
    """
    Analyzes Python codebases to extract dependency and relationship information.
    
    This class provides comprehensive analysis of:
    - Import dependencies between files
    - Class inheritance hierarchies
    - Function call relationships
    - Cross-file relationships
    
    Designed to generate LLM-friendly summaries of codebase structure.
    """
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.analysis = DependencyAnalysis()
        self.python_files: List[Path] = []
        self.project_modules: Set[str] = set()
    
    def analyze(self, file_paths: Optional[List[str]] = None) -> DependencyAnalysis:
        """
        Perform complete dependency analysis on the codebase.
        
        Args:
            file_paths: Optional list of specific files to analyze. If None, analyzes all Python files.
            
        Returns:
            DependencyAnalysis object containing all discovered relationships.
        """
        if file_paths:
            self.python_files = [Path(fp) for fp in file_paths if fp.endswith('.py')]
        else:
            self.python_files = list(self.root_path.rglob('*.py'))
        
        # Build project module set for internal/external distinction
        self._build_project_modules()
        
        # Analyze each file
        for file_path in self.python_files:
            try:
                self._analyze_file(file_path)
            except Exception as e:
                # Continue analysis even if one file fails
                print(f"Warning: Failed to analyze {file_path}: {e}")
                continue
        
        # Build cross-file relationships
        self._build_relationships()
        
        return self.analysis
    
    def _build_project_modules(self):
        """Build set of internal project modules."""
        for py_file in self.python_files:
            # Convert file path to module name
            rel_path = py_file.relative_to(self.root_path)
            if rel_path.name == '__init__.py':
                module_name = str(rel_path.parent).replace(os.sep, '.')
            else:
                module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
            
            if module_name != '.':
                self.project_modules.add(module_name)
                # Add parent modules too
                parts = module_name.split('.')
                for i in range(1, len(parts)):
                    self.project_modules.add('.'.join(parts[:i]))
    
    def _analyze_file(self, file_path: Path):
        """Analyze a single Python file for dependencies and relationships."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            return
        
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return
        
        rel_path = str(file_path.relative_to(self.root_path))
        
        # Initialize file imports
        self.analysis.imports[rel_path] = []
        
        # Analyze the AST
        visitor = self.DependencyVisitor(self, rel_path)
        visitor.visit(tree)
    
    def _build_relationships(self):
        """Build cross-file relationships after analyzing all files."""
        # Build file dependencies from imports
        for file_path, imports in self.analysis.imports.items():
            for import_info in imports:
                if not import_info.is_external:
                    self.analysis.file_dependencies[file_path].add(import_info.module)
        
        # Build inheritance tree
        for class_key, class_info in self.analysis.classes.items():
            for base in class_info.bases:
                # Find the base class in our analysis
                for other_key, other_class in self.analysis.classes.items():
                    if other_class.name == base or other_key.endswith(f".{base}"):
                        self.analysis.inheritance_tree[other_key].append(class_key)
                        break
        
        # Build function call graph with more context
        for func_key, func_info in self.analysis.functions.items():
            for call in func_info.calls:
                # Try to find the called function in our analysis
                for other_key, other_func in self.analysis.functions.items():
                    if (other_func.name == call or 
                        other_key.endswith(f".{call}") or 
                        (func_info.class_name and f"{func_info.class_name}.{call}" in other_key)):
                        self.analysis.function_call_graph[func_key].add(other_key)
                        other_func.called_by.append(func_key)
                        break
    
    class DependencyVisitor(ast.NodeVisitor):
        """AST visitor to extract dependency information."""
        
        def __init__(self, mapper: 'DependencyMapper', file_path: str):
            self.mapper = mapper
            self.file_path = file_path
            self.current_class: Optional[str] = None
            self.current_function: Optional[str] = None
        
        def visit_Import(self, node: ast.Import):
            """Handle import statements."""
            for alias in node.names:
                import_info = ImportInfo(
                    module=alias.name,
                    alias=alias.asname,
                    is_from_import=False,
                    is_external=alias.name not in self.mapper.project_modules,
                    line_number=node.lineno
                )
                self.mapper.analysis.imports[self.file_path].append(import_info)
            self.generic_visit(node)
        
        def visit_ImportFrom(self, node: ast.ImportFrom):
            """Handle from...import statements."""
            if node.module:
                imported_names = [alias.name for alias in node.names]
                import_info = ImportInfo(
                    module=node.module,
                    is_from_import=True,
                    imported_names=imported_names,
                    is_external=node.module not in self.mapper.project_modules,
                    line_number=node.lineno
                )
                self.mapper.analysis.imports[self.file_path].append(import_info)
            self.generic_visit(node)
        
        def visit_ClassDef(self, node: ast.ClassDef):
            """Handle class definitions."""
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(ast.unparse(base))
            
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            
            class_key = f"{self.file_path}::{node.name}"
            class_info = ClassInfo(
                name=node.name,
                file_path=self.file_path,
                bases=bases,
                methods=methods,
                line_number=node.lineno
            )
            self.mapper.analysis.classes[class_key] = class_info
            
            # Visit class body with class context
            old_class = self.current_class
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = old_class
        
        def visit_FunctionDef(self, node: ast.FunctionDef):
            """Handle function definitions."""
            self._visit_function_def(node)
        
        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            """Handle async function definitions."""
            self._visit_function_def(node)
        
        def _visit_function_def(self, node):
            """Common handler for function definitions."""
            func_key = f"{self.file_path}::{self.current_class or ''}.{node.name}".strip('.')
            
            function_info = FunctionInfo(
                name=node.name,
                file_path=self.file_path,
                line_number=node.lineno,
                is_method=self.current_class is not None,
                class_name=self.current_class
            )
            
            # Find function calls in the body
            old_function = self.current_function
            self.current_function = node.name
            
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        function_info.calls.append(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        if isinstance(child.func.value, ast.Name):
                            if child.func.value.id == 'self' and self.current_class:
                                function_info.calls.append(child.func.attr)
                            else:
                                function_info.calls.append(f"{child.func.value.id}.{child.func.attr}")
            
            self.mapper.analysis.functions[func_key] = function_info
            self.current_function = old_function
            
            self.generic_visit(node)


def format_dependency_analysis(analysis: DependencyAnalysis, focus: Optional[str] = None) -> str:
    """
    Format dependency analysis results into LLM-friendly text.
    
    Args:
        analysis: DependencyAnalysis object to format
        focus: Optional focus area ('imports', 'inheritance', 'calls', or None for all)
        
    Returns:
        Formatted string suitable for LLM prompts
    """
    output = []
    
    if not focus or focus == 'imports':
        output.append("## 📦 Import Dependencies\n")
        
        # Group by file and show dependencies
        for file_path, imports in analysis.imports.items():
            if not imports:
                continue
                
            internal_imports = [imp for imp in imports if not imp.is_external]
            external_imports = [imp for imp in imports if imp.is_external]
            
            if internal_imports or external_imports:
                output.append(f"**{file_path}** imports:")
                
                if internal_imports:
                    output.append("  Internal:")
                    for imp in internal_imports:
                        if imp.is_from_import and imp.imported_names:
                            names = ", ".join(imp.imported_names)
                            output.append(f"    - from {imp.module} import {names}")
                        else:
                            alias_str = f" as {imp.alias}" if imp.alias else ""
                            output.append(f"    - import {imp.module}{alias_str}")
                
                if external_imports:
                    output.append("  External:")
                    for imp in external_imports:
                        if imp.is_from_import and imp.imported_names:
                            names = ", ".join(imp.imported_names[:3])  # Limit for readability
                            names += "..." if len(imp.imported_names) > 3 else ""
                            output.append(f"    - from {imp.module} import {names}")
                        else:
                            output.append(f"    - import {imp.module}")
                
                output.append("")
    
    if not focus or focus == 'inheritance':
        output.append("## 🏗️ Class Inheritance Hierarchy\n")
        
        # Find root classes (classes with no parents in our codebase)
        all_children = set()
        for children in analysis.inheritance_tree.values():
            all_children.update(children)
        
        root_classes = []
        for class_key, class_info in analysis.classes.items():
            if class_key not in all_children:
                root_classes.append(class_key)
        
        def format_inheritance_tree(class_key: str, level: int = 0) -> List[str]:
            """Recursively format inheritance tree."""
            lines = []
            if class_key in analysis.classes:
                class_info = analysis.classes[class_key]
                indent = "  " * level
                connector = "├── " if level > 0 else ""
                
                bases_str = ""
                if class_info.bases:
                    bases_str = f" extends {', '.join(class_info.bases)}"
                
                lines.append(f"{indent}{connector}**{class_info.name}** ({class_info.file_path}){bases_str}")
                
                # Add methods if any
                if class_info.methods:
                    method_list = ", ".join(class_info.methods[:5])
                    if len(class_info.methods) > 5:
                        method_list += "..."
                    lines.append(f"{indent}    Methods: {method_list}")
                
                # Add children
                children = analysis.inheritance_tree.get(class_key, [])
                for child in sorted(children):
                    lines.extend(format_inheritance_tree(child, level + 1))
            
            return lines
        
        if root_classes:
            for root in sorted(root_classes):
                output.extend(format_inheritance_tree(root))
                output.append("")
        else:
            output.append("No class inheritance relationships found.\n")
    
    if not focus or focus == 'calls':
        output.append("## 🔄 Function Call Relationships\n")
        
        # Show functions that call other functions
        functions_with_calls = {k: v for k, v in analysis.functions.items() 
                              if v.calls or analysis.function_call_graph.get(k)}
        
        if functions_with_calls:
            for func_key, func_info in sorted(functions_with_calls.items()):
                class_prefix = f"{func_info.class_name}." if func_info.class_name else ""
                output.append(f"**{class_prefix}{func_info.name}()** ({func_info.file_path})")
                
                # Show what this function calls
                calls = analysis.function_call_graph.get(func_key, set())
                if calls:
                    output.append("  Calls:")
                    for called_func_key in sorted(calls):
                        if called_func_key in analysis.functions:
                            called_func = analysis.functions[called_func_key]
                            called_class_prefix = f"{called_func.class_name}." if called_func.class_name else ""
                            output.append(f"    - {called_class_prefix}{called_func.name}() in {called_func.file_path}")
                
                # Show what calls this function
                if func_info.called_by:
                    output.append("  Called by:")
                    for caller_key in sorted(func_info.called_by):
                        if caller_key in analysis.functions:
                            caller = analysis.functions[caller_key]
                            caller_class_prefix = f"{caller.class_name}." if caller.class_name else ""
                            output.append(f"    - {caller_class_prefix}{caller.name}() in {caller.file_path}")
                
                output.append("")
        else:
            output.append("No function call relationships found.\n")
    
    # Add summary statistics
    output.append("## 📊 Summary Statistics\n")
    total_files = len([f for f in analysis.imports.keys() if analysis.imports[f]])
    total_classes = len(analysis.classes)
    total_functions = len(analysis.functions)
    external_deps = set()
    for imports in analysis.imports.values():
        for imp in imports:
            if imp.is_external:
                external_deps.add(imp.module.split('.')[0])  # Get root module name
    
    output.append(f"- **Files analyzed**: {total_files}")
    output.append(f"- **Classes found**: {total_classes}")
    output.append(f"- **Functions found**: {total_functions}")
    output.append(f"- **External dependencies**: {len(external_deps)} ({', '.join(sorted(list(external_deps))[:10])}{'...' if len(external_deps) > 10 else ''})")
    
    return "\n".join(output)