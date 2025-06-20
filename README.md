# Claude Logs

A web application for browsing and exploring your Claude Code conversation history with an intuitive interface and advanced tool interaction display.

## Features

- **Multi-Project Support** - Browse all your Claude Code projects
- **Session Navigation** - View individual conversation sessions
- **Tool Interaction Display** - Beautifully rendered tool calls and results
- **Smart Content Handling** - Proper overflow handling for long content
- **Search & Filtering** - Find specific messages and interactions
- **File Upload Support** - Upload and view conversation files in the cloud
- **Dual Mode Operation** - Local, cloud, or hybrid functionality
- **Session Management** - Automatic cleanup of uploaded files
- **Responsive Design** - Clean Tailwind CSS interface

## Installation

1. **Clone or download this repository**
2. **Install dependencies:**
   ```bash
   uv sync
   ```

## Usage

### Local Mode (Default)
1. **Start the application:**
   ```bash
   uv run python app.py
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

### Cloud Mode (File Upload)
For cloud deployment or file upload functionality:

1. **Set environment variables:**
   ```bash
   export CLAUDE_MODE=cloud  # or hybrid for both local and upload
   export SECRET_KEY=your-secret-key-here
   uv run python app.py
   ```

2. **Upload conversation files:**
   - Drag and drop JSONL files into the upload area
   - Or click to browse and select files
   - View uploaded conversations using the same interface
   - Delete files when no longer needed

### Operating Modes
- **LOCAL**: Only show local Claude Code projects (default)
- **CLOUD**: Only show upload functionality
- **HYBRID**: Show both local projects and upload functionality

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

- Python 3.8+
- Flask 3.0.0
- Access to `~/.claude/projects/` directory (for local mode)

## Configuration

The application can be configured using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_MODE` | `hybrid` | Operating mode: `local`, `cloud`, or `hybrid` |
| `SECRET_KEY` | `dev-secret-key...` | Flask secret key (change for production) |
| `UPLOAD_FOLDER` | System temp dir | Directory for uploaded files |
| `MAX_CONTENT_LENGTH` | `10485760` | Max upload size in bytes (10MB) |
| `SESSION_TIMEOUT_HOURS` | `24` | Hours before uploaded files are cleaned up |

## Cloud Deployment

### Fly.io Deployment (Recommended)

Deploy to fly.io with one command:

```bash
./deploy.sh
```

Or manually:
```bash
flyctl apps create claude-logs
flyctl volumes create uploads_data --region sjc --size 1
flyctl secrets set SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
flyctl deploy
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

### Generic Cloud Deployment

For other cloud providers:

1. **Set production environment variables:**
   ```bash
   export CLAUDE_MODE=cloud
   export SECRET_KEY=your-secure-random-secret-key
   export UPLOAD_FOLDER=/app/uploads
   export MAX_CONTENT_LENGTH=52428800  # 50MB
   ```

2. **Use the included Dockerfile:**
   ```bash
   docker build -t claude-logs .
   docker run -p 8080:8080 -e SECRET_KEY="your-key" claude-logs
   ```

3. **Or use a production WSGI server:**
   ```bash
   uv sync
   uv run gunicorn -w 4 -b 0.0.0.0:8080 app:app
   ```

### Security considerations:
- Set a strong, random SECRET_KEY
- Configure appropriate file size limits
- Set up proper session cleanup
- Use HTTPS in production
- Consider rate limiting for uploads

## Development

The app consists of:
- `app.py` - Flask backend with Claude project scanning
- `templates/index.html` - Frontend with Tailwind CSS
- `pyproject.toml` - Python dependencies and project configuration

---

**Note**: This tool only reads your local Claude Code history files and does not connect to external services.