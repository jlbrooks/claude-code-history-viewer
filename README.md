# Claude Code History Viewer

A local web application for browsing and exploring your Claude Code conversation history with an intuitive interface and advanced tool interaction display.

## Features

- **Multi-Project Support** - Browse all your Claude Code projects
- **Session Navigation** - View individual conversation sessions
- **Tool Interaction Display** - Beautifully rendered tool calls and results
- **Smart Content Handling** - Proper overflow handling for long content
- **Search & Filtering** - Find specific messages and interactions
- **Responsive Design** - Clean Tailwind CSS interface

## Installation

1. **Clone or download this repository**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the application:**
   ```bash
   python3 app.py
   ```

2. **Open your browser and go to:**
   ```
   http://127.0.0.1:5000
   ```

3. **Navigate your history:**
   - Select a project from the sidebar
   - Choose a session to view conversations
   - Use search and filters to find specific content
   - Click tool interactions to expand/collapse details

## How It Works

The app automatically scans your Claude Code history stored in `~/.claude/projects/` and presents it in an organized, browsable format:

```
Projects/
├── project-name-1/
│   ├── session-uuid-1.jsonl
│   └── session-uuid-2.jsonl
└── project-name-2/
    └── session-uuid-3.jsonl
```

## Interface

- **Left Sidebar**: Project and session navigation with breadcrumbs
- **Main Area**: Conversation history with syntax-highlighted tool interactions
- **Filters**: Search messages and filter by type (User/Assistant/Summary)

## Tool Interactions

The viewer specially handles Claude Code tool interactions:
- **🔧 Tool Calls** - Purple boxes showing tool name and parameters
- **📤 Tool Results** - Orange boxes displaying results and file operations
- **Expandable Content** - Long content is truncated with click-to-expand

## Requirements

- Python 3.6+
- Flask 3.0.0
- Access to `~/.claude/projects/` directory

## Development

The app consists of:
- `app.py` - Flask backend with Claude project scanning
- `templates/index.html` - Frontend with Tailwind CSS
- `requirements.txt` - Python dependencies

---

**Note**: This tool only reads your local Claude Code history files and does not connect to external services.