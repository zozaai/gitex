"""
where we store the 
pydantic Data Structure class
for our project

"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

class NodeType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"

class FileNode(BaseModel):
    name: str
    path: str
    node_type: NodeType
    is_ignored: bool = False
    is_selected: bool = True
    children: Optional[List['FileNode']] = None
    metadata: Dict[str, Any] = {}
    
    class Config:
        use_enum_values = True