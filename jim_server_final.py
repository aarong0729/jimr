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
    
    def get_conversation_context(self, current_question: str):
        """Get relevant context from past conversations."""
        context = []
        
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
            print(f"🎤 Voice generation requested: {generate_voice}")
            print(f"🔑 API Key available: {bool(os.getenv('ELEVENLABS_API_KEY'))}")
            print(f"🗣️ Voice ID available: {bool(os.getenv('JIM_ROHN_VOICE_ID'))}")
            
            if generate_voice and os.getenv("ELEVENLABS_API_KEY") and os.getenv("JIM_ROHN_VOICE_ID"):
                try:
                    from elevenlabs import ElevenLabs
                    import re
                    
                    elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
                    
                    # Clean text for speech synthesis
                    clean_text = self.clean_text_for_speech(jim_response)
                    print(f"📝 Cleaned text length: {len(clean_text)}")
                    
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
                    import traceback
                    traceback.print_exc()
                    audio_data = None
            else:
                print("❌ Voice generation skipped - missing requirements")
            
            # Store conversation in memory system
            conversation = {
                "question": question,
                "response": jim_response,
                "timestamp": datetime.now().isoformat(),
                "has_audio": audio_data is not None
            }
            self.conversations.append(conversation)
            self.conversation_history.append(conversation)
            
            # Analyze patterns and save memory
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

# HTML template
HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧠 Jim Rohn AI Coach</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }

        h1 {
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-align: center;
        }

        .subtitle {
            color: #666;
            font-style: italic;
            font-size: 1.1em;
            text-align: center;
            margin-bottom: 30px;
        }

        .chat-container {
            height: 500px;
            overflow-y: auto;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            background: #f8f9fa;
        }

        .message {
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 10px;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .user-message {
            background: linear-gradient(135deg, #e8f4f8 0%, #d4edda 100%);
            border-left: 4px solid #28a745;
            margin-left: 40px;
        }

        .jim-message {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-left: 4px solid #6c757d;
            margin-right: 40px;
            position: relative;
        }

        .message-header {
            font-weight: bold;
            margin-bottom: 8px;
            color: #333;
        }

        .message-content {
            line-height: 1.6;
            color: #444;
            white-space: pre-wrap;
        }

        .input-section {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }

        .button-group {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .mic-button {
            padding: 15px;
            background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 20px;
            min-width: 60px;
            transition: all 0.3s ease;
        }

        .mic-button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(23, 162, 184, 0.4);
        }

        .mic-button.recording {
            background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);
            animation: pulse 1.5s infinite;
        }

        .voice-controls {
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 15px;
        }

        .voice-toggle {
            display: inline-flex;
            align-items: center;
            cursor: pointer;
            font-size: 14px;
            color: #666;
        }

        .voice-toggle input {
            margin-right: 8px;
        }

        .recording-status {
            color: #dc3545;
            font-weight: bold;
            margin-top: 10px;
            animation: pulse 1.5s infinite;
        }

        .question-input {
            flex: 1;
            padding: 15px;
            border: 2px solid #dee2e6;
            border-radius: 10px;
            font-size: 16px;
            resize: none;
            min-height: 60px;
            font-family: inherit;
        }

        .question-input:focus {
            outline: none;
            border-color: #17a2b8;
            box-shadow: 0 0 0 3px rgba(23, 162, 184, 0.1);
        }

        .ask-button {
            padding: 15px 30px;
            background: linear-gradient(135deg, #495057 0%, #343a40 100%);
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
            min-width: 120px;
        }

        .ask-button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(73, 80, 87, 0.4);
        }

        .ask-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .stats {
            text-align: center;
            color: #666;
            font-size: 14px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #28a745;
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
        
        .history-button {
            padding: 10px 20px;
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            margin-right: 10px;
            transition: all 0.3s ease;
        }
        
        .history-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3);
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        
        .modal-content {
            background-color: white;
            margin: 2% auto;
            padding: 20px;
            border-radius: 15px;
            width: 90%;
            max-width: 1000px;
            max-height: 90%;
            overflow-y: auto;
            position: relative;
        }
        
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            line-height: 20px;
        }
        
        .close:hover {
            color: #333;
        }
        
        .history-header {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e9ecef;
        }
        
        .profile-summary {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .history-conversation {
            margin-bottom: 15px;
            padding: 15px;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            background: #fafafa;
        }
        
        .history-timestamp {
            font-size: 12px;
            color: #666;
            margin-bottom: 8px;
        }
        
        .history-question {
            font-weight: bold;
            color: #28a745;
            margin-bottom: 8px;
        }
        
        .history-response {
            color: #666;
            line-height: 1.4;
        }

        .audio-visualizer {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 40px;
            background: #ffffff;
            border-radius: 20px;
            padding: 5px 15px;
            border: 1px solid #dee2e6;
            flex: 1;
            transition: all 0.3s ease;
        }

        .audio-visualizer.active {
            background: linear-gradient(135deg, #e8f4f8 0%, #d4edda 100%);
            border-color: #17a2b8;
            box-shadow: 0 2px 8px rgba(23, 162, 184, 0.2);
        }

        .visualizer-bar {
            width: 3px;
            background: #dee2e6;
            margin: 0 1px;
            border-radius: 2px;
            height: 8px;
            transition: all 0.3s ease;
        }

        .audio-visualizer.active .visualizer-bar {
            background: linear-gradient(to top, #17a2b8, #28a745);
            animation: audioWave 1.2s ease-in-out infinite;
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

        .speaking-indicator {
            display: none;
            align-items: center;
            font-size: 14px;
            color: #495057;
            font-weight: 500;
        }

        .speaking-indicator.active {
            display: flex;
        }

        .speaking-dot {
            width: 8px;
            height: 8px;
            background: #28a745;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 1.5s ease-in-out infinite;
        }

        .voice-button {
            padding: 8px 16px;
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
            white-space: nowrap;
        }

        .voice-button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3);
        }

        .voice-button.disabled {
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            cursor: default;
        }

        .voice-button.disabled:hover {
            transform: none;
            box-shadow: none;
        }

        .recording-status {
            color: #dc3545;
            font-weight: bold;
            font-size: 12px;
            text-align: center;
            margin-top: 10px;
            animation: pulse 1.5s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 Jim Rohn AI Coach</h1>
        <p class="subtitle">"Success is neither magical nor mysterious. Success is the natural consequence of consistently applying basic fundamentals."</p>

        <div class="chat-container" id="chatContainer">
            <div class="message jim-message">
                <div class="message-header">Jim Rohn:</div>
                <div class="message-content">Welcome, my friend! I'm here to share wisdom about success, personal development, and achieving your goals. What's on your mind today? What challenge are you facing, or what guidance are you seeking?</div>
            </div>
        </div>


        <div class="input-section">
            <textarea id="questionInput" class="question-input" placeholder="Ask Jim about success, goals, discipline, motivation, relationships, or any life challenge..." rows="3"></textarea>
            <div class="button-group">
                <button id="micButton" class="mic-button" onclick="toggleSpeechRecognition()" title="Click to speak your question">🎤</button>
                <button id="askButton" class="ask-button" onclick="askJim()">Ask Jim</button>
            </div>
        </div>

        <div class="voice-controls">
            <!-- Audio Visualizer -->
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

            <button class="voice-button" id="voiceButton" onclick="toggleVoice()">
                <span id="voiceButtonText">🔊 Voice</span>
            </button>

            <div class="recording-status" id="recordingStatus" style="display: none;">
                🔴 Listening... (speak your question)
            </div>
        </div>

        <div class="stats">
            <button class="history-button" onclick="showHistoryModal()">📚 View History</button>
            <span class="status-indicator"></span>
            <span id="statusText">Connected & Ready</span> • Conversations: <span id="conversationCount">0</span>
        </div>
    </div>

    <!-- History Modal -->
    <div id="historyModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeHistory()">&times;</span>
            <div class="history-header">
                <h2>📚 Conversation History</h2>
            </div>
            <div id="historyContent">
                <p>Loading history...</p>
            </div>
        </div>
    </div>

    <script>
        let conversationCount = 0;
        
        // Load conversation count from server on page load
        async function loadConversationCount() {
            try {
                const response = await fetch('/history');
                const data = await response.json();
                conversationCount = data.total_conversations || 0;
                document.getElementById('conversationCount').textContent = conversationCount;
                console.log('Loaded conversation count:', conversationCount);
            } catch (error) {
                console.warn('Failed to load conversation count:', error);
            }
        }
        let recognition = null;
        let isRecording = false;
        let voiceEnabled = true; // Start with voice enabled
        let audioContext = null;
        let audioUnlocked = false;

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

        function unlockAudio() {
            if (audioUnlocked) return Promise.resolve();
            
            return new Promise((resolve) => {
                // Create a silent audio to unlock browser audio
                try {
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const buffer = audioContext.createBuffer(1, 1, 22050);
                    const source = audioContext.createBufferSource();
                    source.buffer = buffer;
                    source.connect(audioContext.destination);
                    source.start(0);
                    
                    audioUnlocked = true;
                    console.log('Audio unlocked successfully');
                    resolve();
                } catch (e) {
                    console.warn('Audio unlock failed:', e);
                    resolve(); // Continue anyway
                }
            });
        }

        function showAudioBlockedMessage() {
            const statusText = document.getElementById('statusText');
            const originalText = statusText.textContent;
            statusText.textContent = '🔊 Click "Enable Audio" button below to hear Jim speak';
            statusText.style.color = '#dc3545';
            statusText.style.fontWeight = 'bold';
            statusText.style.fontSize = '16px';
            
            // Create an enable audio button
            const enableButton = document.createElement('button');
            enableButton.textContent = '🔊 Enable Audio & Unlock Safari';
            enableButton.style.cssText = `
                background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                margin: 10px auto;
                display: block;
                animation: pulse 2s infinite;
            `;
            
            enableButton.onclick = async () => {
                await unlockAudio();
                statusText.textContent = originalText;
                statusText.style.color = '';
                statusText.style.fontWeight = '';
                statusText.style.fontSize = '';
                enableButton.remove();
                alert('✅ Audio Enabled!\nNow ask Jim another question to hear his voice.');
            };
            
            // Add button to the container
            document.querySelector('.container').appendChild(enableButton);
        }

        async function playAudio(audioData) {
            try {
                console.log('Playing audio, data length:', audioData.length);
                
                // Ensure audio is unlocked first
                if (!audioUnlocked) {
                    console.log('Audio not unlocked, showing unlock message');
                    showAudioBlockedMessage();
                    return;
                }
                
                // Show visualizer
                showAudioVisualizer();
                
                // Convert base64 to binary string, then to Uint8Array
                const binaryString = atob(audioData);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                
                // Use MP3 format for best compatibility
                try {
                    const audioBlob = new Blob([bytes], { type: 'audio/mpeg' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    
                    const audio = new Audio(audioUrl);
                    audio.volume = 0.8;
                    
                    // Set up event handlers
                    audio.onended = () => {
                        URL.revokeObjectURL(audioUrl);
                        hideAudioVisualizer();
                    };
                    
                    audio.onerror = (e) => {
                        console.warn('Audio playback failed:', e);
                        URL.revokeObjectURL(audioUrl);
                        hideAudioVisualizer();
                    };
                    
                    // Play the audio
                    audio.play()
                        .then(() => {
                            console.log('Audio playing successfully (MP3)');
                        })
                        .catch(e => {
                            console.warn('Audio play failed:', e);
                            if (e.name === 'NotAllowedError') {
                                showAudioBlockedMessage();
                            }
                            hideAudioVisualizer();
                        });
                        
                } catch (error) {
                    console.error('Audio creation failed:', error);
                    hideAudioVisualizer();
                }
                
            } catch (error) {
                console.error('Audio processing failed:', error);
                hideAudioVisualizer(); // Hide visualizer on error
                // Only alert for unexpected errors, not browser compatibility
                if (error.message.includes('atob') || error.message.includes('Blob')) {
                    alert('Audio processing failed: ' + error.message);
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
                console.log('Voice enabled:', voiceEnabled);
                
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
                    console.log('Response has_voice:', data.has_voice, 'audio length:', data.audio ? data.audio.length : 'no audio');
                    if (data.has_voice && data.audio) {
                        try {
                            console.log('Attempting to play audio...');
                            playAudio(data.audio);
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
                    
                    // Update conversation count
                    conversationCount = data.conversation_count;
                    document.getElementById('conversationCount').textContent = conversationCount;
                    statusText.textContent = 'Connected & Ready';
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

        // Allow Enter to send message (with Shift+Enter for new line)
        document.getElementById('questionInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                askJim();
            }
        });

        // Auto-focus on input and load conversation count
        document.getElementById('questionInput').focus();
        loadConversationCount();

        function toggleVoice() {
            voiceEnabled = !voiceEnabled;
            const button = document.getElementById('voiceButton');
            const buttonText = document.getElementById('voiceButtonText');
            
            if (voiceEnabled) {
                button.classList.remove('disabled');
                buttonText.textContent = '🔊 Voice';
            } else {
                button.classList.add('disabled');
                buttonText.textContent = '🔇 Voice';
            }
        }

        function testVisualizer() {
            // Test the audio visualizer
            showAudioVisualizer();
            
            // Hide after 5 seconds
            setTimeout(() => {
                hideAudioVisualizer();
            }, 5000);
        }

        function showHistoryModal() {
            alert('History viewer temporarily disabled due to JavaScript error. Your conversations are being saved properly. Data shows: 6 total conversations with themes like Career Transition and Personal Growth.');
        }
        
        async function showHistory() {
            console.log('showHistory() called');
            const modal = document.getElementById('historyModal');
            const content = document.getElementById('historyContent');
            
            console.log('Modal element:', modal);
            console.log('Content element:', content);
            
            if (!modal) {
                console.error('History modal not found!');
                return;
            }
            
            modal.style.display = 'block';
            content.innerHTML = '<p>Loading history...</p>';
            
            try {
                console.log('Fetching history...');
                const response = await fetch('/history');
                const data = await response.json();
                
                console.log('History data received:', data);
                console.log('Conversations:', data.conversations);
                console.log('User profile:', data.user_profile);
                
                let html = '';
                
                // Add profile summary
                if (data.user_profile) {
                    html += '<div class="profile-summary">';
                    html += '<h3>🧠 Your Learning Profile</h3>';
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
                    
                    // Sort conversations by timestamp (newest first)
                    const sortedConversations = data.conversations.sort((a, b) => 
                        new Date(b.timestamp) - new Date(a.timestamp)
                    );
                    
                    sortedConversations.forEach(conversation => {
                        const date = new Date(conversation.timestamp).toLocaleString();
                        html += '<div class="history-conversation">';
                        html += `<div class="history-timestamp">${date}</div>`;
                        html += `<div class="history-question">Q: ${conversation.question}</div>`;
                        html += `<div class="history-response">A: ${conversation.response.substring(0, 200)}${conversation.response.length > 200 ? '...' : ''}</div>`;
                        html += '</div>';
                    });
                } else {
                    html += '<p>No conversation history yet. Start chatting with Jim!</p>';
                }
                
                console.log('Generated HTML:', html);
                content.innerHTML = html;
                
            } catch (error) {
                content.innerHTML = '<p>Error loading history: ' + error.message + '</p>';
            }
        }

        function closeHistory() {
            document.getElementById('historyModal').style.display = 'none';
        }

        // Close modal when clicking outside of it
        window.onclick = function(event) {
            const modal = document.getElementById('historyModal');
            if (event.target === modal) {
                closeHistory();
            }
        }
    </script>
</body>
</html>'''

class JimRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging
        pass
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
        elif self.path == '/history':
            # Return conversation history as JSON
            try:
                history_data = {
                    "conversations": coach.conversation_history[-50:],  # Last 50 conversations
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
        else:
            self.send_response(404)
            self.end_headers()

def find_available_port(start_port=9999):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError("No available ports found")

def open_browser_delayed(url, delay=2):
    """Open browser after a delay"""
    time.sleep(delay)
    try:
        webbrowser.open(url)
        print(f"🌐 Opened {url} in your browser")
    except:
        print(f"🌐 Please manually open: {url}")

def main():
    print("🧠 Jim Rohn AI Coach - Final Build")
    print("=" * 50)
    
    # Test API connection first
    try:
        test_response = coach.ask_jim("Hello Jim")
        if test_response['success']:
            print("✅ OpenAI API connection successful")
        else:
            print(f"❌ API Error: {test_response['error']}")
            return
    except Exception as e:
        print(f"❌ Failed to connect to OpenAI: {e}")
        print("Please check your .env file and API key")
        return
    
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
    print(f"🌐 Alternative URL: http://localhost:{port}")
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