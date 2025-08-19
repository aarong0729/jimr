#!/usr/bin/env python3

import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import webbrowser

load_dotenv()

class JimRohnCoach:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.conversations = []
        
        # Memory system files
        self.conversation_history_file = "conversation_history.json"
        self.user_profile_file = "user_profile.json"
        
        # Load existing data
        self.conversation_history = self.load_conversation_history()
        self.user_profile = self.load_user_profile()
        
        # Load the system prompt
        try:
            with open('System prompt.txt', 'r') as f:
                self.system_prompt = f.read()
                print("✅ Loaded custom Jim Rohn system prompt")
        except FileNotFoundError:
            self.system_prompt = """You are Jim Rohn, the legendary personal development speaker. 
            Respond with wisdom, warmth, and practical advice in your distinctive style."""
            print("⚠️  Using basic system prompt")
        
        print(f"📚 Loaded {len(self.conversation_history)} past conversations")
        print(f"🧠 User profile: {len(self.user_profile.get('recurring_themes', []))} themes tracked")
    
    def clean_text_for_speech(self, text: str) -> str:
        """Clean text for better speech synthesis by removing markdown and formatting."""
        import re
        
        # Remove markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove **bold**
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove *italic*
        text = re.sub(r'__(.*?)__', r'\1', text)      # Remove __underline__
        text = re.sub(r'_(.*?)_', r'\1', text)        # Remove _italic_
        
        # Remove other markdown elements
        text = re.sub(r'#{1,6}\s+', '', text)         # Remove headers
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)  # Remove code blocks
        text = re.sub(r'`([^`]+)`', r'\1', text)      # Remove inline code
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Remove links, keep text
        
        # Clean up quotation marks for speech
        text = re.sub(r'"([^"]*)"', r'"\1"', text)    # Standardize quotes
        text = text.replace(''', "'")                 # Convert smart quotes
        text = text.replace(''', "'")                 # Convert smart quotes
        text = text.replace('"', '"')                 # Convert smart quotes
        text = text.replace('"', '"')                 # Convert smart quotes
        
        # Remove excessive punctuation
        text = re.sub(r'[•·–—]', '-', text)           # Replace special dashes
        text = re.sub(r'\.{2,}', '.', text)           # Replace multiple dots
        text = re.sub(r'\s+', ' ', text)              # Replace multiple spaces
        
        # Remove common problematic characters
        text = text.replace(':', ': ')                # Ensure space after colons
        text = text.replace(';', '. ')                # Replace semicolons with periods
        text = text.replace('&', 'and')               # Replace ampersands
        
        return text.strip()
    
    def load_conversation_history(self):
        """Load conversation history from JSON file."""
        try:
            with open(self.conversation_history_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    def load_user_profile(self):
        """Load user profile from JSON file."""
        try:
            with open(self.user_profile_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "name": "",
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
    
    def save_memory(self):
        """Save both conversation history and user profile."""
        # Save conversation history
        with open(self.conversation_history_file, 'w') as f:
            json.dump(self.conversation_history, f, indent=2)
        
        # Save user profile
        with open(self.user_profile_file, 'w') as f:
            json.dump(self.user_profile, f, indent=2)
    
    def analyze_conversation_patterns(self, user_question: str, jim_response: str):
        """Analyze conversation to extract themes and patterns."""
        try:
            analysis_prompt = f"""
            Analyze this conversation for themes and patterns:
            
            User Question: "{user_question}"
            Jim's Response: "{jim_response}"
            
            Current user profile: {json.dumps(self.user_profile, indent=2)}
            
            Extract and return JSON with:
            1. "themes" - Key themes from this conversation (max 3)
            2. "growth_areas" - Areas where user needs development (max 2) 
            3. "goals" - Any goals mentioned or implied (max 2)
            4. "challenges" - Challenges user is facing (max 2)
            5. "insights" - Key insights about the user (max 1)
            
            Keep responses concise and focus on actionable items.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "system", "content": analysis_prompt}],
                temperature=0.3,
                max_tokens=300
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # Update user profile with new insights
            for theme in analysis.get("themes", []):
                if theme not in self.user_profile["recurring_themes"]:
                    self.user_profile["recurring_themes"].append(theme)
            
            for area in analysis.get("growth_areas", []):
                if area not in self.user_profile["growth_areas"]:
                    self.user_profile["growth_areas"].append(area)
            
            for goal in analysis.get("goals", []):
                if goal not in self.user_profile["goals"]:
                    self.user_profile["goals"].append(goal)
                    
            for challenge in analysis.get("challenges", []):
                if challenge not in self.user_profile["challenges"]:
                    self.user_profile["challenges"].append(challenge)
            
            for insight in analysis.get("insights", []):
                self.user_profile["insights"].append(insight)
            
            # Keep lists manageable (last 10 items)
            for key in ["recurring_themes", "growth_areas", "goals", "challenges"]:
                if key in self.user_profile:
                    self.user_profile[key] = self.user_profile[key][-10:]
            
            # Keep last 5 insights
            self.user_profile["insights"] = self.user_profile["insights"][-5:]
            
        except Exception as e:
            print(f"⚠️ Pattern analysis failed: {e}")
    
    def extract_personal_details(self, question: str, response: str):
        """Extract and update personal details from conversations."""
        try:
            import re
            
            # Extract name if mentioned in introduction format
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
                        self.user_profile["name"] = name
                        print(f"💡 Extracted name: {name}")
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
                        self.user_profile["location"] = location
                        print(f"💡 Extracted location: {location}")
                        break
                        
        except Exception as e:
            print(f"⚠️ Personal detail extraction failed: {e}")
    
    def get_conversation_context(self, current_question: str):
        """Get relevant context from past conversations."""
        context = []
        
        # Add personal details first
        personal_info = []
        if self.user_profile.get("name"):
            personal_info.append(f"User's name: {self.user_profile['name']}")
        if self.user_profile.get("location"):
            personal_info.append(f"Location: {self.user_profile['location']}")
        
        if personal_info:
            context.append("Personal Information: " + ", ".join(personal_info))
        
        # Add user profile summary
        if self.user_profile.get("recurring_themes"):
            context.append(f"User's recurring themes: {', '.join(self.user_profile['recurring_themes'][-5:])}")
        
        if self.user_profile.get("growth_areas"):
            context.append(f"Growth areas: {', '.join(self.user_profile['growth_areas'][-3:])}")
        
        if self.user_profile.get("goals"):
            context.append(f"Current goals: {', '.join(self.user_profile['goals'][-3:])}")
        
        # Search recent conversations for similar topics
        recent_conversations = self.conversation_history[-10:]  # Last 10 conversations
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
    
    def ask_jim(self, question: str, generate_voice: bool = True) -> dict:
        """Get Jim's response to a question."""
        try:
            # Get conversation context from memory
            context = self.get_conversation_context(question)
            
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
                    import re
                    
                    elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
                    
                    # Clean text for speech synthesis
                    clean_text = self.clean_text_for_speech(jim_response)
                    
                    # Use the correct API method and convert generator to bytes
                    audio_generator = elevenlabs_client.text_to_speech.convert(
                        voice_id=os.getenv("JIM_ROHN_VOICE_ID"),
                        text=clean_text,
                        model_id="eleven_monolingual_v1"
                    )
                    audio_data = b"".join(audio_generator)
                    print(f"✅ Generated voice response ({len(audio_data)} bytes)")
                    
                except Exception as voice_error:
                    print(f"⚠️ Voice generation failed: {voice_error}")
                    audio_data = None
            
            # Store conversation in memory system
            conversation = {
                "question": question,
                "response": jim_response,
                "timestamp": datetime.now().isoformat(),
                "has_audio": audio_data is not None,
                "is_favorite": False
            }
            self.conversations.append(conversation)
            self.conversation_history.append(conversation)
            
            # Extract personal details and analyze patterns
            self.extract_personal_details(question, jim_response)
            self.analyze_conversation_patterns(question, jim_response)
            self.user_profile["total_conversations"] = len(self.conversation_history)
            self.user_profile["last_conversation"] = conversation["timestamp"]
            if not self.user_profile.get("first_conversation"):
                self.user_profile["first_conversation"] = conversation["timestamp"]
            
            # Save memory to disk
            self.save_memory()
            
            return {
                "success": True,
                "response": jim_response,
                "conversation_count": len(self.conversations),
                "audio": audio_data,
                "has_voice": audio_data is not None
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"I'm having some technical difficulties, my friend. Error: {str(e)}",
                "error": str(e),
                "audio": None,
                "has_voice": False
            }

# Initialize coach
coach = JimRohnCoach()

# HTML template with professional dark mode design
HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jim Rohn AI Coach</title>
    <!-- Version 2.0 - Modern Buttons -->
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
            color: #71717a;
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
                <div class="main-title">
                    Jim Rohn AI Coach
                </div>
                <div class="main-subtitle">"Success is neither magical nor mysterious. Success is the natural consequence of consistently applying basic fundamentals."</div>
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
                const response = await fetch('/history');
                const data = await response.json();
                conversationCount = data.total_conversations || 0;
                document.getElementById('conversationCount').textContent = conversationCount;
                
                // Populate sidebar with recent conversations
                loadRecentConversations(data.conversations || []);
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
            
            fetch('/history')
                .then(response => response.json())
                .then(data => {
                    let html = '';
                    
                    // Add profile summary
                    if (data.user_profile) {
                        html += '<div class="profile-summary">';
                        html += '<h3>Your Learning Profile</h3>';
                        html += `<p><strong>Total Conversations:</strong> ${data.total_conversations}</p>`;
                        
                        if (data.user_profile.recurring_themes && data.user_profile.recurring_themes.length > 0) {
                            html += `<p><strong>Key Themes:</strong> ${data.user_profile.recurring_themes.join(', ')}</p>`;
                        }
                        
                        if (data.user_profile.goals && data.user_profile.goals.length > 0) {
                            html += `<p><strong>Goals:</strong> ${data.user_profile.goals.join(', ')}</p>`;
                        }
                        
                        if (data.user_profile.growth_areas && data.user_profile.growth_areas.length > 0) {
                            html += `<p><strong>Growth Areas:</strong> ${data.user_profile.growth_areas.join(', ')}</p>`;
                        }
                        
                        html += '</div>';
                    }
                    
                    // Add conversations
                    if (data.conversations && data.conversations.length > 0) {
                        html += '<h3>Recent Conversations</h3>';
                        
                        // Add filter buttons
                        html += '<div class="favorites-filter">';
                        html += '<button class="filter-button active" onclick="filterConversations(&apos;all&apos;)">All Conversations</button>';
                        html += '<button class="filter-button" onclick="filterConversations(&apos;favorites&apos;)">Favorites Only</button>';
                        html += '</div>';
                        
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
                            
                            // Add favorite button in header
                            html += `<button class="favorite-button ${isFavorite ? 'favorited' : ''}" onclick="event.stopPropagation(); toggleFavorite('${conversation.timestamp}', ${index})">`;
                            html += isFavorite ? '⭐' : '☆';
                            html += '</button>';
                            
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

        // Toggle favorite status
        async function toggleFavorite(timestamp, index) {
            try {
                const response = await fetch('/toggle-favorite', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: 'timestamp=' + encodeURIComponent(timestamp)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Update the conversation data
                    conversationsData[index].is_favorite = !conversationsData[index].is_favorite;
                    
                    // Update the star button - find by data attributes instead of onclick
                    const buttons = document.querySelectorAll('.favorite-button');
                    let button = null;
                    buttons.forEach(btn => {
                        if (btn.onclick && btn.onclick.toString().includes(timestamp)) {
                            button = btn;
                        }
                    });
                    if (button) {
                        if (conversationsData[index].is_favorite) {
                            button.classList.add('favorited');
                            button.textContent = '⭐';
                        } else {
                            button.classList.remove('favorited');
                            button.textContent = '☆';
                        }
                    }
                    
                    // Update conversation classes for filtering
                    const conversationDiv = button.closest('.history-conversation');
                    if (conversationDiv) {
                        conversationDiv.classList.remove('all-conversations', 'favorites-only');
                        conversationDiv.classList.add(conversationsData[index].is_favorite ? 'favorites-only' : 'all-conversations');
                    }
                } else {
                    alert('Failed to update favorite status');
                }
            } catch (error) {
                console.error('Error toggling favorite:', error);
                alert('Error updating favorite status');
            }
        }
        
        // Filter conversations by type
        function filterConversations(type) {
            const buttons = document.querySelectorAll('.filter-button');
            const conversations = document.querySelectorAll('.history-conversation');
            
            // Update button states
            buttons.forEach(btn => {
                btn.classList.remove('active');
                if ((type === 'all' && btn.textContent.includes('All Conversations')) ||
                    (type === 'favorites' && btn.textContent.includes('Favorites'))) {
                    btn.classList.add('active');
                }
            });
            
            // Show/hide conversations
            conversations.forEach(conv => {
                if (type === 'all') {
                    conv.style.display = 'block';
                } else if (type === 'favorites') {
                    const isFavorite = conv.classList.contains('favorites-only');
                    conv.style.display = isFavorite ? 'block' : 'none';
                }
            });
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
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: 'question=' + encodeURIComponent(question) + '&voice=' + voiceEnabled
                });

                const text = await response.text();
                const data = JSON.parse(text);

                // Remove loading message
                chatContainer.removeChild(loadingMessage);

                if (data.success) {
                    // Add Jim's response
                    const messageElement = addMessage('Jim Rohn', data.response, 'jim-message');
                    
                    // Play audio if available
                    if (data.has_voice && data.audio && voiceEnabled) {
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
                    conversationCount = data.conversation_count;
                    document.getElementById('conversationCount').textContent = conversationCount;
                    statusText.textContent = 'Connected & Ready';
                    
                    // Refresh recent conversations in sidebar
                    loadConversationCount();
                } else {
                    // Add error message
                    addMessage('Jim Rohn', data.response, 'jim-message');
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
                askButton.textContent = 'Ask Jim';
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
</html>'''

class JimRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
        elif self.path == '/history':
            try:
                history_data = {
                    "conversations": coach.conversation_history[-50:],
                    "user_profile": coach.user_profile,
                    "total_conversations": len(coach.conversation_history)
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(history_data).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = json.dumps({"error": str(e)})
                self.wfile.write(error_response.encode('utf-8'))
        elif self.path == '/toggle-favorite':
            # Handle favorite toggling
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'404 - Not Found')
    
    def do_POST(self):
        if self.path == '/ask':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length).decode('utf-8')
                params = urllib.parse.parse_qs(post_data)
                question = params.get('question', [''])[0]
                voice_enabled = params.get('voice', ['false'])[0].lower() == 'true'
                
                if question:
                    result = coach.ask_jim(question, generate_voice=voice_enabled)
                    
                    # Convert audio data to base64 for JSON transmission
                    if result.get('audio'):
                        import base64
                        result['audio'] = base64.b64encode(result['audio']).decode('utf-8')
                    
                    response_text = json.dumps(result)
                else:
                    response_text = json.dumps({
                        "success": False,
                        "response": "Please ask me something!"
                    })
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(response_text.encode('utf-8'))
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = json.dumps({
                    "success": False,
                    "response": f"Server error: {str(e)}"
                })
                self.wfile.write(error_response.encode('utf-8'))
        elif self.path == '/toggle-favorite':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length).decode('utf-8')
                params = urllib.parse.parse_qs(post_data)
                timestamp = params.get('timestamp', [''])[0]
                
                if timestamp:
                    # Find conversation by timestamp and toggle favorite
                    for conversation in coach.conversation_history:
                        if conversation.get('timestamp') == timestamp:
                            conversation['is_favorite'] = not conversation.get('is_favorite', False)
                            break
                    
                    # Save updated history
                    coach.save_memory()
                    
                    response_text = json.dumps({"success": True})
                else:
                    response_text = json.dumps({"success": False, "error": "No timestamp provided"})
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(response_text.encode('utf-8'))
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = json.dumps({
                    "success": False,
                    "error": str(e)
                })
                self.wfile.write(error_response.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def find_available_port(start_port=9999):
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError("No available ports found")

def open_browser_delayed(url, delay=2):
    time.sleep(delay)
    try:
        webbrowser.open(url)
        print(f"🌐 Opened {url} in your browser")
    except:
        print(f"🌐 Please manually open: {url}")

def main():
    print("🧠 Jim Rohn AI Coach - Clean Working Version")
    print("=" * 50)
    
    # Find available port
    try:
        port = find_available_port(9999)
        print(f"✅ Found available port: {port}")
    except RuntimeError as e:
        print(f"❌ {e}")
        return
    
    # Create and start server
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, JimRequestHandler)
    
    url = f"http://127.0.0.1:{port}"
    print(f"🌐 Jim Rohn AI Coach starting at: {url}")
    print("✅ Server is ready!")
    print("=" * 50)
    print("Press Ctrl+C to stop the server")
    
    # Start browser opener in background
    browser_thread = threading.Thread(target=open_browser_delayed, args=(url, 2))
    browser_thread.daemon = True
    browser_thread.start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n👋 Jim Rohn AI Coach shutting down...")
        print(f"💾 Served {len(coach.conversations)} conversations")
        httpd.shutdown()
        httpd.server_close()
        print("✅ Server stopped gracefully")

if __name__ == "__main__":
    main()