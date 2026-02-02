#!/usr/bin/env python3
"""
MCP Observer Server

Exposes wrapped versions of Claude Code's native tools that:
1. Log all calls with timestamps
2. Execute the actual operation
3. Log the result
4. Return the result

This gives you full observability into what Claude Code is doing.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("Claude Observer")

# Configuration - traces go to crl-research/outputs/traces/
TRACE_DIR = Path(os.environ.get("TRACE_DIR", Path(__file__).parent.parent / "outputs" / "traces"))
TRACE_DIR.mkdir(parents=True, exist_ok=True)
TRACE_FILE = TRACE_DIR / "live_trace.jsonl"

# Session tracking
SESSION_START = datetime.now()
SESSION_ID = SESSION_START.strftime("%Y%m%d_%H%M%S")
SEQUENCE = 0


def log_trace(
    tool: str,
    inputs: dict,
    output: str,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None,
):
    """Append a trace entry to the log file."""
    global SEQUENCE
    
    # Estimate tokens (rough: ~3.5 chars per token for code)
    input_str = json.dumps(inputs)
    input_tokens_est = len(input_str) / 3.5
    output_tokens_est = len(output) / 3.5
    
    trace = {
        "session_id": SESSION_ID,
        "sequence": SEQUENCE,
        "timestamp": datetime.now().isoformat(),
        "tool": tool,
        "inputs": inputs,
        "output": output[:5000],  # Truncate large outputs
        "output_full_length": len(output),
        "duration_ms": round(duration_ms, 2),
        "success": success,
        "error": error,
        "input_tokens_est": round(input_tokens_est),
        "output_tokens_est": round(output_tokens_est),
    }
    
    SEQUENCE += 1
    
    # Append to file
    with open(TRACE_FILE, "a") as f:
        f.write(json.dumps(trace) + "\n")
    
    # Also print for real-time observation (goes to stderr so doesn't interfere with MCP)
    status = "✓" if success else "✗"
    print(f"[{SEQUENCE:03d}] {status} {tool} ({duration_ms:.0f}ms) in≈{input_tokens_est:.0f} out≈{output_tokens_est:.0f}", 
          file=__import__('sys').stderr)
    
    return trace


# =============================================================================
# THINKING / REASONING TOOL
# =============================================================================

@mcp.tool()
def observed_think(reasoning: str) -> str:
    """
    Log your current reasoning, plan, or thought process.
    
    Call this BEFORE taking actions to explain your thinking.
    
    Args:
        reasoning: Your current reasoning, plan, or what you're thinking about
    
    Returns:
        Acknowledgment
    """
    start = time.time()
    
    log_trace(
        tool="think",
        inputs={"reasoning": reasoning},
        output="Noted.",
        duration_ms=(time.time() - start) * 1000,
        success=True,
    )
    
    return "Noted."


# =============================================================================
# OBSERVED TOOLS
# =============================================================================

@mcp.tool()
def observed_bash(command: str, description: str = "") -> str:
    """
    Execute a bash command and return the output.
    
    Args:
        command: The bash command to execute
        description: Optional description of why you're running this command
    
    Returns:
        The stdout/stderr output from the command
    """
    start = time.time()
    error = None
    success = True
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=os.getcwd(),
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            success = False
            error = f"Exit code: {result.returncode}"
    except subprocess.TimeoutExpired:
        output = "Command timed out after 300 seconds"
        success = False
        error = "Timeout"
    except Exception as e:
        output = str(e)
        success = False
        error = str(e)
    
    duration_ms = (time.time() - start) * 1000
    
    log_trace(
        tool="bash",
        inputs={"command": command, "description": description},
        output=output,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )
    
    return output


@mcp.tool()
def observed_view(path: str, start_line: int = 1, end_line: int = -1, description: str = "") -> str:
    """
    View the contents of a file or list a directory.
    
    Args:
        path: Path to the file or directory
        start_line: Starting line number (1-indexed, default: 1)
        end_line: Ending line number (-1 for all, default: -1)
        description: Optional description of why you're viewing this
    
    Returns:
        File contents or directory listing
    """
    start = time.time()
    error = None
    success = True
    output = ""
    
    try:
        p = Path(path).expanduser().resolve()
        
        if p.is_dir():
            # List directory
            entries = []
            for entry in sorted(p.iterdir()):
                prefix = "📁 " if entry.is_dir() else "📄 "
                entries.append(f"{prefix}{entry.name}")
            output = "\n".join(entries) if entries else "(empty directory)"
        
        elif p.is_file():
            # Read file
            content = p.read_text()
            lines = content.splitlines()
            
            if end_line == -1:
                end_line = len(lines)
            
            selected = lines[start_line - 1:end_line]
            
            # Add line numbers
            numbered = []
            for i, line in enumerate(selected, start=start_line):
                numbered.append(f"{i:4d} │ {line}")
            
            output = "\n".join(numbered)
        
        else:
            output = f"Path not found: {path}"
            success = False
            error = "Not found"
    
    except Exception as e:
        output = str(e)
        success = False
        error = str(e)
    
    duration_ms = (time.time() - start) * 1000
    
    log_trace(
        tool="view",
        inputs={"path": path, "start_line": start_line, "end_line": end_line, "description": description},
        output=output,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )
    
    return output


@mcp.tool()
def observed_create_file(path: str, content: str, description: str = "") -> str:
    """
    Create a new file with the given content.
    
    Args:
        path: Path where the file should be created
        content: The content to write to the file
        description: Optional description of what this file is for
    
    Returns:
        Confirmation message
    """
    start = time.time()
    error = None
    success = True
    output = ""
    
    try:
        p = Path(path).expanduser().resolve()
        
        # Create parent directories if needed
        p.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        p.write_text(content)
        
        line_count = len(content.splitlines())
        output = f"Created {path} ({line_count} lines, {len(content)} chars)"
    
    except Exception as e:
        output = str(e)
        success = False
        error = str(e)
    
    duration_ms = (time.time() - start) * 1000
    
    log_trace(
        tool="create_file",
        inputs={"path": path, "content_length": len(content), "description": description},
        output=output,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )
    
    return output


@mcp.tool()
def observed_str_replace(
    path: str,
    old_str: str,
    new_str: str,
    description: str = ""
) -> str:
    """
    Replace a string in a file. The old_str must appear exactly once.
    
    Args:
        path: Path to the file to edit
        old_str: The exact string to find and replace (must be unique)
        new_str: The string to replace it with
        description: Optional description of what this edit does
    
    Returns:
        Confirmation message
    """
    start = time.time()
    error = None
    success = True
    output = ""
    
    try:
        p = Path(path).expanduser().resolve()
        
        if not p.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        
        content = p.read_text()
        
        # Check uniqueness
        count = content.count(old_str)
        if count == 0:
            raise ValueError(f"String not found in file")
        if count > 1:
            raise ValueError(f"String appears {count} times, must be unique")
        
        # Replace
        new_content = content.replace(old_str, new_str)
        p.write_text(new_content)
        
        output = f"Replaced in {path} (-{len(old_str)} +{len(new_str)} chars)"
    
    except Exception as e:
        output = str(e)
        success = False
        error = str(e)
    
    duration_ms = (time.time() - start) * 1000
    
    log_trace(
        tool="str_replace",
        inputs={
            "path": path,
            "old_str_length": len(old_str),
            "new_str_length": len(new_str),
            "old_str_preview": old_str[:100] + "..." if len(old_str) > 100 else old_str,
            "description": description,
        },
        output=output,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )
    
    return output


# =============================================================================
# UTILITY TOOLS
# =============================================================================

@mcp.tool()
def get_session_stats() -> str:
    """
    Get statistics about the current observation session.
    
    Returns:
        Session statistics including trace count, duration, token estimates
    """
    global SESSION_ID, SESSION_START, SEQUENCE
    
    elapsed = datetime.now() - SESSION_START
    
    # Read traces and compute stats
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration = 0
    tools_used = {}
    thinking_count = 0
    
    if TRACE_FILE.exists():
        with open(TRACE_FILE) as f:
            for line in f:
                if not line.strip():
                    continue
                trace = json.loads(line)
                if trace.get("session_id") == SESSION_ID:
                    total_input_tokens += trace.get("input_tokens_est", 0)
                    total_output_tokens += trace.get("output_tokens_est", 0)
                    total_duration += trace.get("duration_ms", 0)
                    tool = trace.get("tool", "unknown")
                    tools_used[tool] = tools_used.get(tool, 0) + 1
                    if tool == "think":
                        thinking_count += 1
    
    stats = {
        "session_id": SESSION_ID,
        "elapsed_seconds": round(elapsed.total_seconds()),
        "action_count": SEQUENCE,
        "thinking_steps": thinking_count,
        "total_input_tokens_est": round(total_input_tokens),
        "total_output_tokens_est": round(total_output_tokens),
        "total_tool_duration_ms": round(total_duration),
        "tools_used": tools_used,
    }
    
    return json.dumps(stats, indent=2)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys
    print(f"[Observer] Starting session {SESSION_ID}", file=sys.stderr)
    print(f"[Observer] Traces: {TRACE_FILE}", file=sys.stderr)
    mcp.run()