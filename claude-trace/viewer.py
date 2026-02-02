"""
CLI viewer for browsing and visualizing traces.

Simple terminal-based interface for exploring logged sessions
and action traces. Good for quick debugging and pattern spotting.
"""

import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from .models import ActionTrace, Modality
from .storage import TraceStorage
from .analyzer import TraceAnalyzer


# ANSI color codes for terminal output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    
    # Modality colors
    MODALITY_COLORS = {
        Modality.TOUCH: '\033[94m',      # Blue
        Modality.VISION: '\033[96m',     # Cyan
        Modality.TASTE: '\033[95m',      # Magenta
        Modality.MOTOR: '\033[92m',      # Green
        Modality.PROPRIO: '\033[93m',    # Yellow
        Modality.PAIN: '\033[91m',       # Red
        Modality.UNKNOWN: '\033[90m',    # Gray
    }


def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Colors.RESET}"


def truncate(text: str, max_length: int = 80) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


class TraceViewer:
    """
    Terminal-based viewer for traces and sessions.
    
    Usage:
        viewer = TraceViewer("/path/to/data")
        viewer.show_summary()
        viewer.show_session("session_id")
    """
    
    def __init__(self, data_dir: str | Path):
        self.storage = TraceStorage(data_dir)
        self.analyzer = TraceAnalyzer(self.storage)
    
    def show_summary(self) -> None:
        """Show high-level summary of all logged data."""
        stats = self.analyzer.get_overall_stats()
        
        print(colorize("\n═══ TRACE SUMMARY ═══", Colors.BOLD))
        print(f"Total traces: {colorize(str(stats.get('total_traces', 0)), Colors.CYAN)}")
        print(f"Unique sessions: {colorize(str(stats.get('unique_sessions', 0)), Colors.CYAN)}")
        
        if stats.get('time_span_hours'):
            print(f"Time span: {stats['time_span_hours']:.1f} hours")
        
        if stats.get('success_rate') is not None:
            rate = stats['success_rate'] * 100
            color = Colors.GREEN if rate > 80 else Colors.YELLOW if rate > 50 else Colors.RED
            print(f"Success rate: {colorize(f'{rate:.1f}%', color)}")
        
        # Tools breakdown
        if stats.get('tools'):
            print(colorize("\nTools used:", Colors.BOLD))
            for tool, count in list(stats['tools'].items())[:10]:
                bar = '█' * min(count, 30)
                print(f"  {tool:20} {colorize(bar, Colors.BLUE)} {count}")
        
        # Modalities breakdown
        if stats.get('modalities'):
            print(colorize("\nModalities:", Colors.BOLD))
            for mod, count in stats['modalities'].items():
                mod_enum = Modality(mod)
                color = Colors.MODALITY_COLORS.get(mod_enum, Colors.DIM)
                bar = '█' * min(count, 30)
                print(f"  {mod:12} {colorize(bar, color)} {count}")
        
        print()
    
    def list_sessions(self, limit: int = 20) -> None:
        """List recent sessions."""
        sessions = list(self.storage.iter_sessions())
        
        if not sessions:
            print(colorize("No sessions found.", Colors.DIM))
            return
        
        print(colorize("\n═══ SESSIONS ═══", Colors.BOLD))
        print(f"{'ID':<20} {'Started':<20} {'Traces':<8} {'Goal':<40}")
        print("─" * 90)
        
        for session in sessions[-limit:]:
            trace_count = len(session.traces)
            goal = truncate(session.goal or "(no goal)", 40)
            started = session.started_at.strftime("%Y-%m-%d %H:%M")
            
            status = ""
            if session.success is True:
                status = colorize("✓", Colors.GREEN)
            elif session.success is False:
                status = colorize("✗", Colors.RED)
            
            print(f"{session.session_id:<20} {started:<20} {trace_count:<8} {goal} {status}")
        
        print()
    
    def show_session(self, session_id: str, verbose: bool = False) -> None:
        """Show details of a specific session."""
        traces = list(self.storage.iter_traces(session_id=session_id))
        
        if not traces:
            print(colorize(f"No traces found for session: {session_id}", Colors.RED))
            return
        
        # Header
        print(colorize(f"\n═══ SESSION: {session_id} ═══", Colors.BOLD))
        
        if traces[0].goal:
            print(colorize(f"Goal: {traces[0].goal}", Colors.DIM))
        
        stats = self.analyzer.get_session_stats(session_id)
        if stats:
            print(f"Duration: {stats.duration_ms:.0f}ms | "
                  f"Actions: {stats.length} | "
                  f"Files: {len(stats.unique_files)}")
        
        print()
        
        # Timeline
        print(colorize("Timeline:", Colors.BOLD))
        for i, trace in enumerate(traces):
            self._print_trace(trace, i, verbose)
        
        print()
    
    def _print_trace(self, trace: ActionTrace, index: int, verbose: bool = False) -> None:
        """Print a single trace entry."""
        # Modality indicator
        mod_color = Colors.MODALITY_COLORS.get(trace.modality, Colors.DIM)
        mod_icon = self._modality_icon(trace.modality)
        
        # Status indicator
        if trace.error:
            status = colorize("✗", Colors.RED)
        elif trace.success:
            status = colorize("✓", Colors.GREEN)
        else:
            status = " "
        
        # Time
        time_str = trace.timestamp.strftime("%H:%M:%S")
        
        # Tool and summary
        tool = colorize(trace.tool, Colors.CYAN)
        summary = self._summarize_action(trace)
        
        # Print main line
        print(f"  {colorize(mod_icon, mod_color)} {index:3d} [{time_str}] {status} {tool}")
        print(f"       {colorize(summary, Colors.DIM)}")
        
        if verbose:
            # Show inputs
            if trace.inputs:
                inputs_str = json.dumps(trace.inputs, indent=2)
                for line in inputs_str.split('\n')[:5]:
                    print(f"         {colorize(line, Colors.DIM)}")
            
            # Show output preview
            if trace.output:
                output_preview = truncate(trace.output.replace('\n', ' '), 60)
                print(f"         → {output_preview}")
        
        if trace.error:
            print(f"         {colorize('ERROR: ' + truncate(trace.error, 60), Colors.RED)}")
    
    def _modality_icon(self, modality: Modality) -> str:
        """Get an icon for a modality."""
        icons = {
            Modality.TOUCH: '👆',
            Modality.VISION: '👁',
            Modality.TASTE: '👅',
            Modality.MOTOR: '✍',
            Modality.PROPRIO: '🔄',
            Modality.PAIN: '⚠',
            Modality.UNKNOWN: '?',
        }
        return icons.get(modality, '?')
    
    def _summarize_action(self, trace: ActionTrace) -> str:
        """Generate a brief summary of an action."""
        inputs = trace.inputs
        
        if trace.tool == 'bash_tool':
            cmd = inputs.get('command', '')
            return truncate(cmd, 60)
        
        if trace.tool in ['view', 'create_file', 'str_replace']:
            path = inputs.get('path', '')
            return path
        
        if trace.tool == 'web_search':
            query = inputs.get('query', '')
            return f'"{query}"'
        
        # Generic fallback
        if inputs:
            key = list(inputs.keys())[0]
            val = str(inputs[key])
            return truncate(f"{key}={val}", 60)
        
        return ""
    
    def show_patterns(self, min_frequency: int = 2) -> None:
        """Show detected patterns in tool usage."""
        patterns = self.analyzer.find_tool_sequences(min_frequency=min_frequency)
        
        if not patterns:
            print(colorize("No patterns found.", Colors.DIM))
            return
        
        print(colorize("\n═══ TOOL PATTERNS ═══", Colors.BOLD))
        print(f"Patterns occurring at least {min_frequency} times:\n")
        
        for pattern in patterns[:15]:
            freq = colorize(str(pattern.frequency), Colors.CYAN)
            seq = " → ".join(pattern.pattern)
            print(f"  [{freq}x] {seq}")
        
        # Modality patterns
        mod_patterns = self.analyzer.find_modality_patterns(min_frequency=min_frequency)
        
        if mod_patterns:
            print(colorize("\n═══ MODALITY PATTERNS ═══", Colors.BOLD))
            
            for pattern in mod_patterns[:10]:
                freq = colorize(str(pattern.frequency), Colors.CYAN)
                seq = " → ".join(pattern.pattern)
                print(f"  [{freq}x] {seq}")
        
        print()
    
    def show_transitions(self, use_modalities: bool = False) -> None:
        """Show transition probabilities as a simple matrix."""
        probs = self.analyzer.get_transition_probabilities(use_modalities)
        
        if not probs:
            print(colorize("No transitions found.", Colors.DIM))
            return
        
        kind = "Modality" if use_modalities else "Tool"
        print(colorize(f"\n═══ {kind.upper()} TRANSITIONS ═══", Colors.BOLD))
        
        for source, dests in probs.items():
            print(f"\n  From {colorize(source, Colors.CYAN)}:")
            
            # Sort by probability
            sorted_dests = sorted(dests.items(), key=lambda x: x[1], reverse=True)
            
            for dest, prob in sorted_dests[:5]:
                bar_len = int(prob * 20)
                bar = '█' * bar_len
                print(f"    → {dest:20} {colorize(bar, Colors.GREEN)} {prob:.0%}")
        
        print()


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="View Claude Code action traces")
    parser.add_argument('--data-dir', '-d', default='./data', help='Path to trace data')
    parser.add_argument('--session', '-s', help='Show specific session')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--patterns', '-p', action='store_true', help='Show patterns')
    parser.add_argument('--transitions', '-t', action='store_true', help='Show transitions')
    parser.add_argument('--modalities', '-m', action='store_true', help='Use modalities (with -t)')
    
    args = parser.parse_args()
    
    viewer = TraceViewer(args.data_dir)
    
    if args.session:
        viewer.show_session(args.session, verbose=args.verbose)
    elif args.patterns:
        viewer.show_patterns()
    elif args.transitions:
        viewer.show_transitions(use_modalities=args.modalities)
    else:
        viewer.show_summary()
        viewer.list_sessions()


if __name__ == '__main__':
    main()
