#!/usr/bin/env python3

import os
import json
from datetime import datetime
from typing import Dict

from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify
import base64
import webbrowser
import threading
import time

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
    
    def ask_jim(self, question: str, image_data: str = None) -> Dict:
        """Get Jim's response to a question, optionally with an image."""
        try:
            messages = [
                {"role": "system", "content": self.base_prompt}
            ]
            
            # Handle text with optional image
            if image_data:
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Please analyze this image and provide guidance. {question}" if question else "Please analyze this image and provide guidance."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                })
            else:
                messages.append({"role": "user", "content": question})
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # Use gpt-4o for vision capabilities
                messages=messages,
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
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        h1 {
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #666;
            font-style: italic;
            font-size: 1.1em;
            max-width: 600px;
            margin: 0 auto;
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
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border-left: 4px solid #2196F3;
            margin-left: 40px;
        }

        .jim-message {
            background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
            border-left: 4px solid #9c27b0;
            margin-right: 40px;
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
            flex-direction: column;
            gap: 15px;
            margin-bottom: 20px;
        }

        .image-upload-area {
            border: 2px dashed #dee2e6;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f8f9fa;
            position: relative;
        }

        .image-upload-area:hover {
            border-color: #667eea;
            background: #f0f4ff;
        }

        .image-upload-area.dragover {
            border-color: #667eea;
            background: #e3f2fd;
            transform: scale(1.02);
        }

        .upload-text {
            color: #666;
        }

        .upload-text span {
            display: block;
            font-size: 16px;
            margin-bottom: 5px;
        }

        .upload-text small {
            font-size: 12px;
            color: #999;
        }

        .uploaded-image {
            position: relative;
            display: inline-block;
        }

        .uploaded-image img {
            max-width: 200px;
            max-height: 200px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        .remove-image {
            position: absolute;
            top: -8px;
            right: -8px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            cursor: pointer;
            font-size: 16px;
            line-height: 1;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .question-row {
            display: flex;
            gap: 15px;
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
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .ask-button {
            padding: 15px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: transform 0.2s ease;
            min-width: 120px;
        }

        .ask-button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
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

        .loading {
            display: inline-block;
            animation: pulse 1.5s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #28a745;
            border-radius: 50%;
            margin-right: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Jim Rohn AI Coach</h1>
            <p class="subtitle">"Success is neither magical nor mysterious. Success is the natural consequence of consistently applying basic fundamentals."</p>
        </div>

        <div class="chat-container" id="chatContainer">
            <div class="message jim-message">
                <div class="message-header">Jim Rohn:</div>
                <div class="message-content">Welcome, my friend! I'm here to share wisdom about success, personal development, and achieving your goals. What's on your mind today? What challenge are you facing, or what guidance are you seeking?</div>
            </div>
        </div>

        <div class="input-section">
            <div class="image-upload-area" id="imageUploadArea">
                <div class="upload-text">
                    <span>📎 Drop an image here or click to upload</span>
                    <small>JPG, PNG, GIF up to 10MB</small>
                </div>
                <input type="file" id="imageInput" accept="image/*" style="display: none;">
                <div class="uploaded-image" id="uploadedImageContainer" style="display: none;">
                    <img id="uploadedImage" src="" alt="Uploaded image">
                    <button class="remove-image" onclick="removeImage()">×</button>
                </div>
            </div>
            <div class="question-row">
                <textarea id="questionInput" class="question-input" placeholder="Ask Jim about success, goals, discipline, motivation, relationships, or any life challenge... You can also upload an image for analysis!" rows="3"></textarea>
                <button id="askButton" class="ask-button" onclick="askJim()">Ask Jim</button>
            </div>
        </div>

        <div class="stats">
            <span class="status-indicator"></span>
            <span id="statusText">Connected & Ready</span> • Conversations: <span id="conversationCount">0</span>
        </div>
    </div>

    <script>
        let conversationCount = 0;
        let currentImageData = null;

        async function askJim() {
            const question = document.getElementById('questionInput').value.trim();
            const askButton = document.getElementById('askButton');
            const chatContainer = document.getElementById('chatContainer');
            const statusText = document.getElementById('statusText');

            if (!question && !currentImageData) {
                alert('Please ask Jim a question or upload an image.');
                return;
            }

            // Add user message
            let userMessage = question || 'Shared an image for analysis';
            if (question && currentImageData) {
                userMessage = question + ' 📷';
            } else if (currentImageData) {
                userMessage = '📷 Shared an image for analysis';
            }
            addMessage('You', userMessage, 'user-message');
            
            // Clear input and disable button
            document.getElementById('questionInput').value = '';
            askButton.disabled = true;
            askButton.innerHTML = '<span class="loading">Jim is thinking...</span>';
            statusText.textContent = 'Jim is pondering your question';

            // Add loading message
            const loadingMessage = addMessage('Jim Rohn', 'Let me think about that...', 'jim-message');

            try {
                // Create request data
                const requestData = {
                    question: question
                };
                
                if (currentImageData) {
                    requestData.image = currentImageData;
                }

                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestData)
                });

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const data = await response.json();

                // Remove loading message
                chatContainer.removeChild(loadingMessage);

                if (data.success) {
                    // Add Jim's response
                    addMessage('Jim Rohn', data.response, 'jim-message');
                    
                    // Update conversation count
                    conversationCount = data.conversation_count;
                    document.getElementById('conversationCount').textContent = conversationCount;
                    statusText.textContent = 'Connected & Ready';
                    
                    // Clear the uploaded image after successful response
                    if (currentImageData) {
                        removeImage();
                    }
                } else {
                    // Add error message
                    addMessage('Jim Rohn', data.response, 'jim-message');
                    statusText.textContent = 'Technical difficulty - please try again';
                }

            } catch (error) {
                console.error('Error:', error);
                
                // Remove loading message
                chatContainer.removeChild(loadingMessage);
                
                // Add error message
                addMessage('Jim Rohn', 'I apologize, but I\'m having some technical difficulties right now. Please try again in a moment.', 'jim-message');
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

        // Auto-focus on input
        document.getElementById('questionInput').focus();

        // Image upload functionality
        function setupImageUpload() {
            const uploadArea = document.getElementById('imageUploadArea');
            const imageInput = document.getElementById('imageInput');
            const uploadedImageContainer = document.getElementById('uploadedImageContainer');
            const uploadedImage = document.getElementById('uploadedImage');
            const uploadText = uploadArea.querySelector('.upload-text');

            // Click to upload
            uploadArea.addEventListener('click', () => {
                if (!currentImageData) {
                    imageInput.click();
                }
            });

            // File input change
            imageInput.addEventListener('change', handleImageSelect);

            // Drag and drop
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    handleImageFile(files[0]);
                }
            });
        }

        function handleImageSelect(e) {
            const file = e.target.files[0];
            if (file) {
                handleImageFile(file);
            }
        }

        function handleImageFile(file) {
            // Check file size (10MB limit)
            if (file.size > 10 * 1024 * 1024) {
                alert('File size must be less than 10MB');
                return;
            }

            // Check file type
            if (!file.type.startsWith('image/')) {
                alert('Please select an image file');
                return;
            }

            const reader = new FileReader();
            reader.onload = function(e) {
                currentImageData = e.target.result.split(',')[1]; // Remove data:image/jpeg;base64, prefix
                showUploadedImage(e.target.result);
            };
            reader.readAsDataURL(file);
        }

        function showUploadedImage(imageSrc) {
            const uploadArea = document.getElementById('imageUploadArea');
            const uploadedImageContainer = document.getElementById('uploadedImageContainer');
            const uploadedImage = document.getElementById('uploadedImage');
            const uploadText = uploadArea.querySelector('.upload-text');

            uploadedImage.src = imageSrc;
            uploadText.style.display = 'none';
            uploadedImageContainer.style.display = 'block';
            uploadArea.style.border = '2px solid #28a745';
            uploadArea.style.background = '#f0fff0';
        }

        function removeImage() {
            currentImageData = null;
            const uploadArea = document.getElementById('imageUploadArea');
            const uploadedImageContainer = document.getElementById('uploadedImageContainer');
            const uploadText = uploadArea.querySelector('.upload-text');
            const imageInput = document.getElementById('imageInput');

            uploadedImageContainer.style.display = 'none';
            uploadText.style.display = 'block';
            uploadArea.style.border = '2px dashed #dee2e6';
            uploadArea.style.background = '#f8f9fa';
            imageInput.value = '';
        }

        // Initialize image upload when page loads
        setupImageUpload();
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ask', methods=['POST'])
def ask_jim():
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
            question = data.get('question', '')
            image_data = data.get('image', None)
        else:
            # Handle form data (for file uploads)
            question = request.form.get('question', '')
            image_data = None
            
            # Check for uploaded file
            if 'image' in request.files:
                image_file = request.files['image']
                if image_file and image_file.filename:
                    # Convert uploaded image to base64
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        if not question and not image_data:
            return jsonify({'success': False, 'response': 'Please ask me something or upload an image!'})
        
        result = coach.ask_jim(question, image_data)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'success': False, 
            'response': f'Technical error: {str(e)}'
        })

def open_browser():
    """Open browser after a short delay to ensure server is ready"""
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:3000')

if __name__ == '__main__':
    print("🧠 Jim Rohn AI Coach - Full System")
    print("=" * 40)
    print("📚 Loading your custom Jim Rohn prompt...")
    print("🔑 Using API key from .env file")
    
    # Check if running in production (Railway sets PORT env var)
    port = int(os.environ.get('PORT', 3000))
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    
    print(f"🌐 Starting web interface at: http://{host}:{port}")
    if host == '127.0.0.1':
        print("🌐 Alternative URL: http://localhost:3000")
        # Start browser in background thread for local development
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
    
    print("=" * 40)
    
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Server error: {e}")
        print("Try a different port or check if another service is using the port")