# CRL Research: Dynamic Skills for AI Agents

## Overview

This project explores how AI agents can develop "dynamic skills" — knowledge that shifts from explicit/effortful to automatic/compressed over time, inspired by how humans develop procedural memory.

Core hypothesis: By observing agent behavior patterns (via MCP), we can identify recurring action sequences and eventually compress them into efficient, retrievable skills.

## Folder Structure

```
crl-research/
├── mcp-observer/       # MCP server for observing Claude Code
│   ├── server.py       # Exposes observed_* tools + observed_think
│   ├── viewer.py       # Real-time terminal viewer
│   └── traces/         # All captured traces (JSONL)
├── claude-trace/       # Analysis framework
│   ├── models.py       # Data models (ActionTrace, Session, Modality)
│   ├── storage.py      # JSONL storage utilities
│   ├── analyzer.py     # Pattern detection, transitions
│   └── viewer.py       # Terminal visualization
└── CLAUDE.md           # This file
```

## Research Goals

1. **Observe** — Capture agent tool use + reasoning via MCP
2. **Patterns** — Find common action sequences across tasks
3. **Modalities** — Classify actions by "cognitive mode" (touch/vision/motor/etc.)
4. **Encode** — Build tGNN representations of action trajectories
5. **Retrieve** — Pattern-complete from partial cues (like hippocampal CA3)
6. **Compress** — Distill frequent patterns into efficient skills

## Key Ideas

**Multimodal encoding (DG → CA3):**
- Different action types encoded by different "sensory" encoders
- Multiple DG encoders feed into shared CA3 for auto-association
- Same experience gets redundant encodings for robust retrieval

**Modality mapping:**
| Modality | Actions | Character |
|----------|---------|-----------|
| Touch | grep, find, view file | Probing, local, sequential |
| Vision | read docs, search | Broad, parallel, structural |
| Motor | create, write, edit | Expression, output |
| Proprio | run, test | Sensing state through action |
| Pain | errors, failures | Something's wrong |

---

## 🔴 Use Observed Tools

When working in this folder, use the observed tools:

| Instead of... | Use... |
|---------------|--------|
| `bash_tool` | `observed_bash` |
| `view` | `observed_view` |
| `create_file` | `observed_create_file` |
| `str_replace` | `observed_str_replace` |

**Log your reasoning:**
```
observed_think(reasoning="Need to check if the analyzer handles empty traces")
observed_view(path="claude-trace/analyzer.py", description="checking edge cases")
```

---

## Running the Observer

**Terminal 1 — Viewer:**
```bash
cd mcp-observer
python viewer.py
```

**Terminal 2 — Claude Code:**
```bash
claude
```

---

## Analysis

```python
from claude_trace import TraceStorage, TraceAnalyzer

storage = TraceStorage("./mcp-observer/traces")
analyzer = TraceAnalyzer(storage)

# Find patterns
patterns = analyzer.find_tool_sequences()
transitions = analyzer.get_transition_probabilities()

# Export for ML
tgnn_data = analyzer.export_for_tgnn()
```

---

## Next Steps

- [ ] Collect traces across multiple projects/tasks
- [ ] Build post-hoc reasoning reconstructor
- [ ] Implement modality classification
- [ ] Design tGNN architecture for trajectory encoding
- [ ] Experiment with retrieval from partial cues