from gitex.utils import build_file_tree
from gitex.renderer import Rendered

# Build tree from disk:
root = build_file_tree("./")

# If you want just children of the root directory:
nodes = root.children or []

renderer = Rendered(nodes)
print(renderer.render_tree())
print(renderer.render_files(base_dir="./"))
