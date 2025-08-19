#!/usr/bin/env python3

import os
from dotenv import load_dotenv

load_dotenv()

def test_elevenlabs():
    print("🎤 Testing ElevenLabs Integration")
    print("=" * 40)
    
    # Check API key
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("JIM_ROHN_VOICE_ID")
    
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found in .env file")
        return False
        
    if not voice_id:
        print("❌ JIM_ROHN_VOICE_ID not found in .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:15]}...")
    print(f"✅ Voice ID found: {voice_id}")
    
    # Test ElevenLabs import and connection
    try:
        from elevenlabs import ElevenLabs
        print("✅ ElevenLabs library imported successfully")
        
        client = ElevenLabs(api_key=api_key)
        print("✅ ElevenLabs client created")
        
        # Test voice generation
        print("\n🎵 Testing voice generation...")
        test_text = "Hello, my friend. This is a test of Jim Rohn's voice."
        
        # Try the correct API method
        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=test_text,
            model_id="eleven_monolingual_v1"
        )
        
        # Convert generator to bytes
        audio_data = b"".join(audio_generator)
        
        print(f"✅ Voice generation successful! Audio data size: {len(audio_data)} bytes")
        
        # Save test audio file
        with open("test_voice.mp3", "wb") as f:
            f.write(audio_data)
        
        print("✅ Test audio saved as 'test_voice.mp3'")
        print("\n🎯 ElevenLabs is working correctly!")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import ElevenLabs: {e}")
        print("Run: pip3 install elevenlabs")
        return False
        
    except Exception as e:
        print(f"❌ ElevenLabs error: {e}")
        print(f"Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    test_elevenlabs()