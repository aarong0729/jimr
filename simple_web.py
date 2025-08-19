#!/usr/bin/env python3

import os
import json
from datetime import datetime
from typing import Dict
from openai import OpenAI
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

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

HTML_PAGE = '''<!DOCTYPE html>
<html>
<head>
    <title>🧠 Jim Rohn AI Coach</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif;
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
            background: #f5f5f5;
        }
        .container {
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { 
            color: #333; 
            text-align: center; 
        }
        .chat-area {
            height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 15px;
            margin: 20px 0;
            background: #f9f9f9;
        }
        .message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 5px;
        }
        .user { background: #e3f2fd; }
        .jim { background: #f3e5f5; margin-top: 5px; }
        .input-area {
            display: flex;
            gap: 10px;
        }
        input[type="text"] {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        button {
            padding: 10px 20px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover { background: #45a049; }
        .stats { text-align: center; margin-top: 15px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 Jim Rohn AI Coach</h1>
        <div class="chat-area" id="chat">
            <div class="message jim"><strong>Jim Rohn:</strong> Welcome! I'm here to help with your personal development. What's on your mind?</div>
        </div>
        <div class="input-area">
            <input type="text" id="question" placeholder="Ask Jim about success, goals, discipline, motivation..." maxlength="300">
            <button onclick="askJim()">Ask Jim</button>
        </div>
        <div class="stats">Conversations: <span id="count">0</span></div>
    </div>

    <script>
        let conversationCount = 0;
        
        function askJim() {
            const question = document.getElementById('question').value.trim();
            if (!question) return;
            
            // Add user message
            const chat = document.getElementById('chat');
            const userMsg = document.createElement('div');
            userMsg.className = 'message user';
            userMsg.innerHTML = '<strong>You:</strong> ' + question;
            chat.appendChild(userMsg);
            
            // Show loading
            const loadingMsg = document.createElement('div');
            loadingMsg.className = 'message jim';
            loadingMsg.innerHTML = '<strong>Jim Rohn:</strong> <em>Thinking...</em>';
            chat.appendChild(loadingMsg);
            
            // Clear input
            document.getElementById('question').value = '';
            chat.scrollTop = chat.scrollHeight;
            
            // Send request
            fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'question=' + encodeURIComponent(question)
            })
            .then(response => response.text())
            .then(response => {
                chat.removeChild(loadingMsg);
                const jimMsg = document.createElement('div');
                jimMsg.className = 'message jim';
                jimMsg.innerHTML = '<strong>Jim Rohn:</strong> ' + response;
                chat.appendChild(jimMsg);
                
                conversationCount++;
                document.getElementById('count').textContent = conversationCount;
                chat.scrollTop = chat.scrollHeight;
            })
            .catch(error => {
                chat.removeChild(loadingMsg);
                const errorMsg = document.createElement('div');
                errorMsg.className = 'message jim';
                errorMsg.innerHTML = '<strong>Jim Rohn:</strong> I apologize, but I had a technical difficulty. Please try again.';
                chat.appendChild(errorMsg);
            });
        }
        
        document.getElementById('question').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') askJim();
        });
    </script>
</body>
</html>'''

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/ask':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(post_data)
            question = params.get('question', [''])[0]
            
            if question:
                result = coach.ask_jim(question)
                response = result['response']
            else:
                response = "Please ask me something!"
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

if __name__ == '__main__':
    port = 8080
    print(f"🧠 Jim Rohn AI Coach starting...")
    print(f"📚 System ready with your custom prompt")
    print(f"🌐 Web interface: http://localhost:{port}")
    print(f"🌐 Also try: http://127.0.0.1:{port}")
    print("=" * 50)
    
    try:
        server = HTTPServer(('127.0.0.1', port), RequestHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Goodbye! Keep growing!")
        server.shutdown()