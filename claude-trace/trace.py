#!/usr/bin/env python3
"""
Quick trace logger for Claude Code self-logging.

Usage from bash:
    python3 trace.py log --tool "bash_tool" --input '{"command": "ls"}' --output "file1 file2"
    python3 trace.py log --tool "create_file" --input '{"path": "foo.py"}' --output "created"
    
    python3 trace.py start --goal "Build the chrome extension"
    python3 trace.py end --success
    
    python3 trace.py show
    python3 trace.py stats
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Traces go in the project root
TRACE_DIR = Path(__file__).parent / "traces"
TRACE_FILE = TRACE_DIR / "current_session.jsonl"
SESSION_FILE = TRACE_DIR / "session_meta.json"


def ensure_dir():
    TRACE_DIR.mkdir(exist_ok=True)


def get_session():
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return None


def cmd_start(args):
    """Start a new logging session."""
    ensure_dir()
    
    session = {
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "goal": args.goal,
        "started_at": datetime.now().isoformat(),
        "sequence": 0,
    }
    
    SESSION_FILE.write_text(json.dumps(session, indent=2))
    
    # Clear current trace file for new session
    if TRACE_FILE.exists():
        # Archive old traces
        archive = TRACE_DIR / f"session_{session['session_id']}_prior.jsonl"
        TRACE_FILE.rename(archive)
    
    print(f"✓ Started session: {session['session_id']}")
    print(f"  Goal: {args.goal}")


def cmd_end(args):
    """End the current session."""
    session = get_session()
    if not session:
        print("No active session")
        return
    
    session["ended_at"] = datetime.now().isoformat()
    session["success"] = args.success
    
    # Save final session metadata
    archive_meta = TRACE_DIR / f"session_{session['session_id']}_meta.json"
    archive_meta.write_text(json.dumps(session, indent=2))
    
    # Archive traces
    if TRACE_FILE.exists():
        archive = TRACE_DIR / f"session_{session['session_id']}.jsonl"
        TRACE_FILE.rename(archive)
    
    # Clear current session
    SESSION_FILE.unlink()
    
    status = "✓ Success" if args.success else "✗ Failed"
    print(f"{status} - Session ended: {session['session_id']}")
    print(f"  Traces: {session['sequence']} actions logged")


def cmd_log(args):
    """Log a single action."""
    ensure_dir()
    
    session = get_session()
    session_id = session["session_id"] if session else "anonymous"
    sequence = session.get("sequence", 0) if session else 0
    
    # Parse input JSON
    try:
        inputs = json.loads(args.input) if args.input else {}
    except json.JSONDecodeError:
        inputs = {"raw": args.input}
    
    trace = {
        "session_id": session_id,
        "sequence": sequence,
        "timestamp": datetime.now().isoformat(),
        "tool": args.tool,
        "inputs": inputs,
        "output": args.output[:2000] if args.output else "",  # Truncate
        "success": not args.error,
        "error": args.error,
        "reasoning": args.reasoning,
    }
    
    # Append to trace file
    with open(TRACE_FILE, "a") as f:
        f.write(json.dumps(trace) + "\n")
    
    # Update sequence
    if session:
        session["sequence"] = sequence + 1
        SESSION_FILE.write_text(json.dumps(session, indent=2))
    
    # Brief output
    tool_short = args.tool[:15].ljust(15)
    print(f"  [{sequence:03d}] {tool_short} {'✓' if not args.error else '✗'}")


def cmd_show(args):
    """Show recent traces."""
    if not TRACE_FILE.exists():
        print("No traces yet")
        return
    
    with open(TRACE_FILE) as f:
        lines = f.readlines()
    
    n = args.n or 10
    for line in lines[-n:]:
        trace = json.loads(line)
        tool = trace["tool"][:20].ljust(20)
        seq = trace["sequence"]
        status = "✓" if trace.get("success", True) else "✗"
        
        # Summarize input
        inputs = trace.get("inputs", {})
        if "command" in inputs:
            summary = inputs["command"][:40]
        elif "path" in inputs:
            summary = inputs["path"]
        else:
            summary = str(inputs)[:40]
        
        print(f"[{seq:03d}] {status} {tool} {summary}")


def cmd_stats(args):
    """Show session statistics."""
    session = get_session()
    
    if session:
        print(f"Active session: {session['session_id']}")
        print(f"  Goal: {session.get('goal', 'N/A')}")
        print(f"  Actions: {session.get('sequence', 0)}")
        print(f"  Started: {session.get('started_at', 'N/A')}")
    else:
        print("No active session")
    
    # Count archived sessions
    archives = list(TRACE_DIR.glob("session_*_meta.json"))
    print(f"\nArchived sessions: {len(archives)}")
    
    # Total traces
    total = 0
    for f in TRACE_DIR.glob("*.jsonl"):
        with open(f) as fh:
            total += sum(1 for _ in fh)
    print(f"Total traces: {total}")


def main():
    parser = argparse.ArgumentParser(description="Claude Code trace logger")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # start
    p_start = subparsers.add_parser("start", help="Start a session")
    p_start.add_argument("--goal", "-g", required=True, help="Session goal")
    
    # end
    p_end = subparsers.add_parser("end", help="End a session")
    p_end.add_argument("--success", "-s", action="store_true", help="Mark as successful")
    
    # log
    p_log = subparsers.add_parser("log", help="Log an action")
    p_log.add_argument("--tool", "-t", required=True, help="Tool name")
    p_log.add_argument("--input", "-i", help="Input JSON")
    p_log.add_argument("--output", "-o", help="Output text")
    p_log.add_argument("--error", "-e", help="Error message if failed")
    p_log.add_argument("--reasoning", "-r", help="Reasoning/intent")
    
    # show
    p_show = subparsers.add_parser("show", help="Show recent traces")
    p_show.add_argument("-n", type=int, help="Number of traces to show")
    
    # stats
    p_stats = subparsers.add_parser("stats", help="Show statistics")
    
    args = parser.parse_args()
    
    commands = {
        "start": cmd_start,
        "end": cmd_end,
        "log": cmd_log,
        "show": cmd_show,
        "stats": cmd_stats,
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()