"""Tests for the Python AST builder."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

from crawler.ast_py import (
    ASTNode,
    PythonASTVisitor,
    parse_python_file,
    parse_directory,
    save_ast_to_json,
)


SAMPLE_PYTHON_CODE = """
from typing import List, Optional

class Person:
    \"\"\"A simple person class.
    
    Attributes:
        name: The person's name
        age: The person's age
    \"\"\"
    
    def __init__(self, name: str, age: int = 30):
        \"\"\"Initialize a Person.
        
        Args:
            name: The person's name
            age: The person's age, defaults to 30
        \"\"\"
        self.name = name
        self.age = age
    
    def greet(self) -> str:
        \"\"\"Return a greeting message.
        
        Returns:
            A greeting string
        \"\"\"
        return f"Hello, my name is {self.name}"


def process_people(people: List[Person]) -> int:
    \"\"\"Process a list of people.
    
    Args:
        people: A list of Person objects
        
    Returns:
        The number of processed people
    \"\"\"
    return len(people)
"""


def test_parse_python_file():
    """Test parsing a Python file into an AST."""
    # Mock file operations
    with patch("builtins.open", mock_open(read_data=SAMPLE_PYTHON_CODE)):
        with patch("pathlib.Path.exists", return_value=True):
            ast_dict = parse_python_file("test.py")
    
    # Verify the AST structure
    assert ast_dict["node_type"] == "Module"
    assert ast_dict["name"] == "<module>"
    
    # Should have a class and a function
    children = ast_dict["children"]
    assert len(children) >= 2
    
    # Find the class definition
    class_def = next(child for child in children if child["node_type"] == "ClassDef")
    assert class_def["name"] == "Person"
    
    # Class should have methods
    class_methods = [
        child for child in class_def["children"] 
        if child["node_type"] == "FunctionDef"
    ]
    assert len(class_methods) == 2
    
    # Find the init method
    init_method = next(method for method in class_methods if method["name"] == "__init__")
    assert init_method["docstring"] is not None
    assert "Initialize a Person" in init_method["docstring"]
    
    # Check parameters
    assert "params" in init_method["attributes"]
    params = init_method["attributes"]["params"]
    assert len(params) >= 3  # self, name, age
    
    # Find the standalone function
    process_func = next(
        child for child in children 
        if child["node_type"] == "FunctionDef" and child["name"] == "process_people"
    )
    assert process_func["docstring"] is not None
    assert "Process a list of people" in process_func["docstring"]
    
    # Check return annotation
    assert process_func["attributes"]["returns"] == "int"


def test_parse_python_file_error_handling():
    """Test error handling when parsing a Python file."""
    # Test file not found
    with patch("pathlib.Path.exists", return_value=False):
        result = parse_python_file("nonexistent.py")
        assert "error" in result
        assert "File not found" in result["error"]
    
    # Test parse error
    invalid_code = "def broken_function(:"  # Syntax error
    with patch("builtins.open", mock_open(read_data=invalid_code)):
        with patch("pathlib.Path.exists", return_value=True):
            result = parse_python_file("broken.py")
            assert "error" in result
            assert "Failed to parse" in result["error"]


def test_parse_directory():
    """Test parsing a directory of Python files."""
    # Create a mock file structure
    mock_files = {
        "file1.py": SAMPLE_PYTHON_CODE,
        "file2.py": "def test(): pass",
        "not_python.txt": "This is not Python code",
    }
    
    def mock_glob(**kwargs):
        # Simulate Path.glob
        for filename in mock_files:
            yield Path(filename)
    
    def mock_read_file(path, *args, **kwargs):
        # Return content based on filename
        filename = path.name
        if filename in mock_files:
            return mock_files[filename]
        return ""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("pathlib.Path.glob", mock_glob):
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.is_dir", return_value=True):
                        with patch("builtins.open", lambda p, *a, **k: mock_open(read_data=mock_read_file(p))(*a, **k)):
                            results = parse_directory(temp_dir)
    
    # Should only include Python files
    assert "file1.py" in results
    assert "file2.py" in results
    assert "not_python.txt" not in results


def test_save_ast_to_json():
    """Test saving an AST to a JSON file."""
    ast_dict = {
        "node_type": "Module",
        "name": "<module>",
        "children": [
            {
                "node_type": "FunctionDef",
                "name": "test_function",
                "docstring": "Test function docstring",
            }
        ],
    }
    
    mock_path = Path("test_output.json")
    
    with patch("pathlib.Path.mkdir") as mock_mkdir:
        with patch("builtins.open", mock_open()) as mock_file:
            save_ast_to_json(ast_dict, mock_path)
            
            # Verify directory creation
            mock_mkdir.assert_called_once()
            
            # Verify file writing
            mock_file.assert_called_once_with(mock_path, "w", encoding="utf-8")
            
            # Verify JSON content
            file_handle = mock_file()
            file_handle.write.assert_called_once()
            
            # Get the JSON content
            json_content = file_handle.write.call_args[0][0]
            parsed_json = json.loads(json_content)
            
            assert parsed_json["node_type"] == "Module"
            assert parsed_json["children"][0]["name"] == "test_function" 