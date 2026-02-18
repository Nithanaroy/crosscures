# CLAUDE.md - Project Guidelines

## Coding Conventions

### No Unicode/Emoji Symbols in Code
- **Never use emoji or non-ASCII characters** (e.g., checkmarks, arrows, icons like `✓`, `✅`, `❌`, `⚠️`, `📊`, `🔍`, `💾`, `🦆`, `📥`, `🔧`, `🔬`, `•`, `→`) in Python code, print statements, or string literals.
- Windows terminals and some environments have character encoding issues (e.g., `cp1252` codec) that cause crashes when encountering these symbols.
- Use ASCII-safe text labels instead:
  - Success: `[OK]`, `[DONE]`
  - Error: `[ERROR]`
  - Warning: `[WARN]`
  - Info: `[INFO]`
  - Section headers: `[SECTION_NAME]` (e.g., `[QUERY 1]`, `[IMPORT]`, `[INDEX]`)
  - Bullet points: `*` or `-`
  - Separators: `=`, `-`
