# core/utils.py
from __future__ import annotations
import os
from gitex.models import FileNode, NodeType

def build_file_tree(root_path: str, ignore_hidden: bool = True) -> FileNode:
    def walk_dir(current_path: str) -> FileNode:
        name = os.path.basename(current_path)
        if not name:  # If root_path is '/', basename would be ''
            name = current_path

        is_dir = os.path.isdir(current_path)
        node_type = NodeType.DIRECTORY if is_dir else NodeType.FILE

        if is_dir:
            try:
                entries = os.listdir(current_path)
            except PermissionError:
                entries = []

            children = []
            for entry in entries:
                full_path = os.path.join(current_path, entry)
                if ignore_hidden and entry.startswith('.'):
                    continue
                children.append(walk_dir(full_path))
        else:
            children = None

        return FileNode(
            name=name,
            path=current_path,
            node_type=node_type,
            children=children
        )

    return walk_dir(root_path)
