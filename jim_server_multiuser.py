#!/usr/bin/env python3
"""
Jim Rohn AI Coach - Multi-User Version
Supports multiple users with individual profiles and shared knowledge base
"""

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file
from openai import OpenAI
from dotenv import load_dotenv
import re
from pathlib import Path

load_dotenv()

class MultiUserJimCoach:
    def __init__(self):
        """Initialize the multi-user Jim Rohn coaching system."""
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Create directories
        os.makedirs("user_data", exist_ok=True)
        os.makedirs("user_data/shared", exist_ok=True)
        
        # Load admin config
        self.admin_password = os.getenv("ADMIN_PASSWORD", "admin123")  # Change this!
        
        # Load system prompt
        try:
            with open('System prompt.txt', 'r') as f:
                self.system_prompt = f.read()
        except FileNotFoundError:
            self.system_prompt = """You are Jim Rohn, the legendary personal development speaker and mentor. 
            Respond with wisdom, warmth, and practical advice in your distinctive style."""
        
        # User sessions (in production, use Redis)
        self.active_sessions = {}
        
    def create_user_account(self, username: str, email: str, password: str) -> Dict:
        """Create a new user account."""
        # Clean input
        username = username.strip()
        email = email.strip()
        
        users_file = "user_data/users.json"
        
        # Load existing users
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                users = json.load(f)
        else:
            users = {}
        
        # Check if user exists
        if username in users:
            return {"success": False, "message": "Username already exists"}
        
        # Create user
        user_id = f"user_{secrets.token_hex(8)}"
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        users[username] = {
            "user_id": user_id,
            "email": email,
            "password_hash": password_hash,
            "created_at": datetime.now().isoformat(),
            "is_active": True
        }
        
        # Save users
        with open(users_file, 'w') as f:
            json.dump(users, f, indent=2)
        
        # Create user directory and files
        user_dir = f"user_data/{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        
        # Initialize user profile
        profile = {
            "name": "",
            "location": "",
            "total_conversations": 0,
            "recurring_themes": [],
            "growth_areas": [],
            "goals": [],
            "strengths": [],
            "challenges": [],
            "insights": [],
            "first_conversation": None,
            "last_conversation": None
        }
        
        with open(f"{user_dir}/profile.json", 'w') as f:
            json.dump(profile, f, indent=2)
        
        # Initialize conversation history
        with open(f"{user_dir}/conversations.json", 'w') as f:
            json.dump([], f)
        
        return {"success": True, "user_id": user_id, "message": "Account created successfully"}
    
    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return user_id if successful."""
        # Clean input
        username = username.strip()
        
        users_file = "user_data/users.json"
        
        if not os.path.exists(users_file):
            return None
        
        with open(users_file, 'r') as f:
            users = json.load(f)
        
        if username not in users:
            return None
        
        user = users[username]
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if user["password_hash"] == password_hash and user["is_active"]:
            return user["user_id"]
        
        return None
    
    def load_user_profile(self, user_id: str) -> Dict:
        """Load user profile."""
        profile_file = f"user_data/{user_id}/profile.json"
        
        if os.path.exists(profile_file):
            with open(profile_file, 'r') as f:
                return json.load(f)
        
        # Return default profile if not found
        return {
            "name": "",
            "location": "",
            "total_conversations": 0,
            "recurring_themes": [],
            "growth_areas": [],
            "goals": [],
            "strengths": [],
            "challenges": [],
            "insights": [],
            "first_conversation": None,
            "last_conversation": None
        }
    
    def save_user_profile(self, user_id: str, profile: Dict):
        """Save user profile."""
        profile_file = f"user_data/{user_id}/profile.json"
        with open(profile_file, 'w') as f:
            json.dump(profile, f, indent=2)
    
    def load_user_conversations(self, user_id: str) -> List[Dict]:
        """Load user conversation history."""
        conversations_file = f"user_data/{user_id}/conversations.json"
        
        if os.path.exists(conversations_file):
            with open(conversations_file, 'r') as f:
                return json.load(f)
        
        return []
    
    def save_user_conversations(self, user_id: str, conversations: List[Dict]):
        """Save user conversation history."""
        conversations_file = f"user_data/{user_id}/conversations.json"
        with open(conversations_file, 'w') as f:
            json.dump(conversations, f, indent=2)
    
    def extract_personal_details(self, user_id: str, question: str, response: str):
        """Extract and update personal details from conversations."""
        try:
            profile = self.load_user_profile(user_id)
            
            # Extract name if mentioned
            name_patterns = [
                r"[Mm]y name is (\w+)",
                r"[Ii]'m (\w+)",
                r"[Nn]ame: (\w+)",
                r"[Cc]all me (\w+)"
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, question)
                if match:
                    name = match.group(1).strip()
                    if name and len(name) > 1 and name.isalpha():
                        profile["name"] = name
                        break
            
            # Extract location if mentioned
            location_patterns = [
                r"\(([^)]+, [A-Z]{2})\)",  # (City, ST)
                r"from ([A-Z][a-z]+, [A-Z]{2})",  # from City, ST
                r"in ([A-Z][a-z]+, [A-Z]{2})"     # in City, ST
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, question)
                if match:
                    location = match.group(1).strip()
                    if location and "," in location:
                        profile["location"] = location
                        break
            
            self.save_user_profile(user_id, profile)
                        
        except Exception as e:
            print(f"⚠️ Personal detail extraction failed: {e}")
    
    def get_conversation_context(self, user_id: str, current_question: str) -> str:
        """Get relevant context from user's past conversations."""
        profile = self.load_user_profile(user_id)
        context = []
        
        # Add personal details first
        personal_info = []
        if profile.get("name"):
            personal_info.append(f"User's name: {profile['name']}")
        if profile.get("location"):
            personal_info.append(f"Location: {profile['location']}")
        
        if personal_info:
            context.append("Personal Information: " + ", ".join(personal_info))
        
        # Add user profile summary
        if profile.get("recurring_themes"):
            context.append(f"User's recurring themes: {', '.join(profile['recurring_themes'][-5:])}")
        
        if profile.get("growth_areas"):
            context.append(f"Growth areas: {', '.join(profile['growth_areas'][-3:])}")
        
        if profile.get("goals"):
            context.append(f"Current goals: {', '.join(profile['goals'][-3:])}")
        
        # Search recent conversations for similar topics
        conversations = self.load_user_conversations(user_id)
        recent_conversations = conversations[-10:]  # Last 10 conversations
        relevant_convos = []
        
        current_words = current_question.lower().split()
        for convo in recent_conversations:
            question_words = convo.get("question", "").lower().split()
            # Simple word overlap check
            overlap = len(set(current_words) & set(question_words))
            if overlap >= 2:  # If 2+ words match
                relevant_convos.append(convo)
        
        if relevant_convos:
            context.append("Recent similar conversations:")
            for convo in relevant_convos[-2:]:  # Last 2 relevant
                context.append(f"- Q: {convo['question'][:100]}... A: {convo['response'][:150]}...")
        
        return "\n".join(context) if context else ""
    
    def ask_jim(self, user_id: str, question: str, generate_voice: bool = True) -> Dict:
        """Get Jim's response for a specific user."""
        try:
            # Get conversation context from user's memory
            context = self.get_conversation_context(user_id, question)
            
            # Build enhanced system prompt with memory context
            enhanced_prompt = self.system_prompt
            if context:
                enhanced_prompt += f"\n\n=== MEMORY CONTEXT ===\n{context}\n\nUse this context to provide more personalized advice. Reference past conversations when relevant, but don't make it obvious unless it naturally fits the conversation."
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": enhanced_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            jim_response = response.choices[0].message.content
            
            # Generate voice if requested and API key is available
            audio_data = None
            if generate_voice and os.getenv("ELEVENLABS_API_KEY") and os.getenv("JIM_ROHN_VOICE_ID"):
                try:
                    from elevenlabs import ElevenLabs
                    elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
                    
                    # Clean text for speech synthesis
                    clean_text = self.clean_text_for_speech(jim_response)
                    
                    audio_generator = elevenlabs_client.text_to_speech.convert(
                        voice_id=os.getenv("JIM_ROHN_VOICE_ID"),
                        text=clean_text,
                        model_id="eleven_monolingual_v1"
                    )
                    audio_data = b"".join(audio_generator)
                    
                except Exception as voice_error:
                    print(f"⚠️ Voice generation failed: {voice_error}")
                    audio_data = None
            
            # Store conversation in user's memory
            conversation = {
                "question": question,
                "response": jim_response,
                "timestamp": datetime.now().isoformat(),
                "has_audio": audio_data is not None,
                "is_favorite": False
            }
            
            conversations = self.load_user_conversations(user_id)
            conversations.append(conversation)
            self.save_user_conversations(user_id, conversations)
            
            # Extract personal details and update profile
            self.extract_personal_details(user_id, question, jim_response)
            
            # Update user profile
            profile = self.load_user_profile(user_id)
            profile["total_conversations"] = len(conversations)
            profile["last_conversation"] = conversation["timestamp"]
            if not profile.get("first_conversation"):
                profile["first_conversation"] = conversation["timestamp"]
            
            self.save_user_profile(user_id, profile)
            
            return {
                "success": True,
                "response": jim_response,
                "audio": audio_data,
                "timestamp": conversation["timestamp"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def clean_text_for_speech(self, text: str) -> str:
        """Clean text for better speech synthesis."""
        # Remove markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
        text = re.sub(r'`(.*?)`', r'\1', text)        # Code
        
        # Fix common issues
        text = text.replace('*', '')
        text = text.replace('"', '"')
        text = text.replace('"', '"')
        text = text.replace(''', "'")
        text = text.replace(''', "'")
        
        return text
    
    def get_admin_stats(self) -> Dict:
        """Get system statistics for admin dashboard."""
        users_file = "user_data/users.json"
        
        if not os.path.exists(users_file):
            return {"total_users": 0, "active_users": 0, "total_conversations": 0}
        
        with open(users_file, 'r') as f:
            users = json.load(f)
        
        total_users = len(users)
        active_users = sum(1 for user in users.values() if user["is_active"])
        
        total_conversations = 0
        for user_data in users.values():
            user_id = user_data["user_id"]
            conversations = self.load_user_conversations(user_id)
            total_conversations += len(conversations)
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_conversations": total_conversations
        }

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
coach = MultiUserJimCoach()

@app.route('/')
def home():
    """Home page - login or register."""
    if 'user_id' in session:
        return redirect(url_for('chat'))
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/register', methods=['POST'])
def register():
    """Register new user."""
    data = request.json
    result = coach.create_user_account(
        data['username'],
        data['email'],
        data['password']
    )
    return jsonify(result)

@app.route('/login', methods=['POST'])
def login():
    """Login user."""
    data = request.json
    user_id = coach.authenticate_user(data['username'], data['password'])
    
    if user_id:
        session['user_id'] = user_id
        session['username'] = data['username']
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Invalid credentials"})

@app.route('/logout')
def logout():
    """Logout user."""
    session.clear()
    return redirect(url_for('home'))

@app.route('/chat')
def chat():
    """Chat interface for logged-in users."""
    print(f"Chat route - Session contents: {dict(session)}")
    if 'user_id' not in session:
        print("No user_id in session, redirecting to home")
        return redirect(url_for('home'))
    
    print(f"User {session.get('username')} accessing chat")
    return render_template_string(CHAT_TEMPLATE)

@app.route('/api/ask', methods=['POST'])
def api_ask():
    """API endpoint for asking Jim."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"})
    
    data = request.json
    result = coach.ask_jim(
        session['user_id'],
        data['question'],
        data.get('generate_voice', False)
    )
    return jsonify(result)

@app.route('/api/history')
def api_history():
    """Get user's conversation history."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"})
    
    conversations = coach.load_user_conversations(session['user_id'])
    return jsonify({"success": True, "conversations": conversations})

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard."""
    return render_template_string(ADMIN_TEMPLATE)

@app.route('/admin/stats')
def admin_stats():
    """Get admin statistics."""
    password = request.args.get('password')
    if password != coach.admin_password:
        return jsonify({"error": "Invalid admin password"})
    
    stats = coach.get_admin_stats()
    return jsonify(stats)

@app.route('/admin/update_rag', methods=['POST'])
def admin_update_rag():
    """Update RAG knowledge base."""
    password = request.form.get('password')
    if password != coach.admin_password:
        return jsonify({"error": "Invalid admin password"})
    
    # Run the RAG update script
    try:
        from jim_rohn_system import JimRohnCoach
        import shutil
        
        # Delete existing database to force rebuild
        if os.path.exists('./jim_knowledge_db'):
            shutil.rmtree('./jim_knowledge_db')
        
        # Initialize coach (this will trigger setup_knowledge_base)
        rag_coach = JimRohnCoach('./jim_rohn_materials')
        
        return jsonify({"success": True, "message": "RAG database updated successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to update RAG: {str(e)}"})

# Templates
LOGIN_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jim Rohn AI Coach - Login</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
            .form-group { margin: 15px 0; }
            input { width: 100%; padding: 10px; margin: 5px 0; }
            button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; cursor: pointer; }
            .tab { cursor: pointer; padding: 10px; margin: 5px; background: #f8f9fa; text-align: center; }
            .tab.active { background: #007bff; color: white; }
        </style>
    </head>
    <body>
        <h1>🧠 Jim Rohn AI Coach</h1>
        <div style="display: flex;">
            <div class="tab active" onclick="showLogin()">Login</div>
            <div class="tab" onclick="showRegister()">Register</div>
        </div>
        
        <form id="loginForm" style="display: block;">
            <div class="form-group">
                <input type="text" id="loginUsername" placeholder="Username" required>
            </div>
            <div class="form-group">
                <input type="password" id="loginPassword" placeholder="Password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        
        <form id="registerForm" style="display: none;">
            <div class="form-group">
                <input type="text" id="regUsername" placeholder="Username" required>
            </div>
            <div class="form-group">
                <input type="email" id="regEmail" placeholder="Email" required>
            </div>
            <div class="form-group">
                <input type="password" id="regPassword" placeholder="Password" required>
            </div>
            <button type="submit">Register</button>
        </form>
        
        <script>
            function showLogin() {
                document.getElementById('loginForm').style.display = 'block';
                document.getElementById('registerForm').style.display = 'none';
                document.querySelectorAll('.tab')[0].classList.add('active');
                document.querySelectorAll('.tab')[1].classList.remove('active');
            }
            
            function showRegister() {
                document.getElementById('loginForm').style.display = 'none';
                document.getElementById('registerForm').style.display = 'block';
                document.querySelectorAll('.tab')[0].classList.remove('active');
                document.querySelectorAll('.tab')[1].classList.add('active');
            }
            
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: document.getElementById('loginUsername').value,
                        password: document.getElementById('loginPassword').value
                    })
                });
                const result = await response.json();
                if (result.success) {
                    console.log('Login successful, redirecting...');
                    window.location.replace('/chat');
                } else {
                    alert(result.message || 'Login failed');
                }
            });
            
            document.getElementById('registerForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: document.getElementById('regUsername').value,
                        email: document.getElementById('regEmail').value,
                        password: document.getElementById('regPassword').value
                    })
                });
                const result = await response.json();
                if (result.success) {
                    alert('Account created! Please login.');
                    showLogin();
                } else {
                    alert(result.message || 'Registration failed');
                }
            });
        </script>
    </body>
    </html>
    """

CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jim Rohn AI Coach</title>
    <!-- Version 2.0 - Multi-User Dark Mode -->
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #0b1220 0%, #0b1220 50%, #0d1020 100%);
            color: #f4f4f5;
            min-height: 100vh;
            overflow: hidden;
        }

        .app-container {
            display: flex;
            height: 100vh;
            width: 100vw;
        }

        /* Sidebar Styles */
        .sidebar {
            width: 300px;
            background: rgba(39, 39, 42, 0.4);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            margin: 8px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .sidebar-header {
            padding: 16px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            background: transparent;
        }

        .sidebar-title {
            color: #f0f6fc;
            font-size: 1.2em;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .sidebar-subtitle {
            color: #8b949e;
            font-size: 0.85em;
        }

        .conversation-list {
            flex: 1;
            overflow-y: auto;
            padding: 10px 0;
        }

        .conversation-item {
            padding: 12px 20px;
            border-bottom: 1px solid #21262d;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
        }

        .conversation-item:hover {
            background: #21262d;
        }

        .conversation-question {
            color: #f0f6fc;
            font-size: 0.9em;
            margin-bottom: 5px;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .conversation-meta {
            color: #8b949e;
            font-size: 0.75em;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .conversation-star {
            color: #ffd700;
            font-size: 0.8em;
        }

        .sidebar-footer {
            padding: 15px 20px;
            border-top: 1px solid #30363d;
        }

        .view-more-btn {
            width: 100%;
            padding: 8px 12px;
            background: rgba(39, 39, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            color: #a1a1aa;
            font-size: 12px;
            cursor: pointer;
            transition: background 0.2s ease;
            font-weight: 500;
            box-shadow: none;
        }

        .view-more-btn:hover {
            background: rgba(39, 39, 42, 0.9);
        }

        /* Main Content Area */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: transparent;
        }

        .main-header {
            padding: 16px 24px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            background: transparent;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .main-title {
            color: #f4f4f5;
            font-size: 1.5em;
            margin-bottom: 4px;
            font-weight: 600;
            letter-spacing: 0.025em;
        }

        .main-subtitle {
            color: #8b949e;
            font-style: italic;
            font-size: 0.95em;
        }

        .logout-btn {
            padding: 8px 16px;
            background: rgba(220, 53, 69, 0.2);
            color: #f87171;
            border: 1px solid rgba(220, 53, 69, 0.4);
            border-radius: 12px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s ease;
        }

        .logout-btn:hover {
            background: rgba(220, 53, 69, 0.3);
            color: #fca5a5;
        }

        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            margin: 0 24px;
            background: rgba(9, 9, 11, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            position: relative;
        }

        .chat-container::before {
            content: '';
            position: absolute;
            inset: 0;
            background: radial-gradient(ellipse at top, rgba(6, 182, 212, 0.1), transparent);
            border-radius: 16px;
            pointer-events: none;
        }

        .message {
            margin-bottom: 20px;
            padding: 16px 20px;
            border-radius: 12px;
            animation: slideIn 0.3s ease-out;
            border: 1px solid #30363d;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .user-message {
            background: #0f1419;
            border-left: 3px solid #2ea043;
            margin-left: 40px;
        }

        .jim-message {
            background: #161b22;
            border-left: 3px solid #1f6feb;
            margin-right: 40px;
        }

        .message-header {
            font-weight: 600;
            margin-bottom: 8px;
            color: #f0f6fc;
            font-size: 0.9em;
        }

        .message-content {
            line-height: 1.6;
            color: #e6edf3;
            white-space: pre-wrap;
        }

        /* Input Section */
        .input-section {
            padding: 12px 24px;
            margin: 12px 24px 24px 24px;
            background: rgba(39, 39, 42, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
        }

        .input-row {
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
        }

        .voice-controls-row {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
        }

        .voice-label {
            color: #a1a1aa;
            font-size: 12px;
            font-weight: 500;
        }

        .mic-button {
            display: grid;
            place-items: center;
            width: 40px;
            height: 40px;
            background: rgba(9, 9, 11, 0.6);
            color: #a1a1aa;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            cursor: pointer;
            font-size: 16px;
            transition: all 0.2s ease;
            box-shadow: none;
            position: relative;
        }

        .mic-button:hover:not(:disabled) {
            background: rgba(39, 39, 42, 0.8);
            border-color: rgba(6, 182, 212, 0.4);
        }

        .mic-button.recording {
            background: rgba(6, 182, 212, 0.2);
            border-color: rgba(6, 182, 212, 0.5);
            color: #a5f3fc;
        }

        .mic-button.recording::after {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: 12px;
            animation: micPulse 1.6s infinite ease-out;
        }

        @keyframes micPulse {
            0% { box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.35); }
            50% { box-shadow: 0 0 0 6px rgba(6, 182, 212, 0.20); }
            100% { box-shadow: 0 0 0 12px rgba(6, 182, 212, 0.05); }
        }

        .voice-controls {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .audio-visualizer {
            display: flex;
            align-items: end;
            justify-content: center;
            height: 32px;
            background: rgba(39, 39, 42, 0.6);
            border-radius: 8px;
            padding: 4px 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
            box-shadow: none;
            gap: 1px;
            overflow: hidden;
        }

        .audio-visualizer.active {
            background: rgba(9, 9, 11, 0.6);
            border-color: rgba(6, 182, 212, 0.4);
        }

        .visualizer-bar {
            width: 2px;
            background: rgba(212, 212, 216, 0.5);
            border-radius: 1px;
            height: 4px;
            transition: all 0.3s ease;
            transform-origin: bottom;
        }

        .audio-visualizer.active .visualizer-bar {
            background: rgba(212, 212, 216, 0.8);
            animation: audioWave 1.8s ease-in-out infinite;
        }

        @keyframes audioWave {
            0%, 100% { height: 8px; opacity: 0.7; }
            50% { height: 24px; opacity: 1; }
        }

        .visualizer-bar:nth-child(1) { animation-delay: 0.1s; }
        .visualizer-bar:nth-child(2) { animation-delay: 0.2s; }
        .visualizer-bar:nth-child(3) { animation-delay: 0.3s; }
        .visualizer-bar:nth-child(4) { animation-delay: 0.4s; }
        .visualizer-bar:nth-child(5) { animation-delay: 0.5s; }
        .visualizer-bar:nth-child(6) { animation-delay: 0.6s; }
        .visualizer-bar:nth-child(7) { animation-delay: 0.7s; }
        .visualizer-bar:nth-child(8) { animation-delay: 0.8s; }
        .visualizer-bar:nth-child(9) { animation-delay: 0.9s; }
        .visualizer-bar:nth-child(10) { animation-delay: 1.0s; }
        .visualizer-bar:nth-child(11) { animation-delay: 0.8s; }
        .visualizer-bar:nth-child(12) { animation-delay: 0.6s; }
        .visualizer-bar:nth-child(13) { animation-delay: 0.4s; }
        .visualizer-bar:nth-child(14) { animation-delay: 0.2s; }
        .visualizer-bar:nth-child(15) { animation-delay: 0.0s; }

        .voice-button {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 6px 12px;
            background: rgba(6, 182, 212, 0.2);
            color: #a5f3fc;
            border: 1px solid rgba(6, 182, 212, 0.4);
            border-radius: 12px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: background 0.2s ease;
            white-space: nowrap;
            box-shadow: none;
        }

        .voice-button:hover {
            background: rgba(6, 182, 212, 0.3);
        }

        .voice-button.disabled {
            background: rgba(39, 39, 42, 0.6);
            border-color: rgba(255, 255, 255, 0.1);
            color: #a1a1aa;
            cursor: default;
        }

        .voice-button.disabled:hover {
            background: rgba(39, 39, 42, 0.6);
        }

        .recording-status {
            color: #dc3545;
            font-weight: bold;
            font-size: 12px;
            text-align: center;
            margin-top: 10px;
            animation: pulse 1.5s infinite;
        }

        .question-input {
            flex: 1;
            padding: 8px 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            font-size: 15px;
            resize: none;
            min-height: 40px;
            max-height: 160px;
            font-family: inherit;
            background: rgba(9, 9, 11, 0.6);
            color: #f4f4f5;
            transition: border-color 0.2s ease;
        }

        .question-input:focus {
            outline: none;
            border-color: rgba(6, 182, 212, 0.4);
        }

        .question-input::placeholder {
            color: #8b949e;
        }

        .ask-button {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: rgba(6, 182, 212, 0.2);
            color: #a5f3fc;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s ease;
            min-width: 80px;
            box-shadow: none;
        }

        .ask-button:hover:not(:disabled) {
            background: rgba(6, 182, 212, 0.3);
        }

        .ask-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            background: rgba(113, 118, 129, 0.3);
        }

        .stats {
            display: flex;
            align-items: center;
            justify-content: space-between;
            color: #8b949e;
            font-size: 13px;
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #2ea043;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .loading {
            animation: pulse 1.5s ease-in-out infinite;
        }

        .status-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.8);
        }

        .modal-content {
            background-color: #161b22;
            margin: 2% auto;
            padding: 20px;
            border-radius: 12px;
            width: 90%;
            max-width: 1000px;
            max-height: 90%;
            overflow-y: auto;
            position: relative;
            border: 1px solid #30363d;
        }

        .close {
            color: #8b949e;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            line-height: 20px;
        }

        .close:hover {
            color: #f0f6fc;
        }

        .history-header {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #30363d;
            color: #f0f6fc;
        }

        .profile-summary {
            background: #0d1117;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #30363d;
        }

        .history-conversation {
            margin-bottom: 15px;
            padding: 15px;
            border: 1px solid #30363d;
            border-radius: 8px;
            background: #21262d;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .history-conversation:hover {
            background: #30363d;
            border-color: #1f6feb;
        }

        .history-conversation.expanded {
            background: #0f1419;
            border-color: #1f6feb;
        }

        .history-timestamp {
            font-size: 12px;
            color: #8b949e;
            margin-bottom: 8px;
        }

        .history-question {
            font-weight: 600;
            color: #2ea043;
            margin-bottom: 8px;
        }

        .history-response {
            color: #e6edf3;
            line-height: 1.4;
        }

        .history-response.truncated {
            max-height: 60px;
            overflow: hidden;
            position: relative;
        }

        .history-response.truncated::after {
            content: '... Click to read full response';
            position: absolute;
            bottom: 0;
            right: 0;
            background: linear-gradient(to right, transparent, #21262d 50%);
            padding-left: 20px;
            color: #1f6feb;
            font-style: italic;
            font-size: 12px;
        }

        .expand-indicator {
            float: right;
            color: #1f6feb;
            font-size: 12px;
            font-weight: bold;
        }

        .favorite-button {
            float: right;
            background: none;
            border: none;
            font-size: 16px;
            cursor: pointer;
            padding: 2px 4px;
            border-radius: 4px;
            transition: all 0.2s ease;
            color: #8b949e;
            margin-left: 8px;
        }

        .favorite-button:hover {
            background: rgba(255, 215, 0, 0.1);
            transform: scale(1.1);
        }

        .favorite-button.favorited {
            color: #ffd700;
        }

        .favorite-button.favorited:hover {
            color: #ffed4a;
        }

        .favorites-filter {
            margin: 15px 0;
            text-align: center;
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            .sidebar {
                width: 250px;
            }
            
            .main-header {
                padding: 15px 20px;
            }
            
            .main-title {
                font-size: 1.5em;
            }
            
            .chat-container {
                padding: 15px 20px;
            }
            
            .input-section {
                padding: 15px 20px;
            }
        }

        .filter-button {
            padding: 6px 14px;
            margin: 0 4px;
            border: 1px solid #1f6feb;
            background: transparent;
            color: #1f6feb;
            border-radius: 50px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
            font-weight: 500;
            box-shadow: none;
        }

        .filter-button.active {
            background: #1f6feb;
            color: white;
        }

        .filter-button:hover {
            background: #1f6feb;
            color: white;
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Left Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">Recent Conversations</div>
                <div class="sidebar-subtitle">Quick access to your journey</div>
            </div>
            
            <div class="conversation-list" id="recentConversations">
                <div class="conversation-item">
                    <div class="conversation-question">Loading recent conversations...</div>
                    <div class="conversation-meta">Just now</div>
                </div>
            </div>
            
            <div class="sidebar-footer">
                <button class="view-more-btn" onclick="showHistory()">View All History</button>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="main-header">
                <div>
                    <div class="main-title">Jim Rohn AI Coach</div>
                    <div class="main-subtitle">"Success is neither magical nor mysterious. Success is the natural consequence of consistently applying basic fundamentals."</div>
                </div>
                <a href="/logout" class="logout-btn">Logout</a>
            </div>

            <div class="chat-container" id="chatContainer">
                <div class="message jim-message">
                    <div class="message-header">Jim Rohn:</div>
                    <div class="message-content">Welcome, my friend! I'm here to share wisdom about success, personal development, and achieving your goals. What's on your mind today? What challenge are you facing, or what guidance are you seeking?</div>
                </div>
            </div>

            <div class="input-section">
                <div class="voice-controls-row">
                    <span class="voice-label">Voice</span>
                    <button class="voice-button" id="voiceButton" onclick="toggleVoice()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                            <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.08"></path>
                        </svg>
                        <span id="voiceButtonText">On</span>
                    </button>
                    
                    <div class="audio-visualizer" id="audioVisualizer">
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                        <div class="visualizer-bar"></div>
                    </div>

                    <div class="recording-status" id="recordingStatus" style="display: none;">
                        🔴 Listening... (speak your question)
                    </div>
                </div>

                <div class="input-row">
                    <textarea id="questionInput" class="question-input" placeholder="Ask Jim about success, goals, discipline, motivation, relationships, or any life challenge..." rows="3"></textarea>
                    <button id="micButton" class="mic-button" onclick="toggleSpeechRecognition()" title="Click to speak your question">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                            <line x1="12" y1="19" x2="12" y2="23"></line>
                            <line x1="8" y1="23" x2="16" y2="23"></line>
                        </svg>
                    </button>
                    <button id="askButton" class="ask-button" onclick="askJim()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22,2 15,22 11,13 2,9 22,2"></polygon>
                        </svg>
                        Send
                    </button>
                </div>

                <div class="stats">
                    <div class="status-info">
                        <span class="status-indicator"></span>
                        <span id="statusText">Connected & Ready</span>
                    </div>
                    <div>Conversations: <span id="conversationCount">0</span></div>
                </div>
            </div>
        </div>
    </div>

    <!-- History Modal -->
    <div id="historyModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeHistory()">&times;</span>
            <div class="history-header">
                <h2>Conversation History</h2>
            </div>
            <div id="historyContent">
                <p>Loading history...</p>
            </div>
        </div>
    </div>

    <script>
        let conversationCount = 0;
        let recognition = null;
        let isRecording = false;
        let voiceEnabled = true;
        let audioUnlocked = false;

        // Load conversation count and recent conversations
        async function loadConversationCount() {
            try {
                const response = await fetch('/api/history');
                const data = await response.json();
                if (data.success) {
                    conversationCount = data.conversations.length || 0;
                    document.getElementById('conversationCount').textContent = conversationCount;
                    
                    // Populate sidebar with recent conversations
                    loadRecentConversations(data.conversations || []);
                }
            } catch (error) {
                console.warn('Failed to load conversation count:', error);
            }
        }

        // Load recent conversations in sidebar
        function loadRecentConversations(conversations) {
            const container = document.getElementById('recentConversations');
            if (!conversations || conversations.length === 0) {
                container.innerHTML = '<div class="conversation-item"><div class="conversation-question">No conversations yet</div><div class="conversation-meta">Start chatting!</div></div>';
                return;
            }

            // Sort by timestamp (newest first) and take last 10
            const recent = conversations
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
                .slice(0, 10);

            let html = '';
            recent.forEach((conv, index) => {
                const date = new Date(conv.timestamp);
                const timeAgo = getTimeAgo(date);
                const truncatedQuestion = conv.question.length > 60 
                    ? conv.question.substring(0, 60) + '...'
                    : conv.question;
                
                html += `<div class="conversation-item" onclick="openConversationInHistory('${conv.timestamp}')">`;
                html += `<div class="conversation-question">${truncatedQuestion}</div>`;
                html += `<div class="conversation-meta">`;
                html += `${timeAgo}`;
                if (conv.is_favorite) {
                    html += ` <span class="conversation-star">⭐</span>`;
                }
                html += `</div></div>`;
            });

            container.innerHTML = html;
        }

        // Helper function to get time ago
        function getTimeAgo(date) {
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            return date.toLocaleDateString();
        }

        // Open specific conversation in history modal
        function openConversationInHistory(timestamp) {
            showHistory();
            // TODO: Could add logic to highlight/scroll to specific conversation
        }

        // Initialize speech recognition
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';
            
            recognition.onstart = function() {
                isRecording = true;
                document.getElementById('micButton').classList.add('recording');
                document.getElementById('recordingStatus').style.display = 'block';
            };
            
            recognition.onend = function() {
                isRecording = false;
                document.getElementById('micButton').classList.remove('recording');
                document.getElementById('recordingStatus').style.display = 'none';
            };
            
            recognition.onresult = function(event) {
                const transcript = event.results[0][0].transcript;
                document.getElementById('questionInput').value = transcript;
            };
            
            recognition.onerror = function(event) {
                console.error('Speech recognition error:', event.error);
                alert('Speech recognition error: ' + event.error);
            };
        }

        function toggleSpeechRecognition() {
            if (!recognition) {
                alert('Speech recognition not supported in this browser. Please use Chrome or Safari.');
                return;
            }
            
            if (isRecording) {
                recognition.stop();
            } else {
                recognition.start();
            }
        }

        function toggleVoice() {
            voiceEnabled = !voiceEnabled;
            const button = document.getElementById('voiceButton');
            const buttonText = document.getElementById('voiceButtonText');
            
            if (voiceEnabled) {
                button.classList.remove('disabled');
                buttonText.textContent = 'On';
            } else {
                button.classList.add('disabled');
                buttonText.textContent = 'Off';
            }
        }

        // Update voice button status when audio is unlocked
        function updateVoiceButtonStatus() {
            if (voiceEnabled && audioUnlocked) {
                const buttonText = document.getElementById('voiceButtonText');
                buttonText.textContent = 'On';
            }
        }

        function showAudioVisualizer() {
            const visualizer = document.getElementById('audioVisualizer');
            if (visualizer) {
                visualizer.classList.add('active');
            }
        }

        function hideAudioVisualizer() {
            const visualizer = document.getElementById('audioVisualizer');
            if (visualizer) {
                visualizer.classList.remove('active');
            }
        }

        function showHistory() {
            // Show proper modal with full conversation history
            const modal = document.getElementById('historyModal');
            const content = document.getElementById('historyContent');
            
            if (!modal) {
                console.error('History modal not found!');
                return;
            }
            
            modal.style.display = 'block';
            content.innerHTML = '<p>Loading history...</p>';
            
            fetch('/api/history')
                .then(response => response.json())
                .then(data => {
                    let html = '';
                    
                    if (data.success && data.conversations && data.conversations.length > 0) {
                        html += '<h3>Recent Conversations</h3>';
                        
                        // Sort conversations by timestamp (newest first)
                        const sortedConversations = data.conversations.sort((a, b) => 
                            new Date(b.timestamp) - new Date(a.timestamp)
                        );
                        
                        // Store conversations data globally for click handlers
                        conversationsData = sortedConversations;
                        
                        sortedConversations.forEach((conversation, index) => {
                            const date = new Date(conversation.timestamp).toLocaleString();
                            const isLong = conversation.response.length > 200;
                            const truncatedResponse = isLong ? conversation.response.substring(0, 200) : conversation.response;
                            const isFavorite = conversation.is_favorite || false;
                            const favoriteClass = isFavorite ? 'favorites-only' : 'all-conversations';
                            
                            html += `<div class="history-conversation ${favoriteClass}" onclick="toggleConversation(${index})">`;
                            html += `<div class="history-timestamp">${date}`;
                            
                            if (isLong) {
                                html += `<span class="expand-indicator" id="indicator-${index}">▼ Click to expand</span>`;
                            }
                            html += `</div>`;
                            html += `<div class="history-question">Q: ${conversation.question}</div>`;
                            html += `<div class="history-response ${isLong ? 'truncated' : ''}" id="response-${index}">`;
                            html += `A: <span id="response-text-${index}">${truncatedResponse}</span>`;
                            html += `</div>`;
                            html += `<div style="display: none;" id="full-response-${index}">${conversation.response}</div>`;
                            html += '</div>';
                        });
                    } else {
                        html += '<p>No conversation history yet. Start chatting with Jim!</p>';
                    }
                    
                    content.innerHTML = html;
                })
                .catch(error => {
                    content.innerHTML = '<p>Error loading history: ' + error.message + '</p>';
                });
        }

        function closeHistory() {
            document.getElementById('historyModal').style.display = 'none';
        }

        // Toggle conversation expansion
        function toggleConversation(index) {
            const conversation = conversationsData[index];
            const responseElement = document.getElementById(`response-${index}`);
            const responseTextElement = document.getElementById(`response-text-${index}`);
            const indicator = document.getElementById(`indicator-${index}`);
            const conversationDiv = responseElement.closest('.history-conversation');
            
            const isExpanded = conversationDiv.classList.contains('expanded');
            
            if (isExpanded) {
                // Collapse
                conversationDiv.classList.remove('expanded');
                responseElement.classList.add('truncated');
                responseTextElement.textContent = conversation.response.substring(0, 200);
                if (indicator) {
                    indicator.textContent = '▼ Click to expand';
                }
            } else {
                // Expand
                conversationDiv.classList.add('expanded');
                responseElement.classList.remove('truncated');
                responseTextElement.textContent = conversation.response;
                if (indicator) {
                    indicator.textContent = '▲ Click to collapse';
                }
            }
        }

        // Close modal when clicking outside of it
        window.onclick = function(event) {
            const modal = document.getElementById('historyModal');
            if (event.target === modal) {
                closeHistory();
            }
        }

        // Global audio unlock state
        let globalAudioContext = null;
        let pendingAudio = null;
        let conversationsData = [];

        function createAudioUnlockButton() {
            // Remove any existing button
            const existingButton = document.getElementById('audioUnlockButton');
            if (existingButton) {
                existingButton.remove();
            }

            const button = document.createElement('button');
            button.id = 'audioUnlockButton';
            button.innerHTML = '🔊 Click to Enable Jim\\'s Voice';
            button.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                color: white;
                border: none;
                padding: 20px 30px;
                border-radius: 15px;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
                z-index: 2000;
                box-shadow: 0 8px 20px rgba(220, 53, 69, 0.3);
                animation: pulse 2s infinite;
            `;

            button.onclick = async function() {
                try {
                    console.log('User clicked audio unlock button');
                    
                    // Create audio context with user interaction
                    globalAudioContext = new (window.AudioContext || window.webkitAudioContext)();
                    
                    // Play a tiny silent sound to unlock
                    const buffer = globalAudioContext.createBuffer(1, 1, 22050);
                    const source = globalAudioContext.createBufferSource();
                    source.buffer = buffer;
                    source.connect(globalAudioContext.destination);
                    source.start(0);
                    
                    audioUnlocked = true;
                    console.log('Audio unlocked successfully');
                    
                    // Remove the button
                    button.remove();
                    
                    // Update voice button status
                    updateVoiceButtonStatus();
                    
                    // Update status
                    const statusText = document.getElementById('statusText');
                    statusText.textContent = 'Audio Enabled! Ask Jim again to hear his voice';
                    statusText.style.color = '#28a745';
                    
                    setTimeout(() => {
                        statusText.textContent = 'Connected & Ready';
                        statusText.style.color = '';
                    }, 3000);
                    
                    // If there's pending audio, play it now
                    if (pendingAudio) {
                        console.log('Playing pending audio');
                        playAudioDirect(pendingAudio);
                        pendingAudio = null;
                    }
                    
                } catch (error) {
                    console.error('Failed to unlock audio:', error);
                    alert('Failed to enable audio. Please try refreshing the page.');
                }
            };

            document.body.appendChild(button);
        }

        async function playAudioDirect(audioData) {
            try {
                console.log('Playing audio directly, data length:', audioData.length);
                
                showAudioVisualizer();
                
                // Convert base64 to binary string, then to Uint8Array
                const binaryString = atob(audioData);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                
                // Create audio with MP3 format
                const audioBlob = new Blob([bytes], { type: 'audio/mpeg' });
                const audioUrl = URL.createObjectURL(audioBlob);
                
                const audio = new Audio(audioUrl);
                audio.volume = 0.8;
                
                audio.onended = () => {
                    URL.revokeObjectURL(audioUrl);
                    hideAudioVisualizer();
                    console.log('Audio playback completed');
                };
                
                audio.onerror = (e) => {
                    console.error('Audio playback error:', e);
                    URL.revokeObjectURL(audioUrl);
                    hideAudioVisualizer();
                };
                
                // Play the audio
                await audio.play();
                console.log('Audio playing successfully');
                        
            } catch (error) {
                console.error('Direct audio playback failed:', error);
                hideAudioVisualizer();
                throw error;
            }
        }

        async function playAudio(audioData) {
            try {
                // Check if audio is unlocked
                if (!audioUnlocked || !globalAudioContext) {
                    console.log('Audio not unlocked, storing for later and showing unlock button');
                    pendingAudio = audioData;
                    createAudioUnlockButton();
                    return;
                }
                
                // Audio is unlocked, play directly
                await playAudioDirect(audioData);
                        
            } catch (error) {
                console.error('Audio processing failed:', error);
                hideAudioVisualizer();
                
                if (error.name === 'NotAllowedError') {
                    console.log('Audio blocked, showing unlock button');
                    pendingAudio = audioData;
                    createAudioUnlockButton();
                } else {
                    // Other error, show message
                    const statusText = document.getElementById('statusText');
                    statusText.textContent = 'Audio error - voice disabled for this session';
                    statusText.style.color = '#dc3545';
                    setTimeout(() => {
                        statusText.textContent = 'Connected & Ready';
                        statusText.style.color = '';
                    }, 3000);
                }
            }
        }

        async function askJim() {
            const question = document.getElementById('questionInput').value.trim();
            const askButton = document.getElementById('askButton');
            const chatContainer = document.getElementById('chatContainer');
            const statusText = document.getElementById('statusText');

            if (!question) {
                alert('Please ask Jim a question.');
                return;
            }

            // Add user message
            addMessage('You', question, 'user-message');
            
            // Clear input and disable button
            document.getElementById('questionInput').value = '';
            askButton.disabled = true;
            askButton.innerHTML = '<span class="loading">Jim is thinking...</span>';
            statusText.textContent = 'Jim is pondering your question';

            // Add loading message
            const loadingMessage = addMessage('Jim Rohn', 'Let me think about that...', 'jim-message');

            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ 
                        question: question, 
                        generate_voice: voiceEnabled 
                    })
                });

                const data = await response.json();

                // Remove loading message
                chatContainer.removeChild(loadingMessage);

                if (data.success) {
                    // Add Jim's response
                    const messageElement = addMessage('Jim Rohn', data.response, 'jim-message');
                    
                    // Play audio if available
                    if (data.audio && voiceEnabled) {
                        try {
                            await playAudio(data.audio);
                            // Add audio indicator to message
                            const audioIcon = document.createElement('span');
                            audioIcon.innerHTML = ' 🔊';
                            audioIcon.style.color = '#28a745';
                            audioIcon.title = 'Audio response available';
                            messageElement.querySelector('.message-header').appendChild(audioIcon);
                        } catch (audioError) {
                            console.error('Audio playback error:', audioError);
                        }
                    }
                    
                    // Update conversation count and refresh sidebar
                    statusText.textContent = 'Connected & Ready';
                    
                    // Refresh recent conversations in sidebar
                    loadConversationCount();
                } else {
                    // Add error message
                    addMessage('Jim Rohn', data.response || data.error || 'I encountered an error', 'jim-message');
                    statusText.textContent = 'Technical difficulty - please try again';
                }

            } catch (error) {
                console.error('Error:', error);
                
                // Remove loading message if it exists
                if (loadingMessage && loadingMessage.parentNode) {
                    chatContainer.removeChild(loadingMessage);
                }
                
                // Add error message
                addMessage('Jim Rohn', 'I apologize, but I\\'m having some technical difficulties right now. Please try again in a moment.', 'jim-message');
                statusText.textContent = 'Connection error - please try again';
            } finally {
                // Re-enable button
                askButton.disabled = false;
                askButton.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22,2 15,22 11,13 2,9 22,2"></polygon></svg> Send';
            }
        }

        function addMessage(sender, content, className) {
            const chatContainer = document.getElementById('chatContainer');
            const message = document.createElement('div');
            message.className = `message ${className}`;
            
            const header = document.createElement('div');
            header.className = 'message-header';
            header.textContent = sender + ':';
            
            const messageContent = document.createElement('div');
            messageContent.className = 'message-content';
            messageContent.textContent = content;
            
            message.appendChild(header);
            message.appendChild(messageContent);
            chatContainer.appendChild(message);
            
            // Scroll to bottom
            chatContainer.scrollTop = chatContainer.scrollHeight;
            
            return message;
        }

        // Allow Enter to send message
        document.getElementById('questionInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                askJim();
            }
        });

        // Auto-focus and load count
        document.getElementById('questionInput').focus();
        loadConversationCount();
    </script>
</body>
</html>
"""

ADMIN_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jim Rohn Coach - Admin</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .section { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
            input, button { padding: 10px; margin: 5px; }
            .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
            .stat { text-align: center; padding: 15px; background: #f8f9fa; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>🔧 Admin Dashboard</h1>
        
        <div class="section">
            <h3>System Statistics</h3>
            <input type="password" id="adminPassword" placeholder="Admin Password">
            <button onclick="loadStats()">Load Stats</button>
            <div id="stats" class="stats"></div>
        </div>
        
        <div class="section">
            <h3>Update RAG Knowledge Base</h3>
            <p>Use this to update the knowledge base with new Jim Rohn content.</p>
            <button onclick="updateRAG()">Update Knowledge Base</button>
            <div id="ragResult"></div>
        </div>
        
        <script>
            async function loadStats() {
                const password = document.getElementById('adminPassword').value;
                const response = await fetch(`/admin/stats?password=${password}`);
                const result = await response.json();
                
                if (result.error) {
                    alert(result.error);
                    return;
                }
                
                document.getElementById('stats').innerHTML = `
                    <div class="stat">
                        <h4>${result.total_users}</h4>
                        <p>Total Users</p>
                    </div>
                    <div class="stat">
                        <h4>${result.active_users}</h4>
                        <p>Active Users</p>
                    </div>
                    <div class="stat">
                        <h4>${result.total_conversations}</h4>
                        <p>Total Conversations</p>
                    </div>
                `;
            }
            
            async function updateRAG() {
                const password = document.getElementById('adminPassword').value;
                if (!password) {
                    alert('Please enter admin password');
                    return;
                }
                
                document.getElementById('ragResult').innerHTML = 'Updating knowledge base...';
                
                const formData = new FormData();
                formData.append('password', password);
                
                const response = await fetch('/admin/update_rag', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('ragResult').innerHTML = '✅ ' + result.message;
                } else {
                    document.getElementById('ragResult').innerHTML = '❌ ' + result.error;
                }
            }
        </script>
    </body>
    </html>
    """

# Production configuration
def create_app():
    """Create and configure the Flask app for production."""
    return app

if __name__ == '__main__':
    print("🧠 Starting Multi-User Jim Rohn AI Coach...")
    print("🌐 Server will be available at: http://localhost:5001")
    print("🔧 Admin dashboard: http://localhost:5001/admin")
    print("🛑 To stop: Press Ctrl+C")
    
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)