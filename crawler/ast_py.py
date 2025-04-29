"""Python source code parser using libcst to generate JSON-serializable AST."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

logger = logging.getLogger(__name__)


@dataclass
class ASTNode:
    """JSON-serializable representation of a Python AST node.

    Attributes:
        node_type: Type of the node (e.g., 'Module', 'FunctionDef', etc.)
        name: Name of the node if applicable (e.g., function name, class name)
        start_line: Starting line number in the source code
        end_line: Ending line number in the source code
        docstring: Documentation string if available
        children: List of child nodes
        attributes: Additional attributes specific to the node type
    """

    node_type: str
    name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    docstring: Optional[str] = None
    children: List[ASTNode] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)


class PythonASTVisitor(cst.CSTVisitor):
    """Visitor that converts a CST to simplified JSON-serializable AST."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        """Initialize the visitor."""
        super().__init__()
        self.stack: List[ASTNode] = []
        self.current_docstring: Optional[str] = None

    def _add_node(self, node_type: str, name: Optional[str] = None) -> ASTNode:
        """Create a new AST node and add it to the stack.

        Args:
            node_type: Type of the node
            name: Name of the node if applicable

        Returns:
            The created ASTNode
        """
        position = self.get_metadata(PositionProvider, self.syntax_node)
        
        ast_node = ASTNode(
            node_type=node_type,
            name=name,
            start_line=position.start.line,
            end_line=position.end.line,
        )
        
        if self.stack:
            self.stack[-1].children.append(ast_node)
        
        return ast_node

    def visit_Module(self, node: cst.Module) -> Optional[bool]:
        """Visit a module node.

        Args:
            node: The CST Module node

        Returns:
            Optional boolean to control traversal
        """
        module_node = ASTNode(
            node_type="Module",
            name="<module>",
            start_line=1,
            end_line=len(node.code.splitlines()),
        )
        self.stack.append(module_node)
        return True

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        """Visit a class definition.

        Args:
            node: The CST ClassDef node

        Returns:
            Optional boolean to control traversal
        """
        class_node = self._add_node("ClassDef", node.name.value)
        
        # Save bases/inheritance
        bases = []
        for base in node.bases:
            if isinstance(base.value, cst.Name):
                bases.append(base.value.value)
        
        if bases:
            class_node.attributes["bases"] = bases
        
        self.stack.append(class_node)
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        """Visit a function definition.

        Args:
            node: The CST FunctionDef node

        Returns:
            Optional boolean to control traversal
        """
        func_node = self._add_node("FunctionDef", node.name.value)
        
        # Extract parameters
        params = []
        for param in node.params.params:
            param_info = {"name": param.name.value}
            
            # Get parameter annotation if exists
            if param.annotation:
                annotation_str = None
                if isinstance(param.annotation.annotation, cst.Name):
                    annotation_str = param.annotation.annotation.value
                elif isinstance(param.annotation.annotation, cst.Attribute):
                    # Handle attributes like typing.List
                    annotation_str = get_attribute_full_name(param.annotation.annotation)
                
                if annotation_str:
                    param_info["annotation"] = annotation_str
            
            # Get default value if exists
            if param.default:
                default_str = None
                if isinstance(param.default, cst.SimpleString):
                    default_str = param.default.value
                elif isinstance(param.default, cst.Integer):
                    default_str = param.default.value
                elif isinstance(param.default, cst.Float):
                    default_str = param.default.value
                elif isinstance(param.default, (cst.List, cst.Dict, cst.Set)):
                    default_str = "<container>"
                
                if default_str:
                    param_info["default"] = default_str
            
            params.append(param_info)
        
        if params:
            func_node.attributes["params"] = params
        
        # Get return annotation if exists
        if node.returns:
            return_annotation = None
            if isinstance(node.returns.annotation, cst.Name):
                return_annotation = node.returns.annotation.value
            elif isinstance(node.returns.annotation, cst.Attribute):
                return_annotation = get_attribute_full_name(node.returns.annotation)
            
            if return_annotation:
                func_node.attributes["returns"] = return_annotation
        
        # Check for docstring in the first statement
        if node.body.body and isinstance(node.body.body[0], cst.SimpleStatementLine):
            stmt = node.body.body[0]
            if len(stmt.body) == 1 and isinstance(stmt.body[0], cst.Expr):
                expr = stmt.body[0].value
                if isinstance(expr, cst.SimpleString):
                    # Extract and clean the docstring
                    docstring = expr.value.strip('"\'')
                    func_node.docstring = docstring
        
        self.stack.append(func_node)
        return True

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        """Leave a class definition node.

        Args:
            original_node: The CST ClassDef node
        """
        self.stack.pop()

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        """Leave a function definition node.

        Args:
            original_node: The CST FunctionDef node
        """
        self.stack.pop()

    def leave_Module(self, original_node: cst.Module) -> None:
        """Leave a module node.

        Args:
            original_node: The CST Module node
        """
        # Root module node stays in the stack for retrieval
        pass

    def get_root(self) -> ASTNode:
        """Get the root AST node.

        Returns:
            The root AST node
        """
        if not self.stack:
            return ASTNode(node_type="Empty")
        return self.stack[0]


def get_attribute_full_name(node: cst.Attribute) -> str:
    """Get the full name of an attribute (e.g., 'typing.List').

    Args:
        node: The CST Attribute node

    Returns:
        The full attribute name
    """
    if isinstance(node.value, cst.Name):
        return f"{node.value.value}.{node.attr.value}"
    elif isinstance(node.value, cst.Attribute):
        return f"{get_attribute_full_name(node.value)}.{node.attr.value}"
    return node.attr.value


def parse_python_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Parse a Python file into a JSON-serializable AST.

    Args:
        file_path: Path to the Python file

    Returns:
        A JSON-serializable dictionary representing the AST
    """
    path = Path(file_path)
    if not path.exists():
        logger.error(f"File does not exist: {path}")
        return {"error": f"File not found: {path}"}

    try:
        with open(path, "r", encoding="utf-8") as f:
            source_code = f.read()

        # Parse the code with libcst
        module = cst.parse_module(source_code)
        
        # Apply metadata wrapper for position information
        wrapper = MetadataWrapper(module)
        
        # Create and use our visitor
        visitor = PythonASTVisitor()
        wrapper.visit(visitor)
        
        # Get the simplified AST
        ast_root = visitor.get_root()
        
        # Convert to dictionary
        ast_dict = asdict(ast_root)
        
        return ast_dict
    except Exception as e:
        logger.exception(f"Error parsing {path}: {e}")
        return {"error": f"Failed to parse {path}: {str(e)}"}


def parse_directory(dir_path: Union[str, Path], extensions: Set[str] = {".py"}) -> Dict[str, Dict[str, Any]]:
    """Parse all Python files in a directory.

    Args:
        dir_path: Path to the directory
        extensions: File extensions to include (default: {".py"})

    Returns:
        Dictionary mapping file paths to their ASTs
    """
    path = Path(dir_path)
    if not path.exists() or not path.is_dir():
        logger.error(f"Directory does not exist: {path}")
        return {"error": f"Directory not found: {path}"}

    results = {}
    for file_path in path.glob("**/*"):
        if file_path.is_file() and file_path.suffix in extensions:
            relative_path = str(file_path.relative_to(path))
            results[relative_path] = parse_python_file(file_path)

    return results


def save_ast_to_json(ast: Dict[str, Any], output_path: Union[str, Path]) -> None:
    """Save an AST dictionary to a JSON file.

    Args:
        ast: The AST dictionary
        output_path: Path to the output JSON file
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ast, f, indent=2)
    
    logger.info(f"AST saved to {path}") 