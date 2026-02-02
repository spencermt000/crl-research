#!/usr/bin/env python3
"""
Demo script for claude-trace.

This simulates logging some Claude Code actions to show
how the framework works.
"""

import sys
sys.path.insert(0, '..')

from datetime import datetime, timedelta
import random

from claude_trace import (
    ActionLogger,
    TraceAnalyzer,
    TraceViewer,
    Modality,
)


def simulate_web_scraper_session(logger: ActionLogger):
    """Simulate a session where we build a web scraper."""
    
    with logger.session(goal="Build a web scraper for news articles") as session:
        # First, explore the directory
        logger.log_action(
            tool="bash_tool",
            inputs={"command": "ls -la"},
            output="total 0\ndrwxr-xr-x  2 user user  40 Jan 15 10:00 .\ndrwxr-xr-x 10 user user 200 Jan 15 09:00 ..",
            success=True,
        )
        
        # Install dependencies
        logger.log_action(
            tool="bash_tool",
            inputs={"command": "pip install requests beautifulsoup4"},
            output="Successfully installed requests-2.31.0 beautifulsoup4-4.12.0",
            success=True,
        )
        
        # Create the scraper file
        logger.log_action(
            tool="create_file",
            inputs={
                "path": "scraper.py",
                "content": "import requests\nfrom bs4 import BeautifulSoup\n..."
            },
            output="File created successfully",
            success=True,
        )
        
        # Test it
        logger.log_action(
            tool="bash_tool",
            inputs={"command": "python scraper.py"},
            output="Fetched 10 articles from example.com",
            success=True,
        )
        
        session.complete(success=True)


def simulate_debugging_session(logger: ActionLogger):
    """Simulate a debugging session with errors."""
    
    with logger.session(goal="Fix the failing tests") as session:
        # Run tests first
        logger.log_action(
            tool="bash_tool",
            inputs={"command": "pytest tests/"},
            output="FAILED tests/test_api.py::test_login - AssertionError",
            success=False,
            error="Test failures",
        )
        
        # Look at the failing test
        logger.log_action(
            tool="view",
            inputs={"path": "tests/test_api.py"},
            output="def test_login():\n    response = client.post('/login', ...)",
            success=True,
        )
        
        # Search for related code
        logger.log_action(
            tool="bash_tool",
            inputs={"command": "grep -r 'def login' src/"},
            output="src/api.py:def login(username, password):",
            success=True,
        )
        
        # View the source
        logger.log_action(
            tool="view",
            inputs={"path": "src/api.py"},
            output="def login(username, password):\n    # Bug: missing validation",
            success=True,
        )
        
        # Fix it
        logger.log_action(
            tool="str_replace",
            inputs={
                "path": "src/api.py",
                "old": "def login(username, password):",
                "new": "def login(username, password):\n    if not username:\n        raise ValueError('Username required')"
            },
            output="Replacement successful",
            success=True,
        )
        
        # Re-run tests
        logger.log_action(
            tool="bash_tool",
            inputs={"command": "pytest tests/"},
            output="All tests passed!",
            success=True,
        )
        
        session.complete(success=True)


def simulate_research_session(logger: ActionLogger):
    """Simulate a research/exploration session."""
    
    with logger.session(goal="Research best practices for API design") as session:
        # Web search
        logger.log_action(
            tool="web_search",
            inputs={"query": "REST API design best practices 2024"},
            output="Found 10 results...",
            success=True,
        )
        
        # Fetch a page
        logger.log_action(
            tool="web_fetch",
            inputs={"url": "https://example.com/api-guide"},
            output="# API Design Guide\n\n1. Use nouns for resources...",
            success=True,
        )
        
        # Take notes
        logger.log_action(
            tool="create_file",
            inputs={"path": "notes.md", "content": "# API Research Notes\n\n..."},
            output="File created",
            success=True,
        )
        
        session.complete(success=True)


def main():
    print("=" * 60)
    print("Claude Trace Demo")
    print("=" * 60)
    
    # Use a temp data directory for the demo
    data_dir = "./demo_data"
    
    # Create logger
    logger = ActionLogger(data_dir)
    
    print("\n1. Simulating sessions...")
    
    # Simulate several sessions
    simulate_web_scraper_session(logger)
    print("   ✓ Web scraper session")
    
    simulate_debugging_session(logger)
    print("   ✓ Debugging session")
    
    simulate_research_session(logger)
    print("   ✓ Research session")
    
    # Now analyze
    print("\n2. Analyzing traces...")
    analyzer = TraceAnalyzer(logger.storage)
    
    stats = analyzer.get_overall_stats()
    print(f"   Total traces: {stats['total_traces']}")
    print(f"   Sessions: {stats['unique_sessions']}")
    
    # Find patterns
    patterns = analyzer.find_tool_sequences(min_frequency=1)
    print(f"   Patterns found: {len(patterns)}")
    
    # View
    print("\n3. Viewing results...")
    viewer = TraceViewer(data_dir)
    
    viewer.show_summary()
    viewer.list_sessions()
    viewer.show_patterns()
    
    # Export for ML
    print("\n4. Exporting for ML...")
    sequences = analyzer.export_sequences_for_training()
    print(f"   Exported {len(sequences)} sequences")
    
    tgnn_data = analyzer.export_for_tgnn()
    print(f"   Exported {len(tgnn_data)} graphs for tGNN")
    
    print("\n" + "=" * 60)
    print("Demo complete! Check ./demo_data for the logged traces.")
    print("=" * 60)


if __name__ == "__main__":
    main()
