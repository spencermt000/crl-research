"""
Analysis utilities for exploring patterns in action traces.

This module provides tools for:
- Basic statistics and summaries
- Trajectory visualization
- Pattern detection
- Preparing data for tGNN training

Think of this as the "observation" phase - helping us understand
what patterns exist before we try to formalize them.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional, Iterator
from dataclasses import dataclass

from .models import ActionTrace, Session, Modality, ToolType
from .storage import TraceStorage


@dataclass
class TrajectoryStats:
    """Statistics about a trajectory (sequence of actions)."""
    length: int
    duration_ms: float
    tools_used: Counter
    modalities: Counter
    unique_files: set
    error_count: int
    success_rate: Optional[float]


@dataclass
class PatternMatch:
    """A detected pattern in trajectories."""
    pattern: list[str]  # Sequence of tools/modalities
    frequency: int
    example_sessions: list[str]
    avg_duration_ms: float


class TraceAnalyzer:
    """
    Analyze stored traces to find patterns and insights.
    
    Usage:
        analyzer = TraceAnalyzer(storage)
        stats = analyzer.get_overall_stats()
        patterns = analyzer.find_tool_sequences(min_length=3)
    """
    
    def __init__(self, storage: TraceStorage):
        self.storage = storage
    
    # -------------------------------------------------------------------------
    # Basic Statistics
    # -------------------------------------------------------------------------
    
    def get_overall_stats(self) -> dict:
        """Get high-level statistics about all traces."""
        traces = list(self.storage.iter_traces())
        
        if not traces:
            return {'total_traces': 0}
        
        tools = Counter(t.tool for t in traces)
        modalities = Counter(t.modality.value for t in traces)
        sessions = Counter(t.session_id for t in traces)
        
        # Time distribution
        timestamps = [t.timestamp for t in traces]
        time_span = max(timestamps) - min(timestamps)
        
        # Success rate
        with_outcome = [t for t in traces if t.success is not None]
        success_rate = (
            sum(1 for t in with_outcome if t.success) / len(with_outcome)
            if with_outcome else None
        )
        
        return {
            'total_traces': len(traces),
            'unique_sessions': len(sessions),
            'tools': dict(tools.most_common()),
            'modalities': dict(modalities.most_common()),
            'time_span_hours': time_span.total_seconds() / 3600,
            'success_rate': success_rate,
            'avg_traces_per_session': len(traces) / len(sessions) if sessions else 0,
        }
    
    def get_session_stats(self, session_id: str) -> Optional[TrajectoryStats]:
        """Get statistics for a specific session."""
        traces = list(self.storage.iter_traces(session_id=session_id))
        
        if not traces:
            return None
        
        tools = Counter(t.tool for t in traces)
        modalities = Counter(t.modality for t in traces)
        files = set()
        for t in traces:
            files.update(t.files_touched)
        
        errors = sum(1 for t in traces if t.error)
        with_outcome = [t for t in traces if t.success is not None]
        success_rate = (
            sum(1 for t in with_outcome if t.success) / len(with_outcome)
            if with_outcome else None
        )
        
        duration = (traces[-1].timestamp - traces[0].timestamp).total_seconds() * 1000
        
        return TrajectoryStats(
            length=len(traces),
            duration_ms=duration,
            tools_used=tools,
            modalities=modalities,
            unique_files=files,
            error_count=errors,
            success_rate=success_rate,
        )
    
    # -------------------------------------------------------------------------
    # Trajectory Analysis
    # -------------------------------------------------------------------------
    
    def get_trajectories(self) -> dict[str, list[ActionTrace]]:
        """Group traces by session into trajectories."""
        trajectories = defaultdict(list)
        
        for trace in self.storage.iter_traces():
            trajectories[trace.session_id].append(trace)
        
        # Sort each trajectory by sequence number
        for session_id in trajectories:
            trajectories[session_id].sort(key=lambda t: t.sequence_num)
        
        return dict(trajectories)
    
    def get_tool_sequence(self, session_id: str) -> list[str]:
        """Get the sequence of tools used in a session."""
        traces = sorted(
            self.storage.iter_traces(session_id=session_id),
            key=lambda t: t.sequence_num
        )
        return [t.tool for t in traces]
    
    def get_modality_sequence(self, session_id: str) -> list[Modality]:
        """Get the sequence of modalities in a session."""
        traces = sorted(
            self.storage.iter_traces(session_id=session_id),
            key=lambda t: t.sequence_num
        )
        return [t.modality for t in traces]
    
    # -------------------------------------------------------------------------
    # Pattern Detection
    # -------------------------------------------------------------------------
    
    def find_tool_sequences(
        self,
        min_length: int = 2,
        max_length: int = 5,
        min_frequency: int = 2,
    ) -> list[PatternMatch]:
        """
        Find common sequences of tool usage across sessions.
        
        This is a simple n-gram approach. More sophisticated pattern
        detection could use sequence mining algorithms.
        """
        trajectories = self.get_trajectories()
        
        # Extract all n-grams
        ngram_sessions = defaultdict(list)  # ngram -> list of session_ids
        ngram_durations = defaultdict(list)  # ngram -> list of durations
        
        for session_id, traces in trajectories.items():
            tools = [t.tool for t in traces]
            
            for n in range(min_length, min(max_length + 1, len(tools) + 1)):
                for i in range(len(tools) - n + 1):
                    ngram = tuple(tools[i:i+n])
                    ngram_sessions[ngram].append(session_id)
                    
                    # Calculate duration of this subsequence
                    if i + n <= len(traces):
                        start = traces[i].timestamp
                        end = traces[i + n - 1].timestamp
                        duration = (end - start).total_seconds() * 1000
                        ngram_durations[ngram].append(duration)
        
        # Filter and create matches
        patterns = []
        for ngram, sessions in ngram_sessions.items():
            if len(sessions) >= min_frequency:
                durations = ngram_durations[ngram]
                patterns.append(PatternMatch(
                    pattern=list(ngram),
                    frequency=len(sessions),
                    example_sessions=list(set(sessions))[:5],
                    avg_duration_ms=sum(durations) / len(durations) if durations else 0,
                ))
        
        # Sort by frequency
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        return patterns
    
    def find_modality_patterns(
        self,
        min_length: int = 2,
        max_length: int = 4,
        min_frequency: int = 2,
    ) -> list[PatternMatch]:
        """
        Find common sequences of modalities.
        
        This operates at a higher level of abstraction than tool sequences,
        potentially revealing cognitive patterns.
        """
        trajectories = self.get_trajectories()
        
        ngram_sessions = defaultdict(list)
        
        for session_id, traces in trajectories.items():
            modalities = [t.modality.value for t in traces]
            
            for n in range(min_length, min(max_length + 1, len(modalities) + 1)):
                for i in range(len(modalities) - n + 1):
                    ngram = tuple(modalities[i:i+n])
                    ngram_sessions[ngram].append(session_id)
        
        patterns = []
        for ngram, sessions in ngram_sessions.items():
            if len(sessions) >= min_frequency:
                patterns.append(PatternMatch(
                    pattern=list(ngram),
                    frequency=len(sessions),
                    example_sessions=list(set(sessions))[:5],
                    avg_duration_ms=0,  # Not computed for modalities
                ))
        
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        return patterns
    
    # -------------------------------------------------------------------------
    # Transition Analysis (for future tGNN)
    # -------------------------------------------------------------------------
    
    def compute_transition_matrix(
        self,
        use_modalities: bool = False
    ) -> dict[str, Counter]:
        """
        Compute transition probabilities between tools or modalities.
        
        Returns a dict where keys are source states and values are
        Counters of destination states.
        
        This is a first step toward understanding the "shape" of
        trajectories - which actions tend to follow which.
        """
        trajectories = self.get_trajectories()
        transitions = defaultdict(Counter)
        
        for session_id, traces in trajectories.items():
            if use_modalities:
                sequence = [t.modality.value for t in traces]
            else:
                sequence = [t.tool for t in traces]
            
            for i in range(len(sequence) - 1):
                source = sequence[i]
                dest = sequence[i + 1]
                transitions[source][dest] += 1
        
        return dict(transitions)
    
    def get_transition_probabilities(
        self,
        use_modalities: bool = False
    ) -> dict[str, dict[str, float]]:
        """Convert transition counts to probabilities."""
        transitions = self.compute_transition_matrix(use_modalities)
        
        probabilities = {}
        for source, counts in transitions.items():
            total = sum(counts.values())
            probabilities[source] = {
                dest: count / total
                for dest, count in counts.items()
            }
        
        return probabilities
    
    # -------------------------------------------------------------------------
    # Export for ML
    # -------------------------------------------------------------------------
    
    def export_sequences_for_training(
        self,
        include_outcome: bool = True
    ) -> list[dict]:
        """
        Export trajectories in a format suitable for sequence modeling.
        
        Returns list of dicts with:
        - session_id
        - goal (if available)
        - tool_sequence
        - modality_sequence  
        - success (if available)
        """
        trajectories = self.get_trajectories()
        sessions = {s.session_id: s for s in self.storage.iter_sessions()}
        
        exports = []
        for session_id, traces in trajectories.items():
            session = sessions.get(session_id)
            
            export = {
                'session_id': session_id,
                'goal': session.goal if session else traces[0].goal if traces else None,
                'tool_sequence': [t.tool for t in traces],
                'modality_sequence': [t.modality.value for t in traces],
                'timestamps': [t.timestamp.isoformat() for t in traces],
            }
            
            if include_outcome and session:
                export['success'] = session.success
            
            exports.append(export)
        
        return exports
    
    def export_for_tgnn(self) -> list[dict]:
        """
        Export trajectories in a format suitable for temporal GNN training.
        
        Each trajectory becomes a sequence of nodes with:
        - node features (tool, modality, etc.)
        - temporal position
        - edges to previous nodes
        """
        trajectories = self.get_trajectories()
        exports = []
        
        for session_id, traces in trajectories.items():
            nodes = []
            edges = []
            
            for i, trace in enumerate(traces):
                node = {
                    'id': i,
                    'tool': trace.tool,
                    'tool_type': trace.tool_type.value,
                    'modality': trace.modality.value,
                    'has_error': bool(trace.error),
                    'files_count': len(trace.files_touched),
                    'output_length': len(trace.output),
                    'temporal_position': i / len(traces),  # Normalized position
                }
                nodes.append(node)
                
                # Temporal edges: connect to previous nodes
                # Could also add causal edges based on file dependencies
                if i > 0:
                    edges.append({
                        'source': i - 1,
                        'target': i,
                        'type': 'temporal',
                    })
            
            exports.append({
                'session_id': session_id,
                'nodes': nodes,
                'edges': edges,
            })
        
        return exports
