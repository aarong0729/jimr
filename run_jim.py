#!/usr/bin/env python3

import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import subprocess
import sys

load_dotenv()

def test_api_connection():
    """Test if we can connect to OpenAI"""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Say 'Hello' as Jim Rohn would"}],
            temperature=0.7,
            max_tokens=50
        )
        
        print("✅ API Connection successful!")
        print(f"Test response: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ API Connection failed: {e}")
        return False

def create_simple_server():
    """Create a simple server file that should work on Mac"""
    server_code = '''#!/usr/bin/env python3

import http.server
import socketserver
import json
import urllib.parse
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class JimRohnHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            with open('index.html', 'r') as f:
                content = f.read()
            
            self.wfile.write(content.encode())
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path == '/ask':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                question = data.get('question', '')
                
                if not question:
                    response = {"error": "No question provided"}
                else:
                    # Call OpenAI
                    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    
                    # Load Jim Rohn prompt
                    try:
                        with open('System prompt.txt', 'r') as f:
                            prompt = f.read()
                    except:
                        prompt = "You are Jim Rohn, the legendary personal development speaker."
                    
                    api_response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": question}
                        ],
                        temperature=0.7
                    )
                    
                    response = {
                        "success": True,
                        "response": api_response.choices[0].message.content
                    }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                error_response = {"error": str(e)}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    PORT = 8000
    print(f"🧠 Jim Rohn AI Coach starting on port {PORT}")
    print(f"🌐 Open: http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    
    with socketserver.TCPServer(("", PORT), JimRohnHandler) as httpd:
        httpd.serve_forever()
'''
    
    with open('/Users/goodin/Desktop/jim/simple_server.py', 'w') as f:
        f.write(server_code)
    
    print("✅ Created simple_server.py")

def main():
    print("🧠 Jim Rohn AI Coach - Mac Troubleshoot")
    print("=" * 50)
    
    # Check if files exist
    required_files = ['.env', 'System prompt.txt', 'index.html']
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ Found: {file}")
        else:
            print(f"❌ Missing: {file}")
    
    # Test API
    if not test_api_connection():
        print("\n❌ API connection failed. Check your .env file.")
        return
    
    # Create simple server
    create_simple_server()
    
    print("\n🚀 Try running the simple server:")
    print("python3 simple_server.py")
    print("\nThen open: http://localhost:8000")
    
    # Ask user if they want to start it
    try:
        start = input("\nStart the server now? (y/n): ").lower().strip()
        if start == 'y':
            print("Starting server...")
            subprocess.run([sys.executable, 'simple_server.py'])
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()