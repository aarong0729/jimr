#!/usr/bin/env python3

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
