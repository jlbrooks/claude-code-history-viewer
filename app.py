from flask import Flask, render_template, jsonify, request, session
import json
import os
import tempfile
import uuid
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from abc import ABC, abstractmethod
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', tempfile.gettempdir())
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10MB
CLAUDE_MODE = os.environ.get('CLAUDE_MODE', 'hybrid').lower()  # local, cloud, hybrid
SESSION_TIMEOUT_HOURS = int(os.environ.get('SESSION_TIMEOUT_HOURS', 24))

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

class DataManager(ABC):
    """Abstract base class for data management"""
    
    @abstractmethod
    def get_projects(self):
        """Get all available projects"""
        pass
    
    @abstractmethod
    def get_project_sessions(self, project_id):
        """Get all sessions for a specific project"""
        pass
    
    @abstractmethod
    def parse_session(self, project_id, session_id):
        """Parse a specific session file"""
        pass

class LocalDataManager(DataManager):
    """Data manager for local Claude projects"""
    
    def __init__(self, claude_dir=None):
        self.claude_dir = claude_dir or os.path.expanduser('~/.claude/projects')
        
    def decode_project_path(self, encoded_path):
        """Convert encoded project path back to readable format"""
        if encoded_path.startswith('-'):
            decoded = encoded_path[1:].replace('-', '/')
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
                session_files = [f for f in os.listdir(project_path) 
                               if f.endswith('.jsonl')]
                
                projects.append({
                    'id': item,
                    'name': self.decode_project_path(item),
                    'encoded_path': item,
                    'session_count': len(session_files),
                    'sessions': session_files,
                    'source': 'local'
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
                    stat = os.stat(file_path)
                    file_size = stat.st_size
                    modified_time = datetime.fromtimestamp(stat.st_mtime)
                    
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
                        'modified_display': modified_time.strftime('%b %d, %Y %I:%M %p'),
                        'source': 'local'
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

class CloudDataManager(DataManager):
    """Data manager for uploaded files"""
    
    def __init__(self, upload_dir):
        self.upload_dir = upload_dir
        
    def _get_session_dir(self):
        """Get session-specific upload directory"""
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        session_dir = os.path.join(self.upload_dir, 'sessions', session['session_id'])
        os.makedirs(session_dir, exist_ok=True)
        return session_dir
    
    def _get_uploaded_files(self):
        """Get list of uploaded files for current session"""
        session_dir = self._get_session_dir()
        files = []
        
        if os.path.exists(session_dir):
            for filename in os.listdir(session_dir):
                if filename.endswith('.jsonl'):
                    file_path = os.path.join(session_dir, filename)
                    try:
                        stat = os.stat(file_path)
                        files.append({
                            'filename': filename,
                            'file_path': file_path,
                            'upload_time': datetime.fromtimestamp(stat.st_ctime),
                            'file_size': stat.st_size
                        })
                    except Exception as e:
                        print(f"Error processing uploaded file {filename}: {e}")
        
        return sorted(files, key=lambda x: x['upload_time'], reverse=True)
    
    def get_projects(self):
        """Get uploaded files as 'projects'"""
        uploaded_files = self._get_uploaded_files()
        
        # Group files as a single "Uploaded Files" project
        if uploaded_files:
            return [{
                'id': 'uploaded',
                'name': 'Uploaded Files',
                'encoded_path': 'uploaded',
                'session_count': len(uploaded_files),
                'sessions': [f['filename'] for f in uploaded_files],
                'source': 'uploaded'
            }]
        
        return []
    
    def get_project_sessions(self, project_id):
        """Get uploaded files as sessions"""
        if project_id != 'uploaded':
            return []
        
        uploaded_files = self._get_uploaded_files()
        sessions = []
        
        for file_info in uploaded_files:
            try:
                # Count messages in file
                message_count = 0
                with open(file_info['file_path'], 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            message_count += 1
                
                session_id = file_info['filename'].replace('.jsonl', '')
                sessions.append({
                    'id': session_id,
                    'filename': file_info['filename'],
                    'file_path': file_info['file_path'],
                    'message_count': message_count,
                    'file_size': file_info['file_size'],
                    'modified_time': file_info['upload_time'].isoformat(),
                    'modified_display': file_info['upload_time'].strftime('%b %d, %Y %I:%M %p'),
                    'source': 'uploaded'
                })
            except Exception as e:
                print(f"Error processing uploaded file {file_info['filename']}: {e}")
                continue
        
        return sessions
    
    def parse_session(self, project_id, session_id):
        """Parse an uploaded session file"""
        if project_id != 'uploaded':
            return []
        
        session_dir = self._get_session_dir()
        session_file = os.path.join(session_dir, f"{session_id}.jsonl")
        
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
    
    def save_uploaded_file(self, file, original_filename):
        """Save an uploaded file"""
        session_dir = self._get_session_dir()
        
        # Secure the filename
        filename = secure_filename(original_filename)
        if not filename.endswith('.jsonl'):
            filename += '.jsonl'
        
        # Ensure unique filename
        counter = 1
        base_name = filename.replace('.jsonl', '')
        while os.path.exists(os.path.join(session_dir, filename)):
            filename = f"{base_name}_{counter}.jsonl"
            counter += 1
        
        file_path = os.path.join(session_dir, filename)
        file.save(file_path)
        
        return filename
    
    def delete_uploaded_file(self, filename):
        """Delete an uploaded file"""
        session_dir = self._get_session_dir()
        file_path = os.path.join(session_dir, secure_filename(filename))
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

class HybridDataManager(DataManager):
    """Data manager that combines local and cloud data"""
    
    def __init__(self, local_manager, cloud_manager):
        self.local_manager = local_manager
        self.cloud_manager = cloud_manager
    
    def get_projects(self):
        """Get projects from both local and cloud sources"""
        local_projects = self.local_manager.get_projects()
        cloud_projects = self.cloud_manager.get_projects()
        return local_projects + cloud_projects
    
    def get_project_sessions(self, project_id):
        """Get sessions from appropriate source"""
        if project_id == 'uploaded':
            return self.cloud_manager.get_project_sessions(project_id)
        else:
            return self.local_manager.get_project_sessions(project_id)
    
    def parse_session(self, project_id, session_id):
        """Parse session from appropriate source"""
        if project_id == 'uploaded':
            return self.cloud_manager.parse_session(project_id, session_id)
        else:
            return self.local_manager.parse_session(project_id, session_id)

def validate_jsonl_file(file):
    """Validate that uploaded file is valid JSONL"""
    try:
        file.seek(0)
        content = file.read().decode('utf-8')
        file.seek(0)  # Reset for saving
        
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return False, "File is empty"
        
        # Validate each line is valid JSON
        for i, line in enumerate(lines[:10]):  # Check first 10 lines
            try:
                json.loads(line)
            except json.JSONDecodeError:
                return False, f"Invalid JSON on line {i+1}"
        
        return True, "Valid JSONL file"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

# Initialize data managers based on mode
local_manager = LocalDataManager()
cloud_manager = CloudDataManager(UPLOAD_FOLDER)

if CLAUDE_MODE == 'local':
    data_manager = local_manager
elif CLAUDE_MODE == 'cloud':
    data_manager = cloud_manager
else:  # hybrid
    data_manager = HybridDataManager(local_manager, cloud_manager)

# Cleanup old session files
def cleanup_old_sessions():
    """Remove old session directories"""
    sessions_dir = os.path.join(UPLOAD_FOLDER, 'sessions')
    if not os.path.exists(sessions_dir):
        return
    
    cutoff_time = datetime.now() - timedelta(hours=SESSION_TIMEOUT_HOURS)
    
    for session_id in os.listdir(sessions_dir):
        session_path = os.path.join(sessions_dir, session_id)
        if os.path.isdir(session_path):
            try:
                # Check last modified time
                stat = os.stat(session_path)
                if datetime.fromtimestamp(stat.st_mtime) < cutoff_time:
                    shutil.rmtree(session_path)
                    print(f"Cleaned up old session: {session_id}")
            except Exception as e:
                print(f"Error cleaning up session {session_id}: {e}")

@app.route('/')
def index():
    cleanup_old_sessions()  # Clean up on each page load
    return render_template('index.html', claude_mode=CLAUDE_MODE)

@app.route('/api/config')
def api_config():
    """Get app configuration"""
    return jsonify({
        'mode': CLAUDE_MODE,
        'max_file_size': MAX_CONTENT_LENGTH,
        'session_timeout_hours': SESSION_TIMEOUT_HOURS
    })

@app.route('/api/projects')
def api_projects():
    """Get all available projects"""
    projects = data_manager.get_projects()
    return jsonify(projects)

@app.route('/api/projects/<project_id>/sessions')
def api_project_sessions(project_id):
    """Get all sessions for a specific project"""
    sessions = data_manager.get_project_sessions(project_id)
    return jsonify(sessions)

@app.route('/api/sessions/<project_id>/<session_id>')
def api_session_messages(project_id, session_id):
    """Get all messages for a specific session"""
    conversations = data_manager.parse_session(project_id, session_id)
    return jsonify(conversations)

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Upload a conversation file"""
    if CLAUDE_MODE == 'local':
        return jsonify({'error': 'File upload not available in local mode'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file
    is_valid, message = validate_jsonl_file(file)
    if not is_valid:
        return jsonify({'error': f'Invalid file: {message}'}), 400
    
    try:
        filename = cloud_manager.save_uploaded_file(file, file.filename)
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'File uploaded successfully'
        })
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/uploaded-files')
def api_uploaded_files():
    """Get list of uploaded files"""
    if CLAUDE_MODE == 'local':
        return jsonify([])
    
    try:
        files = cloud_manager._get_uploaded_files()
        return jsonify([{
            'filename': f['filename'],
            'upload_time': f['upload_time'].isoformat(),
            'file_size': f['file_size']
        } for f in files])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/uploaded-files/<filename>', methods=['DELETE'])
def api_delete_uploaded_file(filename):
    """Delete an uploaded file"""
    if CLAUDE_MODE == 'local':
        return jsonify({'error': 'File management not available in local mode'}), 403
    
    try:
        success = cloud_manager.delete_uploaded_file(filename)
        if success:
            return jsonify({'success': True, 'message': 'File deleted successfully'})
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)