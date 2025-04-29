"""Crawler package for fetching and analyzing repositories."""
from __future__ import annotations

from crawler.clone import CloneManager
from crawler.baseline import BaselineAnalyzer
from crawler.ast_py import PythonASTExtractor
from crawler.ast_ts import TypeScriptASTExtractor

__all__ = [
    "CloneManager",
    "BaselineAnalyzer",
    "PythonASTExtractor",
    "TypeScriptASTExtractor",
] 