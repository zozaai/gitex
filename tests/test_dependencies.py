import textwrap
from pathlib import Path

import pytest

from gitex.picker.base import DefaultPicker
from gitex.picker.textuals import _PickerApp
from gitex.renderer import Renderer


def _write(repo: Path, relpath: str, content: str) -> None:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def _create_sample_repo(repo: Path) -> None:
    _write(
        repo,
        ".gitignore",
        """
        __pycache__/
        *.pyc
        .venv/
        .pytest_cache/
        """,
    )

    _write(
        repo,
        "README.md",
        """
        # Math Shapes Demo

        Small demo repo for testing recursive dependency selection in `gitex`.
        """,
    )

    _write(
        repo,
        "geometry/__init__.py",
        """
        from geometry.helpers.helper import validate_positive

        __all__ = ["validate_positive"]
        """,
    )

    _write(
        repo,
        "geometry/calculator.py",
        """
        from __future__ import annotations

        from geometry.helpers.square import Square


        def total_square_area(sides: list[float]) -> float:
            return sum(Square(side).area() for side in sides)


        def describe_square(side: float) -> dict[str, float | str]:
            sq = Square(side)
            return {
                "kind": sq.kind.value,
                "side": sq.side,
                "area": sq.area(),
                "perimeter": sq.perimeter(),
                "diagonal": sq.diagonal(),
            }


        if __name__ == "__main__":
            print(total_square_area([2, 3, 4]))
            print(describe_square(5))
        """,
    )

    _write(repo, "geometry/helpers/__init__.py", "")

    _write(
        repo,
        "geometry/helpers/helper.py",
        """
        def validate_positive(value: float, name: str) -> float:
            if value <= 0:
                raise ValueError(f"{name} must be > 0")
            return value
        """,
    )

    _write(
        repo,
        "geometry/helpers/square.py",
        """
        from __future__ import annotations

        from geometry.shapes.rectangle import Rectangle
        from geometry import validate_positive
        from ..shapes.surface import area
        from ..types_enums import ShapeKind


        class Square(Rectangle):
            def __init__(self, side: float) -> None:
                side = validate_positive(side, "side")
                super().__init__(width=side, height=side)
                self.kind = ShapeKind.SQUARE

            @property
            def side(self) -> float:
                return self.width

            def diagonal(self) -> float:
                return self.side * (2 ** 0.5)

            def area(self, a, b):
                return area(a=a, b=b)
        """,
    )

    _write(
        repo,
        "geometry/rectangle_only.py",
        """
        from __future__ import annotations

        from geometry.shapes.rectangle import Rectangle


        def describe_rectangle(width: float, height: float) -> dict[str, float | str]:
            rect = Rectangle(width=width, height=height)
            return {
                "kind": rect.kind.value,
                "width": rect.width,
                "height": rect.height,
                "area": rect.area(),
                "perimeter": rect.perimeter(),
            }


        if __name__ == "__main__":
            print(describe_rectangle(3, 5))
        """,
    )

    _write(
        repo,
        "geometry/shapes/__init__.py",
        """
        from .rectangle import Rectangle
        from ..helpers.square import Square

        __all__ = ["Rectangle", "Square"]
        """,
    )

    _write(
        repo,
        "geometry/shapes/rectangle.py",
        """
        from __future__ import annotations

        from geometry.types import Dimensions
        from geometry import validate_positive
        from ..types_enums import ShapeKind


        class Rectangle:
            def __init__(self, width: float, height: float) -> None:
                self.width = validate_positive(width, "width")
                self.height = validate_positive(height, "height")
                self.kind = ShapeKind.RECTANGLE

            @property
            def dimensions(self) -> Dimensions:
                return Dimensions(width=self.width, height=self.height)

            def area(self) -> float:
                return self.width * self.height

            def perimeter(self) -> float:
                return 2 * (self.width + self.height)
        """,
    )

    _write(
        repo,
        "geometry/shapes/surface.py",
        """
        def area(a, b):
            return a * b
        """,
    )

    _write(
        repo,
        "geometry/types.py",
        """
        from __future__ import annotations

        from dataclasses import dataclass


        @dataclass(frozen=True)
        class Dimensions:
            width: float
            height: float
        """,
    )

    _write(
        repo,
        "geometry/types_enums.py",
        """
        from __future__ import annotations

        from enum import Enum


        class ShapeKind(str, Enum):
            RECTANGLE = "rectangle"
            SQUARE = "square"
        """,
    )


def _collect_relative_file_paths(nodes, repo: Path) -> set[str]:
    out: set[str] = set()

    def walk(items) -> None:
        for node in items:
            if node.node_type == "file":
                out.add(str(Path(node.path).resolve().relative_to(repo.resolve())))
            if node.children:
                walk(node.children)

    walk(nodes)
    return out


def _build_app(repo: Path) -> _PickerApp:
    picker = DefaultPicker(ignore_hidden=True, respect_gitignore=True)
    nodes = picker.pick(str(repo))
    return _PickerApp(nodes)


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    _create_sample_repo(tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_dependencies_from_calculator(sample_repo: Path):
    app = _build_app(sample_repo)

    async with app.run_test() as pilot:
        app.selected_paths.add(str((sample_repo / "geometry" / "calculator.py").resolve()))

        await pilot.press("d")
        await pilot.press("enter")

    selected = _collect_relative_file_paths(app.selected_nodes, sample_repo)

    expected = {
        "geometry/__init__.py",
        "geometry/calculator.py",
        "geometry/helpers/helper.py",
        "geometry/helpers/square.py",
        "geometry/shapes/rectangle.py",
        "geometry/shapes/surface.py",
        "geometry/types.py",
        "geometry/types_enums.py",
    }

    assert selected == expected

    rendered_tree = Renderer(app.selected_nodes).render_tree()
    expected_tree = textwrap.dedent(
        """
        .
        └── geometry/
            ├── __init__.py
            ├── calculator.py
            ├── helpers/
            │   ├── helper.py
            │   └── square.py
            ├── shapes/
            │   ├── rectangle.py
            │   └── surface.py
            ├── types.py
            └── types_enums.py
        """
    ).strip()
    assert rendered_tree == expected_tree

    rendered_files = Renderer(app.selected_nodes).render_files(base_dir=str(sample_repo))
    assert "# geometry/calculator.py" in rendered_files
    assert "# geometry/helpers/square.py" in rendered_files
    assert "# geometry/shapes/rectangle.py" in rendered_files
    assert "# geometry/shapes/surface.py" in rendered_files
    assert "# geometry/types.py" in rendered_files
    assert "# geometry/types_enums.py" in rendered_files

    assert "# geometry/rectangle_only.py" not in rendered_files
    assert "# README.md" not in rendered_files
    assert "# .gitignore" not in rendered_files
    assert "# geometry/helpers/__init__.py" not in rendered_files
    assert "# geometry/shapes/__init__.py" not in rendered_files


@pytest.mark.asyncio
async def test_dependencies_from_rectangle_only(sample_repo: Path):
    app = _build_app(sample_repo)

    async with app.run_test() as pilot:
        app.selected_paths.add(str((sample_repo / "geometry" / "rectangle_only.py").resolve()))

        await pilot.press("d")
        await pilot.press("enter")

    selected = _collect_relative_file_paths(app.selected_nodes, sample_repo)

    expected = {
        "geometry/__init__.py",
        "geometry/helpers/helper.py",
        "geometry/rectangle_only.py",
        "geometry/shapes/rectangle.py",
        "geometry/types.py",
        "geometry/types_enums.py",
    }

    assert selected == expected

    rendered_tree = Renderer(app.selected_nodes).render_tree()
    expected_tree = textwrap.dedent(
        """
        .
        └── geometry/
            ├── __init__.py
            ├── helpers/
            │   └── helper.py
            ├── rectangle_only.py
            ├── shapes/
            │   └── rectangle.py
            ├── types.py
            └── types_enums.py
        """
    ).strip()
    assert rendered_tree == expected_tree

    rendered_files = Renderer(app.selected_nodes).render_files(base_dir=str(sample_repo))
    assert "# geometry/rectangle_only.py" in rendered_files
    assert "# geometry/shapes/rectangle.py" in rendered_files
    assert "# geometry/types.py" in rendered_files
    assert "# geometry/types_enums.py" in rendered_files
    assert "# geometry/__init__.py" in rendered_files
    assert "# geometry/helpers/helper.py" in rendered_files

    assert "# geometry/calculator.py" not in rendered_files
    assert "# geometry/helpers/square.py" not in rendered_files
    assert "# geometry/shapes/surface.py" not in rendered_files
    assert "# geometry/helpers/__init__.py" not in rendered_files
    assert "# geometry/shapes/__init__.py" not in rendered_files