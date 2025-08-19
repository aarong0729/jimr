#!/usr/bin/env python3

import os
import json
from datetime import datetime
from typing import Dict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class SimpleJimRohnCoach:
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
    
    def ask_jim(self, question: str) -> str:
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
            self.conversations.append({
                "user": question,
                "jim": jim_response,
                "timestamp": datetime.now().isoformat()
            })
            
            return jim_response
            
        except Exception as e:
            return f"I'm having some technical difficulties right now. Error: {e}"

def main():
    print("🧠 Jim Rohn AI Coach - Simple Test Version")
    print("=" * 50)
    
    coach = SimpleJimRohnCoach()
    
    print("Ask Jim Rohn anything about personal development, success, or life wisdom.")
    print("Type 'quit' to exit.\n")
    
    while True:
        question = input("You: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            print("Keep growing! Until next time. - Jim")
            break
            
        if not question:
            continue
            
        print("\nJim Rohn:", end=" ")
        response = coach.ask_jim(question)
        print(response)
        print("\n" + "-" * 50 + "\n")

if __name__ == "__main__":
    main()