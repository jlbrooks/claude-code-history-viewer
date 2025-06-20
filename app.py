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
from supabase import create_client, Client
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', tempfile.gettempdir())
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10MB
CLAUDE_MODE = os.environ.get('CLAUDE_MODE', 'hybrid').lower()  # local, cloud, hybrid
SESSION_TIMEOUT_HOURS = int(os.environ.get('SESSION_TIMEOUT_HOURS', 24))

# Supabase Configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
SUPABASE_BUCKET = os.environ.get('SUPABASE_BUCKET', 'claude-logs-uploads')

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

class SupabaseDataManager(DataManager):
    """Data manager for Supabase storage"""
    
    def __init__(self, supabase_url, supabase_key, bucket_name):
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and Service Key are required")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()
        
    def _ensure_bucket_exists(self):
        """Ensure the storage bucket exists"""
        try:
            # Try to get bucket info, create if it doesn't exist
            self.supabase.storage.get_bucket(self.bucket_name)
        except Exception:
            try:
                # Create bucket if it doesn't exist
                self.supabase.storage.create_bucket(self.bucket_name, {
                    'public': False,
                    'file_size_limit': MAX_CONTENT_LENGTH,
                    'allowed_mime_types': ['application/json', 'text/plain']
                })
            except Exception as e:
                print(f"Warning: Could not create bucket {self.bucket_name}: {e}")
    
    def _get_session_id(self):
        """Get or create session ID"""
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        return session['session_id']
    
    def _get_session_prefix(self):
        """Get session-specific prefix for file storage"""
        return f"{self._get_session_id()}/"
    
    def _get_uploaded_files(self):
        """Get list of uploaded files for current session"""
        session_prefix = self._get_session_prefix()
        files = []
        
        try:
            # List files in the session directory
            result = self.supabase.storage.from_(self.bucket_name).list(session_prefix.rstrip('/'))
            
            for file_obj in result:
                if file_obj['name'].endswith('.jsonl'):
                    try:
                        # Get file metadata
                        file_path = f"{session_prefix}{file_obj['name']}"
                        
                        files.append({
                            'filename': file_obj['name'],
                            'file_path': file_path,
                            'upload_time': datetime.fromisoformat(file_obj['created_at'].replace('Z', '+00:00')),
                            'file_size': file_obj.get('metadata', {}).get('size', 0)
                        })
                    except Exception as e:
                        print(f"Error processing uploaded file {file_obj['name']}: {e}")
        except Exception as e:
            print(f"Error listing uploaded files: {e}")
        
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
                # Download and count messages in file
                message_count = 0
                file_content = self._download_file_content(file_info['file_path'])
                
                if file_content:
                    for line in file_content.split('\n'):
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
        
        session_prefix = self._get_session_prefix()
        file_path = f"{session_prefix}{session_id}.jsonl"
        
        try:
            file_content = self._download_file_content(file_path)
            if not file_content:
                return []
            
            conversations = []
            for line in file_content.split('\n'):
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        conversations.append(data)
                    except json.JSONDecodeError:
                        continue
            
            return conversations
        except Exception as e:
            print(f"Error parsing session {session_id}: {e}")
            return []
    
    def _download_file_content(self, file_path):
        """Download file content from Supabase storage"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).download(file_path)
            return response.decode('utf-8')
        except Exception as e:
            print(f"Error downloading file {file_path}: {e}")
            return None
    
    def save_uploaded_file(self, file, original_filename):
        """Save an uploaded file to Supabase storage"""
        # Secure the filename
        filename = secure_filename(original_filename)
        if not filename.endswith('.jsonl'):
            filename += '.jsonl'
        
        # Ensure unique filename within session
        session_prefix = self._get_session_prefix()
        counter = 1
        base_name = filename.replace('.jsonl', '')
        original_filename = filename
        
        while self._file_exists(f"{session_prefix}{filename}"):
            filename = f"{base_name}_{counter}.jsonl"
            counter += 1
        
        # Upload file to Supabase storage
        file_path = f"{session_prefix}{filename}"
        
        try:
            # Read file content
            file.seek(0)
            file_content = file.read()
            
            # Upload to Supabase
            self.supabase.storage.from_(self.bucket_name).upload(
                file_path, 
                file_content,
                file_options={
                    'content-type': 'application/json',
                    'cache-control': '3600'
                }
            )
            
            return filename
        except Exception as e:
            print(f"Error uploading file {filename}: {e}")
            raise
    
    def delete_uploaded_file(self, filename):
        """Delete an uploaded file from Supabase storage"""
        session_prefix = self._get_session_prefix()
        file_path = f"{session_prefix}{secure_filename(filename)}"
        
        try:
            self.supabase.storage.from_(self.bucket_name).remove([file_path])
            return True
        except Exception as e:
            print(f"Error deleting file {filename}: {e}")
            return False
    
    def _file_exists(self, file_path):
        """Check if file exists in Supabase storage"""
        try:
            # Try to get file info
            self.supabase.storage.from_(self.bucket_name).download(file_path)
            return True
        except:
            return False

class HybridDataManager(DataManager):
    """Data manager that combines local and cloud data"""
    
    def __init__(self, local_manager, supabase_manager):
        self.local_manager = local_manager
        self.supabase_manager = supabase_manager
    
    def get_projects(self):
        """Get projects from both local and cloud sources"""
        local_projects = self.local_manager.get_projects()
        cloud_projects = self.supabase_manager.get_projects()
        return local_projects + cloud_projects
    
    def get_project_sessions(self, project_id):
        """Get sessions from appropriate source"""
        if project_id == 'uploaded':
            return self.supabase_manager.get_project_sessions(project_id)
        else:
            return self.local_manager.get_project_sessions(project_id)
    
    def parse_session(self, project_id, session_id):
        """Parse session from appropriate source"""
        if project_id == 'uploaded':
            return self.supabase_manager.parse_session(project_id, session_id)
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

# Initialize Supabase manager if credentials are available
supabase_manager = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        supabase_manager = SupabaseDataManager(SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET)
    except Exception as e:
        print(f"Warning: Failed to initialize Supabase storage: {e}")
        print("Falling back to local-only mode")

if CLAUDE_MODE == 'local':
    data_manager = local_manager
elif CLAUDE_MODE == 'cloud':
    if supabase_manager:
        data_manager = supabase_manager
    else:
        raise ValueError("Cloud mode requires Supabase configuration (SUPABASE_URL and SUPABASE_SERVICE_KEY)")
else:  # hybrid
    if supabase_manager:
        data_manager = HybridDataManager(local_manager, supabase_manager)
    else:
        print("Warning: Supabase not configured, falling back to local-only mode")
        data_manager = local_manager

@app.route('/')
def index():
    return render_template('index.html', claude_mode=CLAUDE_MODE)

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'mode': CLAUDE_MODE,
        'timestamp': datetime.now().isoformat()
    })

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
        if not supabase_manager:
            return jsonify({'error': 'Storage not configured'}), 500
            
        filename = supabase_manager.save_uploaded_file(file, file.filename)
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
        if not supabase_manager:
            return jsonify({'error': 'Storage not configured'}), 500
            
        files = supabase_manager._get_uploaded_files()
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
        if not supabase_manager:
            return jsonify({'error': 'Storage not configured'}), 500
            
        success = supabase_manager.delete_uploaded_file(filename)
        if success:
            return jsonify({'success': True, 'message': 'File deleted successfully'})
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)