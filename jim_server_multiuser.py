#!/usr/bin/env python3
"""
Jim Rohn AI Coach - Multi-User Version
Supports multiple users with individual profiles and shared knowledge base
"""

import os
import json
import secrets
import base64
import bcrypt
from datetime import datetime
from typing import Dict, List, Optional
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file
from openai import OpenAI
from dotenv import load_dotenv
import re
import traceback
from pathlib import Path
from contextlib import contextmanager

load_dotenv()

# Database setup - use PostgreSQL if DATABASE_URL is set, otherwise fall back to JSON files
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2 import pool

    # Create connection pool
    db_pool = pool.ThreadedConnectionPool(1, 10, DATABASE_URL)

    @contextmanager
    def get_db_connection():
        """Get a database connection from the pool."""
        conn = db_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            db_pool.putconn(conn)

    def init_database():
        """Create tables if they don't exist."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(32) PRIMARY KEY,
                        username VARCHAR(255) UNIQUE NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        is_active BOOLEAN DEFAULT true
                    )
                """)

                # User profiles table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id VARCHAR(32) PRIMARY KEY REFERENCES users(user_id),
                        name VARCHAR(255),
                        location VARCHAR(255),
                        total_conversations INTEGER DEFAULT 0,
                        recurring_themes JSONB DEFAULT '[]',
                        growth_areas JSONB DEFAULT '[]',
                        goals JSONB DEFAULT '[]',
                        strengths JSONB DEFAULT '[]',
                        challenges JSONB DEFAULT '[]',
                        insights JSONB DEFAULT '[]',
                        first_conversation TIMESTAMP,
                        last_conversation TIMESTAMP
                    )
                """)

                # Conversations table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(32) NOT NULL REFERENCES users(user_id),
                        question TEXT NOT NULL,
                        response TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        has_audio BOOLEAN DEFAULT false,
                        is_favorite BOOLEAN DEFAULT false
                    )
                """)

                # Create index for faster queries
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conversations_user_time
                    ON conversations(user_id, timestamp DESC)
                """)
        print("✅ PostgreSQL database initialized")

    # Initialize database on startup
    init_database()
else:
    print("⚠️  DATABASE_URL not set. Using JSON file storage (data will be lost on redeploy)")

# Validate required environment variables
def validate_env():
    required = ["OPENAI_API_KEY"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    # Warn about insecure defaults
    if not os.getenv("SECRET_KEY"):
        print("⚠️  WARNING: SECRET_KEY not set. Using insecure default.")
    if not os.getenv("ADMIN_PASSWORD"):
        print("⚠️  WARNING: ADMIN_PASSWORD not set. Using insecure default.")

validate_env()


class MultiUserJimCoach:
    def __init__(self):
        """Initialize the multi-user Jim Rohn coaching system."""
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Create directories
        os.makedirs("user_data", exist_ok=True)
        os.makedirs("user_data/shared", exist_ok=True)

        # Load admin config
        self.admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        
        # Load system prompt
        try:
            with open('System prompt.txt', 'r') as f:
                self.system_prompt = f.read()
        except FileNotFoundError:
            self.system_prompt = """You are Jim Rohn, the legendary personal development speaker and mentor.
            Respond with wisdom, warmth, and practical advice in your distinctive style."""
        
    def create_user_account(self, username: str, email: str, password: str) -> Dict:
        """Create a new user account."""
        username = username.strip()
        email = email.strip()

        user_id = f"user_{secrets.token_hex(8)}"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode('utf-8')
        created_at = datetime.now()

        if USE_POSTGRES:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        # Check if username exists
                        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
                        if cur.fetchone():
                            return {"success": False, "message": "Username already exists"}

                        # Insert user
                        cur.execute("""
                            INSERT INTO users (user_id, username, email, password_hash, created_at, is_active)
                            VALUES (%s, %s, %s, %s, %s, true)
                        """, (user_id, username, email, password_hash, created_at))

                        # Insert empty profile
                        cur.execute("""
                            INSERT INTO user_profiles (user_id, name, location, total_conversations,
                                recurring_themes, growth_areas, goals, strengths, challenges, insights)
                            VALUES (%s, '', '', 0, '[]', '[]', '[]', '[]', '[]', '[]')
                        """, (user_id,))

                return {"success": True, "user_id": user_id, "message": "Account created successfully"}
            except Exception as e:
                print(f"Database error: {e}")
                return {"success": False, "message": "Database error creating account"}
        else:
            # JSON file fallback
            users_file = "user_data/users.json"
            if os.path.exists(users_file):
                with open(users_file, 'r') as f:
                    users = json.load(f)
            else:
                users = {}

            if username in users:
                return {"success": False, "message": "Username already exists"}

            users[username] = {
                "user_id": user_id,
                "email": email,
                "password_hash": password_hash,
                "created_at": created_at.isoformat(),
                "is_active": True
            }

            with open(users_file, 'w') as f:
                json.dump(users, f, indent=2)

            user_dir = f"user_data/{user_id}"
            os.makedirs(user_dir, exist_ok=True)

            profile = {
                "name": "", "location": "", "total_conversations": 0,
                "recurring_themes": [], "growth_areas": [], "goals": [],
                "strengths": [], "challenges": [], "insights": [],
                "first_conversation": None, "last_conversation": None
            }
            with open(f"{user_dir}/profile.json", 'w') as f:
                json.dump(profile, f, indent=2)

            with open(f"{user_dir}/conversations.json", 'w') as f:
                json.dump([], f)

            return {"success": True, "user_id": user_id, "message": "Account created successfully"}
    
    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return user_id if successful."""
        username = username.strip()

        if USE_POSTGRES:
            try:
                with get_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT user_id, password_hash, is_active
                            FROM users WHERE username = %s
                        """, (username,))
                        user = cur.fetchone()

                        if not user or not user["is_active"]:
                            return None

                        stored_hash = user["password_hash"]

                        # Try bcrypt (all PostgreSQL users use bcrypt)
                        if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                            return user["user_id"]

                        return None
            except Exception as e:
                print(f"Authentication error: {e}")
                return None
        else:
            # JSON file fallback
            users_file = "user_data/users.json"
            if not os.path.exists(users_file):
                return None

            with open(users_file, 'r') as f:
                users = json.load(f)

            if username not in users:
                return None

            user = users[username]
            if not user["is_active"]:
                return None

            stored_hash = user["password_hash"]

            if stored_hash.startswith('$2'):
                if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                    return user["user_id"]
            else:
                import hashlib
                if stored_hash == hashlib.sha256(password.encode()).hexdigest():
                    new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode('utf-8')
                    users[username]["password_hash"] = new_hash
                    with open(users_file, 'w') as f:
                        json.dump(users, f, indent=2)
                    return user["user_id"]

            return None
    
    def load_user_profile(self, user_id: str) -> Dict:
        """Load user profile."""
        default_profile = {
            "name": "", "location": "", "total_conversations": 0,
            "recurring_themes": [], "growth_areas": [], "goals": [],
            "strengths": [], "challenges": [], "insights": [],
            "first_conversation": None, "last_conversation": None
        }

        if USE_POSTGRES:
            try:
                with get_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT name, location, total_conversations,
                                recurring_themes, growth_areas, goals,
                                strengths, challenges, insights,
                                first_conversation, last_conversation
                            FROM user_profiles WHERE user_id = %s
                        """, (user_id,))
                        row = cur.fetchone()
                        if row:
                            return {
                                "name": row["name"] or "",
                                "location": row["location"] or "",
                                "total_conversations": row["total_conversations"] or 0,
                                "recurring_themes": row["recurring_themes"] or [],
                                "growth_areas": row["growth_areas"] or [],
                                "goals": row["goals"] or [],
                                "strengths": row["strengths"] or [],
                                "challenges": row["challenges"] or [],
                                "insights": row["insights"] or [],
                                "first_conversation": row["first_conversation"].isoformat() if row["first_conversation"] else None,
                                "last_conversation": row["last_conversation"].isoformat() if row["last_conversation"] else None
                            }
                        return default_profile
            except Exception as e:
                print(f"Error loading profile: {e}")
                traceback.print_exc()
                return default_profile
        else:
            profile_file = f"user_data/{user_id}/profile.json"
            if os.path.exists(profile_file):
                with open(profile_file, 'r') as f:
                    return json.load(f)
            return default_profile

    def save_user_profile(self, user_id: str, profile: Dict):
        """Save user profile."""
        if USE_POSTGRES:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        first_conv = profile.get("first_conversation")
                        last_conv = profile.get("last_conversation")
                        if isinstance(first_conv, str):
                            first_conv = datetime.fromisoformat(first_conv)
                        if isinstance(last_conv, str):
                            last_conv = datetime.fromisoformat(last_conv)

                        cur.execute("""
                            UPDATE user_profiles SET
                                name = %s, location = %s, total_conversations = %s,
                                recurring_themes = %s, growth_areas = %s, goals = %s,
                                strengths = %s, challenges = %s, insights = %s,
                                first_conversation = %s, last_conversation = %s
                            WHERE user_id = %s
                        """, (
                            profile.get("name", ""),
                            profile.get("location", ""),
                            profile.get("total_conversations", 0),
                            json.dumps(profile.get("recurring_themes", [])),
                            json.dumps(profile.get("growth_areas", [])),
                            json.dumps(profile.get("goals", [])),
                            json.dumps(profile.get("strengths", [])),
                            json.dumps(profile.get("challenges", [])),
                            json.dumps(profile.get("insights", [])),
                            first_conv,
                            last_conv,
                            user_id
                        ))
            except Exception as e:
                print(f"Error saving profile: {e}")
                traceback.print_exc()
                raise
        else:
            profile_file = f"user_data/{user_id}/profile.json"
            with open(profile_file, 'w') as f:
                json.dump(profile, f, indent=2)

    def load_user_conversations(self, user_id: str) -> List[Dict]:
        """Load user conversation history."""
        if USE_POSTGRES:
            try:
                with get_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT question, response, timestamp, has_audio, is_favorite
                            FROM conversations
                            WHERE user_id = %s
                            ORDER BY timestamp ASC
                        """, (user_id,))
                        rows = cur.fetchall()
                        return [{
                            "question": row["question"],
                            "response": row["response"],
                            "timestamp": row["timestamp"].isoformat() if row["timestamp"] else datetime.now().isoformat(),
                            "has_audio": row["has_audio"] or False,
                            "is_favorite": row["is_favorite"] or False
                        } for row in rows]
            except Exception as e:
                print(f"Error loading conversations: {e}")
                traceback.print_exc()
                return []
        else:
            conversations_file = f"user_data/{user_id}/conversations.json"
            if os.path.exists(conversations_file):
                with open(conversations_file, 'r') as f:
                    return json.load(f)
            return []

    def save_user_conversations(self, user_id: str, conversations: List[Dict]):
        """Save user conversation history (append the last conversation to DB)."""
        if USE_POSTGRES:
            # For PostgreSQL, we only append the newest conversation
            if conversations:
                conv = conversations[-1]
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            timestamp = conv.get("timestamp")
                            if isinstance(timestamp, str):
                                timestamp = datetime.fromisoformat(timestamp)
                            cur.execute("""
                                INSERT INTO conversations (user_id, question, response, timestamp, has_audio, is_favorite)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                user_id,
                                conv["question"],
                                conv["response"],
                                timestamp,
                                conv.get("has_audio", False),
                                conv.get("is_favorite", False)
                            ))
                except Exception as e:
                    print(f"Error saving conversation: {e}")
                    traceback.print_exc()
                    raise
        else:
            conversations_file = f"user_data/{user_id}/conversations.json"
            with open(conversations_file, 'w') as f:
                json.dump(conversations, f, indent=2)
    
    def extract_personal_details(self, user_id: str, question: str, response: str):
        """Extract and update personal details from conversations."""
        try:
            profile = self.load_user_profile(user_id)
            updated = False

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
                        updated = True
                        print(f"📝 Extracted name: {name}")
                        break

            # Extract location if mentioned (more flexible patterns)
            location_patterns = [
                r"\(([^)]+, [A-Z]{2})\)",  # (City, ST)
                r"from ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?, [A-Z]{2})",  # from City, ST or from New York, NY
                r"in ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?, [A-Z]{2})",   # in City, ST
                r"live in ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",  # live in Denver
                r"from ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",     # from Denver
                r"located in ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)"  # located in Denver
            ]

            for pattern in location_patterns:
                match = re.search(pattern, question)
                if match:
                    location = match.group(1).strip()
                    if location and len(location) > 2:
                        profile["location"] = location
                        updated = True
                        print(f"📍 Extracted location: {location}")
                        break

            if updated:
                self.save_user_profile(user_id, profile)
                print(f"✅ Profile updated for {user_id}: name={profile.get('name')}, location={profile.get('location')}")

        except Exception as e:
            print(f"⚠️ Personal detail extraction failed: {e}")
            traceback.print_exc()
    
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

            import time
            openai_start = time.time()
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": enhanced_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            jim_response = response.choices[0].message.content
            print(f"🤖 OpenAI response in {time.time() - openai_start:.1f}s ({len(jim_response)} chars)")
            
            # Generate voice if requested and API key is available
            audio_data = None
            if generate_voice and os.getenv("ELEVENLABS_API_KEY") and os.getenv("JIM_ROHN_VOICE_ID"):
                try:
                    import time
                    voice_start = time.time()
                    from elevenlabs import ElevenLabs
                    elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

                    # Clean text for speech synthesis
                    clean_text = self.clean_text_for_speech(jim_response)

                    # Limit text length for faster voice generation (max ~2000 chars)
                    if len(clean_text) > 2000:
                        clean_text = clean_text[:2000] + "..."
                        print(f"⚠️ Truncated voice text from {len(jim_response)} to 2000 chars")

                    audio_generator = elevenlabs_client.text_to_speech.convert(
                        voice_id=os.getenv("JIM_ROHN_VOICE_ID"),
                        text=clean_text,
                        model_id="eleven_turbo_v2"  # Faster model
                    )
                    audio_data = b"".join(audio_generator)
                    print(f"🔊 Voice generated in {time.time() - voice_start:.1f}s ({len(clean_text)} chars)")

                except Exception as voice_error:
                    print(f"⚠️ Voice generation failed: {voice_error}")
                    traceback.print_exc()
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
                "audio": base64.b64encode(audio_data).decode('utf-8') if audio_data else None,
                "timestamp": conversation["timestamp"]
            }
            
        except Exception as e:
            print(f"Error in ask_jim: {e}")
            traceback.print_exc()
            error_msg = str(e) if str(e) else type(e).__name__
            return {
                "success": False,
                "error": error_msg
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
        if USE_POSTGRES:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM users")
                        total_users = cur.fetchone()[0]

                        cur.execute("SELECT COUNT(*) FROM users WHERE is_active = true")
                        active_users = cur.fetchone()[0]

                        cur.execute("SELECT COUNT(*) FROM conversations")
                        total_conversations = cur.fetchone()[0]

                        return {
                            "total_users": total_users,
                            "active_users": active_users,
                            "total_conversations": total_conversations
                        }
            except Exception as e:
                print(f"Error getting admin stats: {e}")
                return {"total_users": 0, "active_users": 0, "total_conversations": 0}
        else:
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

# Production session settings
app.config.update(
    SESSION_COOKIE_SECURE=os.getenv("FLASK_ENV") == "production",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400 * 7  # 7 days
)

coach = MultiUserJimCoach()


@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "jim-rohn-coach",
        "version": "2.0"
    })


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
    if 'user_id' not in session:
        return redirect(url_for('home'))
    return render_template_string(CHAT_TEMPLATE)

@app.route('/api/ask', methods=['POST'])
def api_ask():
    """API endpoint for asking Jim."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"})

    try:
        data = request.json
        if not data or 'question' not in data:
            return jsonify({"success": False, "error": "Question is required"})

        result = coach.ask_jim(
            session['user_id'],
            data['question'],
            data.get('generate_voice', False)
        )
        return jsonify(result)
    except Exception as e:
        print(f"Error in /api/ask: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Server error: {str(e)}"})

@app.route('/api/history')
def api_history():
    """Get user's conversation history."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"})

    conversations = coach.load_user_conversations(session['user_id'])
    return jsonify({"success": True, "conversations": conversations})

@app.route('/api/favorite', methods=['POST'])
def api_toggle_favorite():
    """Toggle favorite status on a conversation."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"})

    data = request.json
    timestamp = data.get('timestamp')
    if not timestamp:
        return jsonify({"success": False, "error": "Timestamp required"})

    user_id = session['user_id']

    if USE_POSTGRES:
        try:
            ts = datetime.fromisoformat(timestamp)
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Toggle the favorite status directly in DB
                    cur.execute("""
                        UPDATE conversations
                        SET is_favorite = NOT is_favorite
                        WHERE user_id = %s AND timestamp = %s
                        RETURNING is_favorite
                    """, (user_id, ts))
                    row = cur.fetchone()
                    if row:
                        return jsonify({"success": True, "is_favorite": row["is_favorite"]})
                    return jsonify({"success": False, "error": "Conversation not found"})
        except Exception as e:
            print(f"Error toggling favorite: {e}")
            return jsonify({"success": False, "error": "Database error"})
    else:
        conversations = coach.load_user_conversations(user_id)
        for conv in conversations:
            if conv.get('timestamp') == timestamp:
                conv['is_favorite'] = not conv.get('is_favorite', False)
                coach.save_user_conversations(user_id, conversations)
                return jsonify({"success": True, "is_favorite": conv['is_favorite']})
        return jsonify({"success": False, "error": "Conversation not found"})

@app.route('/api/profile')
def api_profile():
    """Get user's profile/memory data."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"})

    try:
        profile = coach.load_user_profile(session['user_id'])
        print(f"Profile loaded for {session['user_id']}: {profile}")  # Debug logging
        return jsonify({"success": True, "profile": profile})
    except Exception as e:
        print(f"Error in /api/profile: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Error loading profile: {str(e)}"})

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard."""
    return render_template_string(ADMIN_TEMPLATE)

@app.route('/admin/stats', methods=['POST'])
def admin_stats():
    """Get admin statistics."""
    data = request.get_json() or {}
    password = data.get('password') or request.form.get('password')
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jim Rohn AI Coach - Login</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #0b1220 0%, #0d1525 50%, #0a0f1a 100%);
            color: #f4f4f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }

        /* Ambient background glow */
        body::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(ellipse at 30% 20%, rgba(6, 182, 212, 0.08) 0%, transparent 50%),
                        radial-gradient(ellipse at 70% 80%, rgba(59, 130, 246, 0.06) 0%, transparent 50%);
            pointer-events: none;
            animation: ambientShift 20s ease-in-out infinite alternate;
        }

        @keyframes ambientShift {
            0% { transform: translate(0, 0) rotate(0deg); }
            100% { transform: translate(-5%, 5%) rotate(3deg); }
        }

        .login-container {
            width: 100%;
            max-width: 420px;
            position: relative;
            z-index: 1;
        }

        .login-card {
            background: rgba(22, 27, 34, 0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            padding: 40px 36px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5),
                        0 0 0 1px rgba(255, 255, 255, 0.05) inset;
            animation: cardFloat 0.6s ease-out;
        }

        @keyframes cardFloat {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .logo-section {
            text-align: center;
            margin-bottom: 32px;
        }

        .logo-icon {
            font-size: 48px;
            margin-bottom: 16px;
            display: block;
            animation: logoPulse 3s ease-in-out infinite;
        }

        @keyframes logoPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }

        .logo-title {
            font-size: 1.75rem;
            font-weight: 700;
            color: #f4f4f5;
            letter-spacing: -0.02em;
            margin-bottom: 8px;
        }

        .logo-subtitle {
            color: #8b949e;
            font-size: 0.9rem;
            font-style: italic;
            line-height: 1.5;
        }

        .tab-container {
            display: flex;
            background: rgba(9, 9, 11, 0.5);
            border-radius: 14px;
            padding: 4px;
            margin-bottom: 28px;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .tab {
            flex: 1;
            padding: 12px 20px;
            text-align: center;
            cursor: pointer;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            color: #8b949e;
            transition: all 0.25s ease;
            border: none;
            background: transparent;
        }

        .tab:hover:not(.active) {
            color: #c9d1d9;
            background: rgba(255, 255, 255, 0.03);
        }

        .tab.active {
            background: rgba(6, 182, 212, 0.15);
            color: #a5f3fc;
            box-shadow: 0 2px 8px rgba(6, 182, 212, 0.15);
        }

        .form-container {
            position: relative;
        }

        form {
            display: none;
            animation: formFade 0.3s ease-out;
        }

        form.active {
            display: block;
        }

        @keyframes formFade {
            from { opacity: 0; transform: translateX(10px); }
            to { opacity: 1; transform: translateX(0); }
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            color: #c9d1d9;
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 8px;
            letter-spacing: 0.01em;
        }

        .form-input {
            width: 100%;
            padding: 14px 16px;
            background: rgba(9, 9, 11, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            font-size: 15px;
            color: #f4f4f5;
            font-family: inherit;
            transition: all 0.2s ease;
        }

        .form-input::placeholder {
            color: #6e7681;
        }

        .form-input:focus {
            outline: none;
            border-color: rgba(6, 182, 212, 0.5);
            background: rgba(9, 9, 11, 0.8);
            box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
        }

        .submit-btn {
            width: 100%;
            padding: 14px 24px;
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.9) 0%, rgba(59, 130, 246, 0.9) 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.25s ease;
            margin-top: 8px;
            position: relative;
            overflow: hidden;
            letter-spacing: 0.01em;
        }

        .submit-btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.5s ease;
        }

        .submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px -8px rgba(6, 182, 212, 0.5);
        }

        .submit-btn:hover::before {
            left: 100%;
        }

        .submit-btn:active {
            transform: translateY(0);
        }

        .submit-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .submit-btn .btn-text {
            position: relative;
            z-index: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .submit-btn .spinner {
            display: none;
            width: 18px;
            height: 18px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        .submit-btn.loading .spinner {
            display: block;
        }

        .submit-btn.loading .btn-label {
            display: none;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .message {
            padding: 12px 16px;
            border-radius: 10px;
            font-size: 14px;
            margin-bottom: 20px;
            display: none;
            animation: messageSlide 0.3s ease-out;
        }

        @keyframes messageSlide {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.error {
            display: block;
            background: rgba(220, 53, 69, 0.15);
            border: 1px solid rgba(220, 53, 69, 0.3);
            color: #f87171;
        }

        .message.success {
            display: block;
            background: rgba(34, 197, 94, 0.15);
            border: 1px solid rgba(34, 197, 94, 0.3);
            color: #4ade80;
        }

        .footer-text {
            text-align: center;
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            color: #6e7681;
            font-size: 13px;
        }

        .footer-text a {
            color: #60a5fa;
            text-decoration: none;
            font-weight: 500;
        }

        .footer-text a:hover {
            text-decoration: underline;
        }

        /* Decorative elements */
        .decoration {
            position: absolute;
            border-radius: 50%;
            pointer-events: none;
            opacity: 0.5;
        }

        .decoration-1 {
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(6, 182, 212, 0.1) 0%, transparent 70%);
            top: -150px;
            right: -100px;
        }

        .decoration-2 {
            width: 200px;
            height: 200px;
            background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%);
            bottom: -100px;
            left: -50px;
        }

        /* Mobile responsiveness */
        @media (max-width: 480px) {
            body {
                padding: 16px;
                align-items: flex-start;
                padding-top: 40px;
            }

            .login-card {
                padding: 32px 24px;
                border-radius: 20px;
            }

            .logo-icon {
                font-size: 40px;
            }

            .logo-title {
                font-size: 1.5rem;
            }

            .logo-subtitle {
                font-size: 0.85rem;
            }

            .tab {
                padding: 10px 16px;
                font-size: 13px;
            }

            .form-input {
                padding: 12px 14px;
                font-size: 16px; /* Prevents iOS zoom */
            }

            .submit-btn {
                padding: 12px 20px;
            }
        }

        @media (max-width: 360px) {
            .login-card {
                padding: 24px 20px;
            }

            .logo-title {
                font-size: 1.35rem;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="decoration decoration-1"></div>
        <div class="decoration decoration-2"></div>

        <div class="login-card">
            <div class="logo-section">
                <span class="logo-icon">🧠</span>
                <h1 class="logo-title">Jim Rohn AI Coach</h1>
                <p class="logo-subtitle">"Success is doing ordinary things extraordinarily well."</p>
            </div>

            <div class="tab-container">
                <button class="tab active" onclick="showLogin()" type="button">Sign In</button>
                <button class="tab" onclick="showRegister()" type="button">Create Account</button>
            </div>

            <div id="messageBox" class="message"></div>

            <div class="form-container">
                <form id="loginForm" class="active">
                    <div class="form-group">
                        <label class="form-label" for="loginUsername">Username</label>
                        <input type="text" id="loginUsername" class="form-input" placeholder="Enter your username" required autocomplete="username">
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="loginPassword">Password</label>
                        <input type="password" id="loginPassword" class="form-input" placeholder="Enter your password" required autocomplete="current-password">
                    </div>
                    <button type="submit" class="submit-btn">
                        <span class="btn-text">
                            <span class="btn-label">Sign In</span>
                            <span class="spinner"></span>
                        </span>
                    </button>
                </form>

                <form id="registerForm">
                    <div class="form-group">
                        <label class="form-label" for="regUsername">Username</label>
                        <input type="text" id="regUsername" class="form-input" placeholder="Choose a username" required autocomplete="username">
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="regEmail">Email</label>
                        <input type="email" id="regEmail" class="form-input" placeholder="your@email.com" required autocomplete="email">
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="regPassword">Password</label>
                        <input type="password" id="regPassword" class="form-input" placeholder="Create a password" required autocomplete="new-password">
                    </div>
                    <button type="submit" class="submit-btn">
                        <span class="btn-text">
                            <span class="btn-label">Create Account</span>
                            <span class="spinner"></span>
                        </span>
                    </button>
                </form>
            </div>

            <div class="footer-text">
                Your personal AI mentor for success & growth
            </div>
        </div>
    </div>

    <script>
        const messageBox = document.getElementById('messageBox');
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const tabs = document.querySelectorAll('.tab');

        function showMessage(text, type) {
            messageBox.textContent = text;
            messageBox.className = 'message ' + type;
            setTimeout(() => {
                if (messageBox.classList.contains(type)) {
                    messageBox.style.opacity = '0';
                    setTimeout(() => {
                        messageBox.className = 'message';
                        messageBox.style.opacity = '1';
                    }, 300);
                }
            }, 5000);
        }

        function hideMessage() {
            messageBox.className = 'message';
        }

        function showLogin() {
            loginForm.classList.add('active');
            registerForm.classList.remove('active');
            tabs[0].classList.add('active');
            tabs[1].classList.remove('active');
            hideMessage();
        }

        function showRegister() {
            loginForm.classList.remove('active');
            registerForm.classList.add('active');
            tabs[0].classList.remove('active');
            tabs[1].classList.add('active');
            hideMessage();
        }

        function setLoading(form, loading) {
            const btn = form.querySelector('.submit-btn');
            const inputs = form.querySelectorAll('.form-input');
            if (loading) {
                btn.classList.add('loading');
                btn.disabled = true;
                inputs.forEach(input => input.disabled = true);
            } else {
                btn.classList.remove('loading');
                btn.disabled = false;
                inputs.forEach(input => input.disabled = false);
            }
        }

        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideMessage();
            setLoading(loginForm, true);

            try {
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
                    showMessage('Welcome back! Redirecting...', 'success');
                    setTimeout(() => {
                        window.location.replace('/chat');
                    }, 500);
                } else {
                    showMessage(result.message || 'Invalid username or password', 'error');
                    setLoading(loginForm, false);
                }
            } catch (error) {
                showMessage('Connection error. Please try again.', 'error');
                setLoading(loginForm, false);
            }
        });

        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideMessage();
            setLoading(registerForm, true);

            try {
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
                    showMessage('Account created successfully! Please sign in.', 'success');
                    setLoading(registerForm, false);
                    setTimeout(() => {
                        showLogin();
                        document.getElementById('loginUsername').value = document.getElementById('regUsername').value;
                        document.getElementById('loginPassword').focus();
                    }, 1500);
                } else {
                    showMessage(result.message || 'Registration failed. Please try again.', 'error');
                    setLoading(registerForm, false);
                }
            } catch (error) {
                showMessage('Connection error. Please try again.', 'error');
                setLoading(registerForm, false);
            }
        });

        // Handle Enter key in password fields
        document.getElementById('loginPassword').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') loginForm.requestSubmit();
        });
        document.getElementById('regPassword').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') registerForm.requestSubmit();
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, interactive-widget=resizes-content">
    <title>Jim Rohn AI Coach</title>
    <!-- Version 2.1 - Mobile Scroll Fix -->
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

        .sidebar-filters {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }

        .filter-btn {
            padding: 6px 12px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            background: transparent;
            color: #a1a1aa;
            border-radius: 20px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
        }

        .filter-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #f4f4f5;
        }

        .filter-btn.active {
            background: rgba(6, 182, 212, 0.2);
            border-color: rgba(6, 182, 212, 0.4);
            color: #a5f3fc;
        }

        .favorite-toggle {
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            cursor: pointer;
            font-size: 14px;
            opacity: 0.4;
            transition: all 0.2s ease;
            padding: 4px;
        }

        .favorite-toggle:hover {
            opacity: 1;
            transform: translateY(-50%) scale(1.2);
        }

        .favorite-toggle.active {
            opacity: 1;
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
            min-height: 0; /* Important for flex scrolling */
            overflow: hidden;
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

        .header-buttons {
            display: flex;
            gap: 12px;
            align-items: center;
        }

        .memory-btn {
            padding: 8px 16px;
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.4);
            border-radius: 12px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s ease;
        }

        .memory-btn:hover {
            background: rgba(59, 130, 246, 0.3);
            color: #93c5fd;
        }

        .profile-header {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #30363d;
            color: #f0f6fc;
        }

        .profile-header h2 {
            margin: 0;
            font-size: 1.5em;
        }

        .profile-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }

        .stat-card {
            background: #21262d;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #30363d;
            text-align: center;
        }

        .stat-number {
            font-size: 1.8em;
            font-weight: bold;
            color: #60a5fa;
        }

        .stat-label {
            color: #8b949e;
            font-size: 0.9em;
            margin-top: 5px;
        }

        .profile-section {
            background: #0d1117;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            border: 1px solid #30363d;
        }

        .profile-section h3 {
            color: #60a5fa;
            margin: 0 0 12px 0;
            font-size: 1.1em;
        }

        .profile-item {
            padding: 8px 0;
            color: #e6edf3;
            border-bottom: 1px solid #21262d;
        }

        .profile-item:last-child {
            border-bottom: none;
        }

        .profile-tag {
            display: inline-block;
            background: rgba(6, 182, 212, 0.2);
            color: #a5f3fc;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            margin: 3px;
        }

        .profile-empty {
            color: #8b949e;
            font-style: italic;
        }

        .chat-container {
            flex: 1;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
            padding: 16px;
            margin: 0 24px;
            background: rgba(9, 9, 11, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            position: relative;
            min-height: 0; /* Important for flex scrolling */
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

        .input-actions {
            display: flex;
            gap: 10px;
            align-items: stretch;
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
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .history-fav-btn {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 16px;
            padding: 2px 6px;
            border-radius: 4px;
            opacity: 0.5;
            transition: all 0.2s ease;
        }

        .history-fav-btn:hover {
            opacity: 1;
            background: rgba(255, 215, 0, 0.1);
        }

        .history-fav-btn.active {
            opacity: 1;
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
        /* Mobile Menu Button */
        .mobile-menu-btn {
            display: none;
            background: rgba(39, 39, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 10px 12px;
            cursor: pointer;
            color: #f4f4f5;
            font-size: 18px;
            transition: all 0.2s ease;
        }

        .mobile-menu-btn:hover {
            background: rgba(39, 39, 42, 0.9);
        }

        .mobile-menu-btn .bar {
            display: block;
            width: 20px;
            height: 2px;
            background: #f4f4f5;
            margin: 4px 0;
            border-radius: 2px;
            transition: all 0.3s ease;
        }

        /* Mobile Drawer Menu */
        .mobile-drawer {
            display: none;
            position: fixed;
            top: 0;
            right: -280px;
            width: 280px;
            height: 100vh;
            background: rgba(22, 27, 34, 0.98);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            z-index: 1001;
            transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border-left: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: -10px 0 40px rgba(0, 0, 0, 0.5);
        }

        .mobile-drawer.open {
            right: 0;
        }

        .mobile-drawer-header {
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .mobile-drawer-title {
            color: #f4f4f5;
            font-size: 1.1em;
            font-weight: 600;
        }

        .mobile-drawer-close {
            background: none;
            border: none;
            color: #8b949e;
            font-size: 24px;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 8px;
            transition: all 0.2s ease;
        }

        .mobile-drawer-close:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #f4f4f5;
        }

        .mobile-drawer-content {
            padding: 16px;
        }

        .mobile-menu-item {
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 16px;
            margin-bottom: 8px;
            background: rgba(39, 39, 42, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            color: #f4f4f5;
            text-decoration: none;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .mobile-menu-item:hover {
            background: rgba(39, 39, 42, 0.7);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .mobile-menu-item.memory-item {
            border-color: rgba(59, 130, 246, 0.3);
        }

        .mobile-menu-item.memory-item:hover {
            background: rgba(59, 130, 246, 0.15);
            border-color: rgba(59, 130, 246, 0.5);
        }

        .mobile-menu-item.history-item {
            border-color: rgba(6, 182, 212, 0.3);
        }

        .mobile-menu-item.history-item:hover {
            background: rgba(6, 182, 212, 0.15);
            border-color: rgba(6, 182, 212, 0.5);
        }

        .mobile-menu-item.logout-item {
            border-color: rgba(220, 53, 69, 0.3);
            color: #f87171;
        }

        .mobile-menu-item.logout-item:hover {
            background: rgba(220, 53, 69, 0.15);
            border-color: rgba(220, 53, 69, 0.5);
        }

        .mobile-menu-icon {
            font-size: 20px;
            width: 24px;
            text-align: center;
        }

        .mobile-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.6);
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .mobile-overlay.visible {
            opacity: 1;
        }

        /* Mobile Responsive Styles */
        @media (max-width: 768px) {
            body {
                overflow: auto;
                -webkit-overflow-scrolling: touch;
            }

            .sidebar {
                display: none;
            }

            .mobile-menu-btn {
                display: block;
            }

            .mobile-drawer {
                display: block;
            }

            .header-buttons {
                display: none;
            }

            .app-container {
                flex-direction: column;
                height: 100%;
                min-height: 100vh;
                min-height: -webkit-fill-available; /* iOS fix */
            }

            .main-content {
                flex: 1;
                display: flex;
                flex-direction: column;
                min-height: 0;
                height: 100%;
            }

            .main-header {
                padding: 12px 16px;
                flex-wrap: wrap;
                gap: 8px;
                flex-shrink: 0;
            }

            .header-info {
                flex: 1;
                min-width: 0;
            }

            .main-title {
                font-size: 1.25em;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .main-subtitle {
                font-size: 0.8em;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }

            .chat-container {
                margin: 8px 12px;
                padding: 12px;
                border-radius: 12px;
                flex: 1;
                min-height: 0;
                overflow-y: auto;
                -webkit-overflow-scrolling: touch;
                touch-action: pan-y;
                overscroll-behavior: contain;
            }

            .message {
                padding: 12px 14px;
                margin-bottom: 12px;
            }

            .user-message {
                margin-left: 12px;
            }

            .jim-message {
                margin-right: 12px;
            }

            /* Mobile Input Section - Redesigned */
            .input-section {
                margin: 8px 12px 16px 12px;
                padding: 14px;
                border-radius: 14px;
                flex-shrink: 0;
                position: relative;
                z-index: 10;
            }

            .voice-controls-row {
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 12px;
            }

            .voice-controls {
                flex: 1;
                justify-content: flex-start;
            }

            .input-row {
                flex-direction: column;
                gap: 12px;
            }

            .question-input {
                width: 100%;
                min-height: 80px;
                padding: 14px;
                font-size: 16px;
                border-radius: 14px;
                line-height: 1.5;
            }

            .input-actions {
                display: flex;
                gap: 10px;
                width: 100%;
            }

            .mic-button {
                width: 48px;
                height: 48px;
                border-radius: 14px;
                flex-shrink: 0;
            }

            .ask-button {
                flex: 1;
                padding: 14px 20px;
                font-size: 15px;
                border-radius: 14px;
                justify-content: center;
            }

            .stats {
                flex-direction: column;
                gap: 8px;
                align-items: flex-start;
            }

            .status-info {
                flex-wrap: wrap;
                gap: 10px;
            }

            /* Modal adjustments for mobile */
            .modal-content {
                margin: 0;
                width: 100%;
                height: 100%;
                max-height: 100%;
                border-radius: 0;
            }

            .profile-stats {
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
            }

            .stat-card {
                padding: 12px;
            }

            .stat-number {
                font-size: 1.4em;
            }
        }

        /* Small mobile devices */
        @media (max-width: 380px) {
            .main-title {
                font-size: 1.1em;
            }

            .question-input {
                min-height: 70px;
                font-size: 15px;
            }

            .voice-button {
                padding: 5px 8px;
                font-size: 11px;
            }

            .voice-label {
                font-size: 11px;
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
                <div class="sidebar-filters">
                    <button class="filter-btn active" id="filterAll" onclick="setFilter('all')">All</button>
                    <button class="filter-btn" id="filterFavorites" onclick="setFilter('favorites')">⭐ Favorites</button>
                </div>
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
                <div class="header-info">
                    <div class="main-title">Jim Rohn AI Coach</div>
                    <div class="main-subtitle">"Success is neither magical nor mysterious. Success is the natural consequence of consistently applying basic fundamentals."</div>
                </div>
                <div class="header-buttons">
                    <button class="memory-btn" onclick="showProfile()">🧠 My Memory</button>
                    <a href="/logout" class="logout-btn">Logout</a>
                </div>
                <!-- Mobile Menu Button -->
                <button class="mobile-menu-btn" onclick="toggleMobileMenu()" aria-label="Menu">
                    <span class="bar"></span>
                    <span class="bar"></span>
                    <span class="bar"></span>
                </button>
            </div>

            <!-- Mobile Drawer Menu -->
            <div class="mobile-overlay" id="mobileOverlay" onclick="closeMobileMenu()"></div>
            <div class="mobile-drawer" id="mobileDrawer">
                <div class="mobile-drawer-header">
                    <span class="mobile-drawer-title">Menu</span>
                    <button class="mobile-drawer-close" onclick="closeMobileMenu()">&times;</button>
                </div>
                <div class="mobile-drawer-content">
                    <div class="mobile-menu-item memory-item" onclick="showProfile(); closeMobileMenu();">
                        <span class="mobile-menu-icon">🧠</span>
                        <span>My Memory</span>
                    </div>
                    <div class="mobile-menu-item history-item" onclick="showHistory(); closeMobileMenu();">
                        <span class="mobile-menu-icon">📜</span>
                        <span>Conversation History</span>
                    </div>
                    <a href="/logout" class="mobile-menu-item logout-item">
                        <span class="mobile-menu-icon">🚪</span>
                        <span>Logout</span>
                    </a>
                </div>
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
                    <div class="input-actions">
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

    <!-- Profile/Memory Modal -->
    <div id="profileModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeProfile()">&times;</span>
            <div class="profile-header">
                <h2>🧠 What Jim Remembers About You</h2>
            </div>
            <div id="profileContent">
                <p>Loading your profile...</p>
            </div>
        </div>
    </div>

    <script>
        let conversationCount = 0;
        let recognition = null;
        let isRecording = false;
        let voiceEnabled = true;
        let audioUnlocked = false;
        let currentFilter = 'all';
        let allConversations = [];

        // Set filter for sidebar
        function setFilter(filter) {
            currentFilter = filter;
            document.getElementById('filterAll').classList.toggle('active', filter === 'all');
            document.getElementById('filterFavorites').classList.toggle('active', filter === 'favorites');
            loadRecentConversations(allConversations);
        }

        // Toggle favorite status
        async function toggleFavorite(timestamp, event) {
            event.stopPropagation();
            try {
                const response = await fetch('/api/favorite', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ timestamp: timestamp })
                });
                const data = await response.json();
                if (data.success) {
                    // Update local data
                    const conv = allConversations.find(c => c.timestamp === timestamp);
                    if (conv) conv.is_favorite = data.is_favorite;
                    loadRecentConversations(allConversations);
                }
            } catch (error) {
                console.error('Failed to toggle favorite:', error);
            }
        }

        // Load conversation count and recent conversations
        async function loadConversationCount() {
            try {
                const response = await fetch('/api/history');
                const data = await response.json();
                if (data.success) {
                    allConversations = data.conversations || [];
                    conversationCount = allConversations.length;
                    document.getElementById('conversationCount').textContent = conversationCount;

                    // Populate sidebar with recent conversations
                    loadRecentConversations(allConversations);
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

            // Filter by favorites if needed
            let filtered = conversations;
            if (currentFilter === 'favorites') {
                filtered = conversations.filter(c => c.is_favorite);
                if (filtered.length === 0) {
                    container.innerHTML = '<div class="conversation-item"><div class="conversation-question">No favorites yet</div><div class="conversation-meta">Click ⭐ to add favorites</div></div>';
                    return;
                }
            }

            // Sort: favorites first, then by timestamp (newest first)
            const recent = filtered
                .sort((a, b) => {
                    if (a.is_favorite && !b.is_favorite) return -1;
                    if (!a.is_favorite && b.is_favorite) return 1;
                    return new Date(b.timestamp) - new Date(a.timestamp);
                })
                .slice(0, 15);

            let html = '';
            recent.forEach((conv, index) => {
                const date = new Date(conv.timestamp);
                const timeAgo = getTimeAgo(date);
                const truncatedQuestion = conv.question.length > 50
                    ? conv.question.substring(0, 50) + '...'
                    : conv.question;
                const isFav = conv.is_favorite ? 'active' : '';
                const starIcon = conv.is_favorite ? '⭐' : '☆';

                html += `<div class="conversation-item" onclick="openConversationInHistory('${conv.timestamp}')">`;
                html += `<button class="favorite-toggle ${isFav}" onclick="toggleFavorite('${conv.timestamp}', event)" title="Toggle favorite">${starIcon}</button>`;
                html += `<div class="conversation-question">${truncatedQuestion}</div>`;
                html += `<div class="conversation-meta">${timeAgo}</div>`;
                html += `</div>`;
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
                            const starIcon = isFavorite ? '⭐' : '☆';
                            const favClass = isFavorite ? 'active' : '';

                            html += `<div class="history-conversation" onclick="toggleConversation(${index})">`;
                            html += `<div class="history-timestamp">`;
                            html += `<button class="history-fav-btn ${favClass}" onclick="toggleHistoryFavorite('${conversation.timestamp}', ${index}, event)">${starIcon}</button>`;
                            html += `${date}`;
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

        // Profile/Memory Modal Functions
        // Mobile Menu Functions
        function toggleMobileMenu() {
            const drawer = document.getElementById('mobileDrawer');
            const overlay = document.getElementById('mobileOverlay');
            drawer.classList.add('open');
            overlay.style.display = 'block';
            setTimeout(() => overlay.classList.add('visible'), 10);
            document.body.style.overflow = 'hidden';
        }

        function closeMobileMenu() {
            const drawer = document.getElementById('mobileDrawer');
            const overlay = document.getElementById('mobileOverlay');
            drawer.classList.remove('open');
            overlay.classList.remove('visible');
            setTimeout(() => {
                overlay.style.display = 'none';
                document.body.style.overflow = '';
            }, 300);
        }

        // Close mobile menu on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeMobileMenu();
            }
        });

        async function showProfile() {
            const modal = document.getElementById('profileModal');
            const content = document.getElementById('profileContent');

            if (!modal) {
                console.error('Profile modal not found!');
                return;
            }

            modal.style.display = 'block';
            content.innerHTML = '<p>Loading your profile...</p>';

            try {
                const response = await fetch('/api/profile');
                const data = await response.json();

                if (data.success) {
                    content.innerHTML = buildProfileHTML(data.profile);
                } else {
                    content.innerHTML = '<p>Error loading profile: ' + (data.error || 'Unknown error') + '</p>';
                }
            } catch (error) {
                console.error('Failed to load profile:', error);
                content.innerHTML = '<p>Error loading profile: ' + error.message + '</p>';
            }
        }

        function closeProfile() {
            document.getElementById('profileModal').style.display = 'none';
        }

        function buildProfileHTML(profile) {
            let html = '';

            // Stats Grid
            html += '<div class="profile-stats">';
            html += `<div class="stat-card">
                <div class="stat-number">${profile.total_conversations || 0}</div>
                <div class="stat-label">Conversations</div>
            </div>`;
            if (profile.first_conversation) {
                const memberSince = new Date(profile.first_conversation).toLocaleDateString();
                html += `<div class="stat-card">
                    <div class="stat-number" style="font-size: 1em;">${memberSince}</div>
                    <div class="stat-label">Member Since</div>
                </div>`;
            }
            html += '</div>';

            // Personal Info
            html += '<div class="profile-section">';
            html += '<h3>Personal Information</h3>';
            html += `<div class="profile-item"><strong>Name:</strong> ${profile.name || '<span class="profile-empty">Not yet learned</span>'}</div>`;
            html += `<div class="profile-item"><strong>Location:</strong> ${profile.location || '<span class="profile-empty">Not yet learned</span>'}</div>`;
            html += '</div>';

            // Recurring Themes
            html += '<div class="profile-section">';
            html += '<h3>Your Recurring Themes</h3>';
            if (profile.recurring_themes && profile.recurring_themes.length > 0) {
                html += '<div>';
                profile.recurring_themes.forEach(theme => {
                    html += `<span class="profile-tag">${theme}</span>`;
                });
                html += '</div>';
            } else {
                html += '<p class="profile-empty">No patterns identified yet. Keep chatting with Jim!</p>';
            }
            html += '</div>';

            // Goals
            html += '<div class="profile-section">';
            html += '<h3>Your Goals</h3>';
            if (profile.goals && profile.goals.length > 0) {
                profile.goals.forEach(goal => {
                    html += `<div class="profile-item">• ${goal}</div>`;
                });
            } else {
                html += '<p class="profile-empty">No goals identified yet. Share your aspirations with Jim!</p>';
            }
            html += '</div>';

            // Growth Areas
            html += '<div class="profile-section">';
            html += '<h3>Growth Areas</h3>';
            if (profile.growth_areas && profile.growth_areas.length > 0) {
                profile.growth_areas.forEach(area => {
                    html += `<div class="profile-item">• ${area}</div>`;
                });
            } else {
                html += '<p class="profile-empty">No growth areas identified yet.</p>';
            }
            html += '</div>';

            // Strengths
            if (profile.strengths && profile.strengths.length > 0) {
                html += '<div class="profile-section">';
                html += '<h3>Your Strengths</h3>';
                profile.strengths.forEach(strength => {
                    html += `<div class="profile-item">• ${strength}</div>`;
                });
                html += '</div>';
            }

            // Insights
            if (profile.insights && profile.insights.length > 0) {
                html += '<div class="profile-section">';
                html += '<h3>Insights About You</h3>';
                profile.insights.forEach(insight => {
                    html += `<div class="profile-item">• ${insight}</div>`;
                });
                html += '</div>';
            }

            return html;
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

        // Toggle favorite from history modal
        async function toggleHistoryFavorite(timestamp, index, event) {
            event.stopPropagation();
            try {
                const response = await fetch('/api/favorite', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ timestamp: timestamp })
                });
                const data = await response.json();
                if (data.success) {
                    // Update button appearance
                    const btn = event.target;
                    btn.textContent = data.is_favorite ? '⭐' : '☆';
                    btn.classList.toggle('active', data.is_favorite);
                    // Update local data
                    if (conversationsData[index]) {
                        conversationsData[index].is_favorite = data.is_favorite;
                    }
                    // Also update allConversations for sidebar
                    const conv = allConversations.find(c => c.timestamp === timestamp);
                    if (conv) conv.is_favorite = data.is_favorite;
                    loadRecentConversations(allConversations);
                }
            } catch (error) {
                console.error('Failed to toggle favorite:', error);
            }
        }

        // Close modal when clicking outside of it
        window.onclick = function(event) {
            const historyModal = document.getElementById('historyModal');
            const profileModal = document.getElementById('profileModal');
            if (event.target === historyModal) {
                closeHistory();
            }
            if (event.target === profileModal) {
                closeProfile();
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
                    // Ensure scroll is re-enabled on mobile after audio playback
                    document.body.style.overflow = '';
                    const chatContainer = document.getElementById('chatContainer');
                    if (chatContainer) {
                        chatContainer.style.overflow = '';
                        chatContainer.style.overflowY = 'auto';
                    }
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
                const response = await fetch('/admin/stats', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: password })
                });
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