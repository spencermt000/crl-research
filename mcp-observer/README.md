# MCP Observer

An MCP server that wraps Claude Code's native tools to provide full observability.

## What It Does

Exposes these tools that mirror Claude Code's native ones:
- `observed_bash` → wraps `bash_tool`
- `observed_view` → wraps `view`
- `observed_create_file` → wraps `create_file`
- `observed_str_replace` → wraps `str_replace`

Each tool:
1. Logs the call (tool, inputs, timestamp)
2. Executes the real operation
3. Logs the result (output, duration, success/error)
4. Returns the result

## Data Captured

```json
{
  "session_id": "20240115_143022",
  "sequence": 5,
  "timestamp": "2024-01-15T14:30:45.123",
  "tool": "bash",
  "inputs": {"command": "npm test"},
  "output": "All tests passed",
  "duration_ms": 1234.5,
  "success": true,
  "input_tokens_est": 15,
  "output_tokens_est": 42
}
```

## Setup

### 1. Install dependencies

```bash
cd mcp-observer
pip install -r requirements.txt
```

### 2. Register with Claude Code

```bash
claude mcp add observer python /full/path/to/mcp-observer/server.py
```

Or add to your Claude Code config manually (check `~/.claude/` for config files).

### 3. Update your CLAUDE.md

Tell Claude Code to use the observed tools instead of native ones. See the example CLAUDE.md in this repo.

## Usage

### Start the viewer (Terminal 1)

```bash
cd mcp-observer
python viewer.py
```

This tails the trace file and shows actions in real-time.

### Run Claude Code (Terminal 2)

```bash
cd your-project
claude
```

Claude Code will use the observed tools (if CLAUDE.md instructs it to), and you'll see everything in the viewer.

## Real-Time Viewer

```
══════════════════════════════════════════════════════════════════════
  🔍 Claude Code Observer - Real-time Trace Viewer
══════════════════════════════════════════════════════════════════════
  Time      Status Tool         Duration   Tokens       Summary
──────────────────────────────────────────────────────────────────────
[14:30:22] ✓ view         (   12ms  in≈  15  out≈  200) src/app.py
[14:30:25] ✓ bash         (  340ms  in≈  20  out≈   50) npm test
[14:30:28] ✓ str_replace  (    5ms  in≈ 100  out≈   30) src/app.py
[14:30:30] ✓ bash         ( 1200ms  in≈  20  out≈  150) npm test

──────────────────────────────────────────────────────────────────────
  Totals: 4 actions | ~155 in + ~430 out tokens | 1.6s tool time
```

## Integration with claude-trace

Export traces for analysis:

```python
from claude_trace import TraceStorage, TraceAnalyzer

# Point to the observer's trace directory
storage = TraceStorage("./mcp-observer/traces")
analyzer = TraceAnalyzer(storage)

# Find patterns
patterns = analyzer.find_tool_sequences()
```

## Environment Variables

- `TRACE_DIR` — Directory for trace files (default: `./traces`)

## Limitations

- Requires Claude Code to *choose* to use observed_* tools
- This is controlled via CLAUDE.md prompting
- Native tools are still available; Claude might use them if not instructed otherwise
