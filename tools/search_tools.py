"""
tools/search_tools.py
====================

Tavily search tool for Search Agent.
"""

from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from dotenv import load_dotenv

load_dotenv()


search_tool = TavilySearch(
    max_results=5,
    search_depth="basic",
    country="india",
    topic="general",
)