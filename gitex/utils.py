# utils.py
from __future__ import annotations
import os
import subprocess
from shutil import which
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


def copy_to_clipboard(text: str) -> bool:
    """
    Cross-platform clipboard copy helper.

    Strategy (in order):
      1) Try pyperclip (recommended, cross-platform Python API)
      2) Linux Wayland  -> wl-copy
      3) Linux X11      -> xclip
      4) Linux X11      -> xsel
      5) macOS          -> pbcopy

    Returns:
        True if copy succeeded.
        False if no clipboard backend was available.
    """

    # --------------------------------------------------
    # 1) Try Python-level solution (pyperclip)
    # --------------------------------------------------
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return True
    except Exception:
        pass

    # --------------------------------------------------
    # 2) Linux Wayland
    # --------------------------------------------------
    if which("wl-copy"):
        try:
            subprocess.run(
                ["wl-copy"],
                input=text.encode("utf-8"),
                check=True,
            )
            return True
        except Exception:
            pass

    # --------------------------------------------------
    # 3) Linux X11 - xclip
    # --------------------------------------------------
    if which("xclip"):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode("utf-8"),
                check=True,
            )
            return True
        except Exception:
            pass

    # --------------------------------------------------
    # 4) Linux X11 - xsel
    # --------------------------------------------------
    if which("xsel"):
        try:
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text.encode("utf-8"),
                check=True,
            )
            return True
        except Exception:
            pass

    # --------------------------------------------------
    # 5) macOS
    # --------------------------------------------------
    if which("pbcopy"):
        try:
            subprocess.run(
                ["pbcopy"],
                input=text.encode("utf-8"),
                check=True,
            )
            return True
        except Exception:
            pass

    # --------------------------------------------------
    # Nothing worked
    # --------------------------------------------------
    return False