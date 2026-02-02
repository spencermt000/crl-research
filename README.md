# Add this to the top of your CLAUDE.md file
## 🔴 Use Observed Tools

When working in this folder, use the observed tools:

| Instead of... | Use... |
|---------------|--------|
| `bash_tool` | `observed_bash` |
| `view` | `observed_view` |
| `create_file` | `observed_create_file` |
| `str_replace` | `observed_str_replace` |

**Log your reasoning:**
observed_think(reasoning="Need to check if the analyzer handles empty traces")
observed_view(path="claude-trace/analyzer.py", description="checking edge cases")


# Use these commands to set it up in claude
claude

/mcp

claude mcp add observer -- python **INSERT THE FILE PATH TO mcp-observer/server.py

