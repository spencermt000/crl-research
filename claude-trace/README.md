# Claude Trace

Observation and logging framework for Claude Code agents.

## Overview

This project captures traces of Claude Code's actions to enable:

1. **Observation** - See exactly what the agent does, step by step
2. **Pattern detection** - Find common sequences and behaviors
3. **Foundation for dynamic skills** - Data for training tGNN-based memory/retrieval

The long-term vision is to implement a hippocampus-inspired memory system where:
- Different action types are encoded as different "sensory modalities"
- Multiple DG (dentate gyrus) encoders feed into a shared CA3 auto-associator
- Skills emerge from pattern completion across encoded experiences

## Quick Start

```python
from claude_trace import ActionLogger, TraceAnalyzer, TraceViewer

# Create a logger
logger = ActionLogger("./data")

# Log a session
with logger.session(goal="Build a web scraper") as session:
    # Log individual actions
    logger.log_action(
        tool="bash_tool",
        inputs={"command": "pip install requests"},
        output="Successfully installed requests",
        success=True
    )
    
    logger.log_action(
        tool="create_file",
        inputs={"path": "scraper.py"},
        output="File created",
    )

# Analyze patterns
analyzer = TraceAnalyzer(logger.storage)
stats = analyzer.get_overall_stats()
patterns = analyzer.find_tool_sequences(min_frequency=2)

# View in terminal
viewer = TraceViewer("./data")
viewer.show_summary()
viewer.show_patterns()
```

## Data Model

### ActionTrace

The fundamental unit - a single action taken by the agent:

```python
ActionTrace(
    trace_id="abc123",
    session_id="20240115_143022",
    sequence_num=0,
    timestamp=datetime.now(),
    tool="bash_tool",
    tool_type=ToolType.BASH,
    inputs={"command": "ls -la"},
    output="...",
    modality=Modality.TOUCH,  # Inferred cognitive mode
    success=True,
)
```

### Modalities

We classify actions into cognitive "modalities" inspired by human senses:

| Modality | Actions | Character |
|----------|---------|-----------|
| TOUCH | grep, find, view | Local, probing, sequential |
| VISION | read docs, search | Broad, parallel, structural |
| TASTE | code→docs | Transformation, digestion |
| MOTOR | create, write | Expression, output |
| PROPRIO | test, run | Sensing state through action |
| PAIN | errors | Something's wrong |

## CLI Viewer

```bash
# Show summary
python -m claude_trace.viewer --data-dir ./data

# Show specific session
python -m claude_trace.viewer -s SESSION_ID -v

# Show patterns
python -m claude_trace.viewer --patterns

# Show transition probabilities
python -m claude_trace.viewer --transitions
python -m claude_trace.viewer --transitions --modalities
```

## Export for ML

```python
# For sequence modeling
sequences = analyzer.export_sequences_for_training()

# For temporal GNN
graph_data = analyzer.export_for_tgnn()
```

## Architecture

```
claude_trace/
├── models.py      # Data models: ActionTrace, Session, Modality
├── storage.py     # JSONL persistence
├── logger.py      # Core logging functionality  
├── analyzer.py    # Pattern detection, statistics
└── viewer.py      # Terminal visualization
```

## Future Work

- [ ] Real-time proxy for automatic capture
- [ ] Parse Claude Code conversation exports
- [ ] Web-based trace viewer
- [ ] tGNN encoder implementation
- [ ] Multiple DG encoders per modality
- [ ] CA3 auto-associative retrieval
- [ ] Skill distillation pipeline

## Philosophy

> "Knowledge is like a map of a place, skill is being there" 

We're building toward a system where:
- Early: Agent reasons through detailed skill files
- Later: Compressed patterns trigger efficient execution
- The transition is gradual, learned from experience
