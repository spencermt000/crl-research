"""
Core logging functionality for capturing Claude Code actions.

This module provides the main interface for observing and recording
agent actions. It can be used in several modes:

1. Manual logging - explicitly call log_action() 
2. Wrapper mode - wrap tool calls to auto-capture
3. Parse mode - parse conversation logs after the fact

The goal is to capture rich traces that can later be analyzed
for patterns and used to train/retrieve skills.
"""

import uuid
import time
import re
import json
from datetime import datetime
from typing import Optional, Any, Callable
from pathlib import Path
from contextlib import contextmanager
from functools import wraps

from .models import ActionTrace, ToolType, Modality, Session
from .storage import TraceStorage, SessionBuilder


class ActionLogger:
    """
    Main logger for capturing agent actions.
    
    Usage:
        logger = ActionLogger("/path/to/data")
        
        with logger.session(goal="Build a web scraper") as session:
            # Actions are logged automatically or manually
            logger.log_action(
                tool="bash_tool",
                inputs={"command": "ls -la"},
                output="...",
            )
    """
    
    def __init__(self, data_dir: str | Path = "./data"):
        self.storage = TraceStorage(data_dir)
        self._current_session: Optional[SessionBuilder] = None
        self._current_goal: Optional[str] = None
    
    @contextmanager
    def session(self, goal: Optional[str] = None, session_id: Optional[str] = None):
        """
        Context manager for a logging session.
        
        Args:
            goal: The user's stated goal/request
            session_id: Optional custom session ID
        
        Yields:
            SessionBuilder for the active session
        """
        self._current_session = SessionBuilder(
            storage=self.storage,
            session_id=session_id,
            goal=goal,
        )
        self._current_goal = goal
        
        try:
            yield self._current_session
        finally:
            if not self._current_session.session.completed:
                self._current_session.complete()
            self._current_session = None
            self._current_goal = None
    
    def log_action(
        self,
        tool: str,
        inputs: dict[str, Any],
        output: str,
        duration_ms: Optional[float] = None,
        reasoning: Optional[str] = None,
        success: Optional[bool] = None,
        error: Optional[str] = None,
        prior_state_hash: Optional[str] = None,
        posterior_state_hash: Optional[str] = None,
    ) -> ActionTrace:
        """
        Log a single action.
        
        Args:
            tool: Name of the tool used
            inputs: Input parameters to the tool
            output: Raw output from the tool
            duration_ms: How long the action took
            reasoning: Agent's stated reasoning (if available)
            success: Whether the action succeeded
            error: Error message if failed
            prior_state_hash: Hash of state before action
            posterior_state_hash: Hash of state after action
        
        Returns:
            The created ActionTrace
        """
        # Extract files touched from inputs
        files_touched = self._extract_files_touched(tool, inputs)
        
        # Classify tool type
        tool_type = ToolType.from_tool_name(tool)
        
        # Infer modality (basic heuristic for now)
        modality = self._infer_modality(tool, inputs, output)
        
        trace = ActionTrace(
            trace_id=str(uuid.uuid4())[:8],
            session_id=self._current_session.session_id if self._current_session else "anonymous",
            sequence_num=0,  # Will be set by SessionBuilder
            timestamp=datetime.now(),
            tool=tool,
            tool_type=tool_type,
            inputs=inputs,
            output=output[:10000] if output else "",  # Truncate very long outputs
            duration_ms=duration_ms,
            goal=self._current_goal,
            reasoning=reasoning,
            files_touched=files_touched,
            success=success,
            error=error,
            prior_state_hash=prior_state_hash,
            posterior_state_hash=posterior_state_hash,
            modality=modality,
        )
        
        if self._current_session:
            self._current_session.add_trace(trace)
        else:
            # Log without session context
            self.storage.append_trace(trace)
        
        return trace
    
    def _extract_files_touched(self, tool: str, inputs: dict) -> list[str]:
        """Extract file paths from tool inputs."""
        files = []
        
        # Common patterns
        if 'path' in inputs:
            files.append(inputs['path'])
        if 'file_path' in inputs:
            files.append(inputs['file_path'])
        if 'filepath' in inputs:
            files.append(inputs['filepath'])
        
        # Bash commands - try to extract file references
        if tool == 'bash_tool' and 'command' in inputs:
            cmd = inputs['command']
            # Simple heuristic: look for path-like strings
            potential_paths = re.findall(r'[/\w.-]+\.[a-z]+', cmd)
            files.extend(potential_paths)
        
        return list(set(files))
    
    def _infer_modality(self, tool: str, inputs: dict, output: str) -> Modality:
        """
        Infer the cognitive modality of an action.
        
        This is a basic heuristic. Later, this could be learned
        from patterns in the data.
        """
        # Touch: probing, local, sequential
        if tool in ['view', 'bash_tool']:
            cmd = inputs.get('command', '')
            if any(x in cmd for x in ['grep', 'find', 'ls', 'cat', 'head', 'tail']):
                return Modality.TOUCH
        
        # Vision: broad, structural understanding
        if tool in ['read_page', 'web_search', 'web_fetch']:
            return Modality.VISION
        
        # Motor: creation, expression
        if tool in ['create_file', 'str_replace', 'file_create']:
            return Modality.MOTOR
        
        # Pain: error states
        if output and any(x in output.lower() for x in ['error', 'failed', 'exception', 'traceback']):
            return Modality.PAIN
        
        # Proprioception: running/testing
        if tool == 'bash_tool':
            cmd = inputs.get('command', '')
            if any(x in cmd for x in ['python', 'node', 'npm', 'pytest', 'test']):
                return Modality.PROPRIO
        
        return Modality.UNKNOWN
    
    def wrap_tool(self, tool_name: str) -> Callable:
        """
        Decorator to wrap a tool function and auto-log calls.
        
        Usage:
            @logger.wrap_tool("bash_tool")
            def bash_tool(command: str) -> str:
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                error = None
                output = ""
                success = True
                
                try:
                    output = func(*args, **kwargs)
                    return output
                except Exception as e:
                    error = str(e)
                    success = False
                    raise
                finally:
                    duration_ms = (time.time() - start_time) * 1000
                    self.log_action(
                        tool=tool_name,
                        inputs=kwargs if kwargs else {'args': args},
                        output=str(output) if output else "",
                        duration_ms=duration_ms,
                        success=success,
                        error=error,
                    )
            
            return wrapper
        return decorator


class ConversationParser:
    """
    Parse Claude Code conversation logs to extract action traces.
    
    This is useful for analyzing past conversations that weren't
    logged in real-time.
    """
    
    def __init__(self, logger: ActionLogger):
        self.logger = logger
    
    def parse_jsonl_export(self, filepath: str | Path) -> list[ActionTrace]:
        """
        Parse a JSONL export of Claude Code conversations.
        
        Expected format: One JSON object per line with tool calls
        """
        traces = []
        filepath = Path(filepath)
        
        with open(filepath, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                
                data = json.loads(line)
                
                # Extract tool calls from the message
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        trace = self.logger.log_action(
                            tool=call.get('name', 'unknown'),
                            inputs=call.get('inputs', {}),
                            output=call.get('output', ''),
                        )
                        traces.append(trace)
        
        return traces
    
    def parse_markdown_log(self, content: str, goal: Optional[str] = None) -> list[ActionTrace]:
        """
        Parse a markdown-formatted conversation log.
        
        Looks for code blocks with tool invocations.
        """
        traces = []
        
        # Pattern for tool invocations in XML-like format
        # This is a simplified pattern - real parsing would be more robust
        tool_pattern = r'invoke name="(\w+)"'
        param_pattern = r'parameter name="(\w+)">([^<]*)<'
        
        tool_matches = re.finditer(tool_pattern, content)
        
        with self.logger.session(goal=goal) as session:
            for match in tool_matches:
                tool_name = match.group(1)
                
                # Find parameters after this tool
                start_pos = match.end()
                end_pos = content.find('/invoke', start_pos)
                if end_pos == -1:
                    end_pos = len(content)
                
                param_section = content[start_pos:end_pos]
                params = dict(re.findall(param_pattern, param_section))
                
                trace = self.logger.log_action(
                    tool=tool_name,
                    inputs=params,
                    output="[parsed from log]",
                )
                traces.append(trace)
        
        return traces
