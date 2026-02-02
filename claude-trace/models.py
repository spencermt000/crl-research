"""
Data models for Claude Code action tracing.

These models capture the structure of agent actions in a way that's
amenable to later analysis, pattern recognition, and tGNN encoding.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from datetime import datetime
from enum import Enum
import hashlib
import json


class ToolType(str, Enum):
    """Categories of tools - these may map to different 'sensory modalities' later."""
    
    # "Touch" - local, probing, sequential
    VIEW = "view"
    BASH = "bash_tool"
    
    # "Vision" - broad, structural understanding
    READ_PAGE = "read_page"
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"
    
    # "Motor" - creation, expression
    CREATE_FILE = "create_file"
    STR_REPLACE = "str_replace"
    
    # "Proprioception" - sensing state through action
    EXECUTE = "execute"
    
    # Meta / other
    UNKNOWN = "unknown"
    
    @classmethod
    def from_tool_name(cls, name: str) -> "ToolType":
        """Map a tool name string to a ToolType."""
        mapping = {
            "view": cls.VIEW,
            "bash_tool": cls.BASH,
            "read_page": cls.READ_PAGE,
            "web_search": cls.WEB_SEARCH,
            "web_fetch": cls.WEB_FETCH,
            "create_file": cls.CREATE_FILE,
            "str_replace": cls.STR_REPLACE,
            "file_create": cls.CREATE_FILE,
        }
        return mapping.get(name.lower(), cls.UNKNOWN)


class Modality(str, Enum):
    """
    Cognitive modalities - how different actions 'feel' in terms of
    information processing. This is speculative and will be refined
    based on observation.
    """
    TOUCH = "touch"          # probing, local, sequential (grep, find, view)
    VISION = "vision"        # broad, parallel, structural (read docs, search)
    TASTE = "taste"          # transformation, digestion (code -> docs)
    MOTOR = "motor"          # creation, expression (write, create)
    PROPRIO = "proprio"      # state sensing through action (test, run)
    PAIN = "pain"            # error detection, debugging
    UNKNOWN = "unknown"


@dataclass
class ActionTrace:
    """
    A single action taken by the agent.
    
    This is the fundamental unit of observation. Collections of these
    form trajectories that can be analyzed for patterns.
    """
    
    # Identity
    trace_id: str
    session_id: str
    sequence_num: int  # order within session
    timestamp: datetime
    
    # The action itself
    tool: str
    tool_type: ToolType
    inputs: dict[str, Any]
    output: str
    duration_ms: Optional[float] = None
    
    # Context
    goal: Optional[str] = None  # user's original request
    reasoning: Optional[str] = None  # agent's stated intent
    files_touched: list[str] = field(default_factory=list)
    
    # Outcome signals
    success: Optional[bool] = None
    error: Optional[str] = None
    
    # State hashing for tGNN
    prior_state_hash: Optional[str] = None
    posterior_state_hash: Optional[str] = None
    
    # Future: modality classification
    modality: Modality = Modality.UNKNOWN
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        d['tool_type'] = self.tool_type.value
        d['modality'] = self.modality.value
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> "ActionTrace":
        """Reconstruct from dictionary."""
        d = d.copy()
        d['timestamp'] = datetime.fromisoformat(d['timestamp'])
        d['tool_type'] = ToolType(d['tool_type'])
        d['modality'] = Modality(d.get('modality', 'unknown'))
        return cls(**d)
    
    def compute_output_hash(self) -> str:
        """Hash the output for state comparison."""
        return hashlib.sha256(self.output.encode()).hexdigest()[:16]


@dataclass
class Session:
    """
    A session represents a single task/conversation with the agent.
    Contains a sequence of ActionTraces.
    """
    
    session_id: str
    started_at: datetime
    goal: Optional[str] = None
    traces: list[ActionTrace] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Outcome
    completed: bool = False
    success: Optional[bool] = None
    
    def add_trace(self, trace: ActionTrace):
        """Add a trace to this session."""
        self.traces.append(trace)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Total session duration."""
        if not self.traces:
            return None
        start = self.traces[0].timestamp
        end = self.traces[-1].timestamp
        return (end - start).total_seconds() * 1000
    
    @property
    def tool_sequence(self) -> list[str]:
        """Get the sequence of tools used."""
        return [t.tool for t in self.traces]
    
    @property
    def modality_sequence(self) -> list[Modality]:
        """Get the sequence of modalities."""
        return [t.modality for t in self.traces]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'session_id': self.session_id,
            'started_at': self.started_at.isoformat(),
            'goal': self.goal,
            'traces': [t.to_dict() for t in self.traces],
            'metadata': self.metadata,
            'completed': self.completed,
            'success': self.success,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        """Reconstruct from dictionary."""
        return cls(
            session_id=d['session_id'],
            started_at=datetime.fromisoformat(d['started_at']),
            goal=d.get('goal'),
            traces=[ActionTrace.from_dict(t) for t in d.get('traces', [])],
            metadata=d.get('metadata', {}),
            completed=d.get('completed', False),
            success=d.get('success'),
        )


@dataclass 
class StateSnapshot:
    """
    A snapshot of relevant state at a point in time.
    Used for computing state deltas and hashes.
    """
    
    timestamp: datetime
    files: dict[str, str]  # path -> content hash
    working_directory: str
    open_files: list[str]
    recent_outputs: list[str]
    
    def compute_hash(self) -> str:
        """Compute a hash of this state."""
        content = json.dumps({
            'files': self.files,
            'wd': self.working_directory,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
