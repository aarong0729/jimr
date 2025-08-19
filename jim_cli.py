#!/usr/bin/env python3

import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

class JimRohnCoach:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.conversations = []
        
        # Load the system prompt
        try:
            with open('System prompt.txt', 'r') as f:
                self.system_prompt = f.read()
            print("✅ Loaded your custom Jim Rohn system prompt")
        except FileNotFoundError:
            self.system_prompt = """You are Jim Rohn, the legendary personal development speaker. 
            Respond with wisdom, warmth, and practical advice in your distinctive style."""
            print("⚠️  Using basic prompt (System prompt.txt not found)")
    
    def ask_jim(self, question: str) -> str:
        """Get Jim's response to a question."""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            jim_response = response.choices[0].message.content
            
            # Store conversation
            conversation = {
                "user": question,
                "jim": jim_response,
                "timestamp": datetime.now().isoformat()
            }
            self.conversations.append(conversation)
            
            return jim_response
            
        except Exception as e:
            return f"I'm having some technical difficulties right now, my friend. Error: {e}"
    
    def save_conversation_history(self):
        """Save conversations to a JSON file"""
        if self.conversations:
            with open('jim_conversation_history.json', 'w') as f:
                json.dump(self.conversations, f, indent=2)
            print(f"\n💾 Saved {len(self.conversations)} conversations to jim_conversation_history.json")

def main():
    # Header
    print("\n" + "="*80)
    print("🧠  JIM ROHN AI COACH - Command Line Interface")
    print("="*80)
    print('"Success is neither magical nor mysterious. Success is the natural consequence"')
    print('of consistently applying basic fundamentals." - Jim Rohn')
    print("="*80)
    
    # Initialize coach
    print("\n🚀 Initializing Jim Rohn AI Coach...")
    
    try:
        coach = JimRohnCoach()
        print("🔑 Connected to OpenAI")
        print("✅ System ready!")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        print("Please check your .env file and API key.")
        return
    
    print("\n💡 You can ask Jim about:")
    print("   • Personal development and growth")
    print("   • Goal setting and achievement") 
    print("   • Building discipline and habits")
    print("   • Success principles and philosophy")
    print("   • Overcoming challenges and obstacles")
    print("   • Life wisdom and guidance")
    
    print(f"\n📝 Type your questions below (or 'quit' to exit)")
    print("-" * 80)
    
    conversation_count = 0
    
    try:
        while True:
            # Get user input
            print(f"\n[Question #{conversation_count + 1}]")
            question = input("You: ").strip()
            
            # Check for exit commands
            if question.lower() in ['quit', 'exit', 'q', 'bye']:
                print("\nJim Rohn: Keep growing and keep pursuing your dreams, my friend!")
                print("Remember: 'Don't wish it was easier. Wish you were better.'")
                print("\n👋 Until next time!")
                break
            
            # Skip empty questions
            if not question:
                continue
            
            # Get Jim's response
            print(f"\nJim Rohn: ", end="", flush=True)
            response = coach.ask_jim(question)
            print(response)
            
            conversation_count += 1
            
            # Show conversation count
            print(f"\n{'='*20} Conversation #{conversation_count} Complete {'='*20}")
    
    except KeyboardInterrupt:
        print(f"\n\nJim Rohn: Remember, success is a journey, not a destination.")
        print("Keep moving forward, one step at a time!")
        
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
    
    finally:
        # Save conversation history
        coach.save_conversation_history()
        print(f"\n🎯 Total conversations: {len(coach.conversations)}")
        print("Thank you for spending time with Jim Rohn's wisdom!")

if __name__ == "__main__":
    main()