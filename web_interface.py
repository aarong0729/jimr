#!/usr/bin/env python3

import os
import json
from datetime import datetime
from typing import Dict
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify

load_dotenv()

class JimRohnCoach:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.conversations = []
        
        # Load the prompt
        try:
            with open('System prompt.txt', 'r') as f:
                self.base_prompt = f.read()
        except FileNotFoundError:
            self.base_prompt = """You are Jim Rohn, the legendary personal development speaker. 
            Respond with wisdom, warmth, and practical advice in your distinctive style."""
    
    def ask_jim(self, question: str) -> Dict:
        """Get Jim's response to a question."""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.base_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.7
            )
            
            jim_response = response.choices[0].message.content
            
            # Store conversation
            conversation = {
                "user": question,
                "jim": jim_response,
                "timestamp": datetime.now().isoformat()
            }
            self.conversations.append(conversation)
            
            return {
                "success": True,
                "response": jim_response,
                "conversation_count": len(self.conversations)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": f"I'm having some technical difficulties right now. Error: {e}"
            }

# Initialize the coach
coach = JimRohnCoach()

# Flask app
app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🧠 Jim Rohn AI Coach</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        h1 { 
            color: #333; 
            text-align: center; 
            margin-bottom: 10px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-style: italic;
        }
        .chat-container {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 10px;
            background: #f9f9f9;
        }
        .message {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 8px;
        }
        .user-message {
            background: #e3f2fd;
            border-left: 4px solid #2196F3;
        }
        .jim-message {
            background: #f3e5f5;
            border-left: 4px solid #9c27b0;
            margin-top: 10px;
        }
        .input-container {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        #question {
            flex: 1;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
        }
        #askBtn {
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
        }
        #askBtn:hover {
            background: #5a6fd8;
        }
        #askBtn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .loading {
            text-align: center;
            color: #666;
            font-style: italic;
        }
        .stats {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 Jim Rohn AI Coach</h1>
        <p class="subtitle">"Success is neither magical nor mysterious. Success is the natural consequence of consistently applying basic fundamentals."</p>
        
        <div class="chat-container" id="chatContainer">
            <div class="message jim-message">
                <strong>Jim Rohn:</strong> Welcome, my friend! I'm here to help you on your journey of personal development. What's on your mind today? What challenge are you facing, or what wisdom are you seeking?
            </div>
        </div>
        
        <div class="input-container">
            <input type="text" id="question" placeholder="Ask Jim about life, success, goals, discipline, or any challenge you're facing..." maxlength="500">
            <button id="askBtn" onclick="askJim()">Ask Jim</button>
        </div>
        
        <div class="stats" id="stats">
            Ready to help you grow • Conversations: 0
        </div>
    </div>

    <script>
        let conversationCount = 0;
        
        function askJim() {
            const question = document.getElementById('question').value.trim();
            if (!question) return;
            
            const chatContainer = document.getElementById('chatContainer');
            const askBtn = document.getElementById('askBtn');
            
            // Add user message
            const userMessage = document.createElement('div');
            userMessage.className = 'message user-message';
            userMessage.innerHTML = `<strong>You:</strong> ${question}`;
            chatContainer.appendChild(userMessage);
            
            // Add loading message
            const loadingMessage = document.createElement('div');
            loadingMessage.className = 'message loading';
            loadingMessage.innerHTML = 'Jim is thinking...';
            chatContainer.appendChild(loadingMessage);
            
            // Clear input and disable button
            document.getElementById('question').value = '';
            askBtn.disabled = true;
            askBtn.textContent = 'Thinking...';
            
            // Scroll to bottom
            chatContainer.scrollTop = chatContainer.scrollHeight;
            
            // Send request
            fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({question: question})
            })
            .then(response => response.json())
            .then(data => {
                // Remove loading message
                chatContainer.removeChild(loadingMessage);
                
                // Add Jim's response
                const jimMessage = document.createElement('div');
                jimMessage.className = 'message jim-message';
                jimMessage.innerHTML = `<strong>Jim Rohn:</strong> ${data.response}`;
                chatContainer.appendChild(jimMessage);
                
                // Update conversation count
                conversationCount = data.conversation_count || conversationCount + 1;
                document.getElementById('stats').textContent = `Ready to help you grow • Conversations: ${conversationCount}`;
                
                // Re-enable button
                askBtn.disabled = false;
                askBtn.textContent = 'Ask Jim';
                
                // Scroll to bottom
                chatContainer.scrollTop = chatContainer.scrollHeight;
            })
            .catch(error => {
                console.error('Error:', error);
                chatContainer.removeChild(loadingMessage);
                
                const errorMessage = document.createElement('div');
                errorMessage.className = 'message jim-message';
                errorMessage.innerHTML = `<strong>Jim Rohn:</strong> I'm having some technical difficulties right now. Please try again in a moment.`;
                chatContainer.appendChild(errorMessage);
                
                askBtn.disabled = false;
                askBtn.textContent = 'Ask Jim';
            });
        }
        
        // Allow Enter key to send message
        document.getElementById('question').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                askJim();
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ask', methods=['POST'])
def ask_jim():
    data = request.json
    question = data.get('question', '')
    
    if not question:
        return jsonify({'success': False, 'response': 'Please ask me something!'})
    
    result = coach.ask_jim(question)
    return jsonify(result)

if __name__ == '__main__':
    print("🧠 Starting Jim Rohn AI Coach...")
    print("📚 System ready with your custom prompt")
    print("🌐 Opening web interface at: http://localhost:8080")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=8080, debug=False)