#!/usr/bin/env python3

import re

def clean_text_for_speech(text: str) -> str:
    """Clean text for better speech synthesis by removing markdown and formatting."""
    
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

def test_cleaning():
    test_cases = [
        "**Give more than you take**: This is the foundation...",
        "*Success* is nothing more than a few simple disciplines, practiced every day.",
        "My mentor, Mr. Shoaff, used to say: 'Don't wish it was easier. Wish you were better.'",
        "Here are **five key principles**: \n• First principle\n• Second principle",
        "Work harder on yourself than you do on your job & you'll attract more success.",
    ]
    
    print("🧹 Text Cleaning Test")
    print("=" * 60)
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n📝 Test {i}:")
        print(f"Before: {test_text}")
        cleaned = clean_text_for_speech(test_text)
        print(f"After:  {cleaned}")

if __name__ == "__main__":
    test_cleaning()