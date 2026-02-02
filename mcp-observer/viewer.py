#!/usr/bin/env python3
"""
Real-time trace viewer.

Watches the trace file and displays actions as they happen.
Also shows running totals for tokens and time.

Usage:
    python viewer.py [--trace-file PATH]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


# ANSI colors
class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'


TOOL_COLORS = {
    'bash': C.YELLOW,
    'view': C.CYAN,
    'create_file': C.GREEN,
    'str_replace': C.MAGENTA,
    'think': C.BLUE,
}


def format_trace(trace: dict, show_full: bool = False) -> str:
    """Format a trace entry for display."""
    tool = trace.get('tool', 'unknown')
    seq = trace.get('sequence', 0)
    success = trace.get('success', True)
    duration = trace.get('duration_ms', 0)
    input_tokens = trace.get('input_tokens_est', 0)
    output_tokens = trace.get('output_tokens_est', 0)
    
    color = TOOL_COLORS.get(tool, C.RESET)
    status = f"{C.GREEN}✓{C.RESET}" if success else f"{C.RED}✗{C.RESET}"
    
    # Build summary based on tool type
    inputs = trace.get('inputs', {})
    if tool == 'bash':
        summary = inputs.get('command', '')[:60]
    elif tool == 'view':
        summary = inputs.get('path', '')
    elif tool == 'create_file':
        summary = inputs.get('path', '')
    elif tool == 'str_replace':
        summary = inputs.get('path', '')
    elif tool == 'think':
        summary = inputs.get('reasoning', '')[:70]
    else:
        summary = str(inputs)[:60]
    
    # Timestamp
    ts = trace.get('timestamp', '')
    if ts:
        try:
            dt = datetime.fromisoformat(ts)
            ts = dt.strftime('%H:%M:%S')
        except:
            pass
    
    line = f"{C.DIM}[{ts}]{C.RESET} {status} {C.BOLD}{color}{tool:12}{C.RESET} "
    line += f"{C.DIM}({duration:6.0f}ms  in≈{input_tokens:4.0f}  out≈{output_tokens:5.0f}){C.RESET} "
    line += f"{summary}"
    
    if not success and trace.get('error'):
        line += f"\n         {C.RED}Error: {trace['error']}{C.RESET}"
    
    return line


def print_header():
    """Print the viewer header."""
    print(f"\n{C.BOLD}{'═' * 70}{C.RESET}")
    print(f"{C.BOLD}  🔍 Claude Code Observer - Real-time Trace Viewer{C.RESET}")
    print(f"{C.BOLD}{'═' * 70}{C.RESET}")
    print(f"{C.DIM}  Time      Status Tool         Duration   Tokens       Summary{C.RESET}")
    print(f"{C.DIM}{'─' * 70}{C.RESET}")


def print_stats(traces: list):
    """Print running statistics."""
    total_input = sum(t.get('input_tokens_est', 0) for t in traces)
    total_output = sum(t.get('output_tokens_est', 0) for t in traces)
    total_duration = sum(t.get('duration_ms', 0) for t in traces)
    
    tools = {}
    for t in traces:
        tool = t.get('tool', 'unknown')
        tools[tool] = tools.get(tool, 0) + 1
    
    print(f"\n{C.DIM}{'─' * 70}{C.RESET}")
    print(f"{C.BOLD}  Totals:{C.RESET} {len(traces)} actions | "
          f"~{total_input:.0f} in + ~{total_output:.0f} out tokens | "
          f"{total_duration/1000:.1f}s tool time")
    print(f"{C.DIM}  Tools: {dict(tools)}{C.RESET}")


def tail_traces(trace_file: Path, poll_interval: float = 0.5):
    """Tail the trace file and yield new traces."""
    
    # Wait for file to exist
    while not trace_file.exists():
        print(f"{C.DIM}Waiting for trace file: {trace_file}{C.RESET}")
        time.sleep(1)
    
    # Start from current position
    with open(trace_file) as f:
        # Go to end
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass
            else:
                time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Real-time trace viewer")
    parser.add_argument(
        '--trace-file', '-f',
        default=str(Path(__file__).parent.parent / 'outputs' / 'traces' / 'live_trace.jsonl'),
        help='Path to trace file'
    )
    parser.add_argument(
        '--history', '-n',
        type=int,
        default=10,
        help='Number of historical traces to show'
    )
    args = parser.parse_args()
    
    trace_file = Path(args.trace_file)
    
    print_header()
    print(f"{C.DIM}  Trace file: {trace_file}{C.RESET}")
    
    # Load historical traces
    traces = []
    if trace_file.exists():
        with open(trace_file) as f:
            for line in f:
                if line.strip():
                    try:
                        traces.append(json.loads(line))
                    except:
                        pass
        
        # Show recent history
        for trace in traces[-args.history:]:
            print(format_trace(trace))
        
        if traces:
            print_stats(traces)
            print(f"\n{C.CYAN}>>> Watching for new traces...{C.RESET}\n")
    
    # Watch for new traces
    try:
        for trace in tail_traces(trace_file):
            traces.append(trace)
            print(format_trace(trace))
            
            # Update stats every 5 traces
            if len(traces) % 5 == 0:
                print_stats(traces)
    
    except KeyboardInterrupt:
        print(f"\n\n{C.YELLOW}Stopped.{C.RESET}")
        print_stats(traces)


if __name__ == '__main__':
    main()