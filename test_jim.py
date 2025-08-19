#!/usr/bin/env python3

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def test_jim_response():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Load the prompt
    try:
        with open('System prompt.txt', 'r') as f:
            base_prompt = f.read()
    except FileNotFoundError:
        base_prompt = """You are Jim Rohn, the legendary personal development speaker. 
        Respond with wisdom, warmth, and practical advice in your distinctive style."""
    
    # Test question
    question = "I'm struggling with motivation to work on my goals. What advice would you give me?"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": base_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.7
        )
        
        jim_response = response.choices[0].message.content
        
        print("🧠 Jim Rohn AI Coach Test")
        print("=" * 50)
        print(f"Question: {question}")
        print("\nJim's Response:")
        print("-" * 20)
        print(jim_response)
        print("\n✅ System is working!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_jim_response()