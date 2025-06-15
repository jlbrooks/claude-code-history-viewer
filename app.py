from flask import Flask, render_template, jsonify, request
import json
import os
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

class ClaudeProjectManager:
    def __init__(self, claude_dir=None):
        self.claude_dir = claude_dir or os.path.expanduser('~/.claude/projects')
        
    def decode_project_path(self, encoded_path):
        """Convert encoded project path back to readable format"""
        # Remove leading dash and convert remaining dashes back to slashes
        if encoded_path.startswith('-'):
            decoded = encoded_path[1:].replace('-', '/')
            # Extract just the project name (last part of path)
            return os.path.basename(decoded)
        return encoded_path
    
    def get_projects(self):
        """Get all available Claude projects"""
        projects = []
        if not os.path.exists(self.claude_dir):
            return projects
            
        for item in os.listdir(self.claude_dir):
            project_path = os.path.join(self.claude_dir, item)
            if os.path.isdir(project_path) and not item.startswith('.'):
                # Get session files
                session_files = [f for f in os.listdir(project_path) 
                               if f.endswith('.jsonl')]
                
                projects.append({
                    'id': item,
                    'name': self.decode_project_path(item),
                    'encoded_path': item,
                    'session_count': len(session_files),
                    'sessions': session_files
                })
        
        return sorted(projects, key=lambda x: x['name'])
    
    def get_project_sessions(self, project_id):
        """Get all sessions for a specific project"""
        project_path = os.path.join(self.claude_dir, project_id)
        if not os.path.exists(project_path):
            return []
            
        sessions = []
        for filename in os.listdir(project_path):
            if filename.endswith('.jsonl'):
                file_path = os.path.join(project_path, filename)
                try:
                    # Get file stats
                    stat = os.stat(file_path)
                    file_size = stat.st_size
                    modified_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    # Count messages
                    message_count = 0
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                message_count += 1
                    
                    session_id = filename.replace('.jsonl', '')
                    sessions.append({
                        'id': session_id,
                        'filename': filename,
                        'file_path': file_path,
                        'message_count': message_count,
                        'file_size': file_size,
                        'modified_time': modified_time.isoformat(),
                        'modified_display': modified_time.strftime('%b %d, %Y %I:%M %p')
                    })
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    continue
        
        return sorted(sessions, key=lambda x: x['modified_time'], reverse=True)
    
    def parse_session(self, project_id, session_id):
        """Parse a specific session file"""
        project_path = os.path.join(self.claude_dir, project_id)
        session_file = os.path.join(project_path, f"{session_id}.jsonl")
        
        if not os.path.exists(session_file):
            return []
            
        conversations = []
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    conversations.append(data)
                except json.JSONDecodeError:
                    continue
        
        return conversations

project_manager = ClaudeProjectManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/projects')
def api_projects():
    """Get all available Claude projects"""
    projects = project_manager.get_projects()
    return jsonify(projects)

@app.route('/api/projects/<project_id>/sessions')
def api_project_sessions(project_id):
    """Get all sessions for a specific project"""
    sessions = project_manager.get_project_sessions(project_id)
    return jsonify(sessions)

@app.route('/api/sessions/<project_id>/<session_id>')
def api_session_messages(project_id, session_id):
    """Get all messages for a specific session"""
    conversations = project_manager.parse_session(project_id, session_id)
    return jsonify(conversations)

# Legacy endpoints for backward compatibility
@app.route('/api/conversations')
def api_conversations():
    """Legacy endpoint - returns sample.jsonl if it exists"""
    if os.path.exists('sample.jsonl'):
        conversations = []
        with open('sample.jsonl', 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    conversations.append(data)
                except json.JSONDecodeError:
                    continue
        return jsonify(conversations)
    return jsonify([])

@app.route('/api/sessions')
def api_sessions():
    """Legacy endpoint"""
    return jsonify({})

if __name__ == '__main__':
    app.run(debug=True, port=5000)