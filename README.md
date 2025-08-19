# Jim Rohn AI Coach

An intelligent personal coaching system that channels the wisdom of Jim Rohn using RAG (Retrieval-Augmented Generation), memory, and voice synthesis.

## Features

🧠 **Intelligent RAG System**
- Processes your Jim Rohn knowledge base intelligently
- Retrieves most relevant content for each situation
- Supports books, transcripts, and seminar materials

🎭 **Multi-Layer Memory**
- Session Memory: Remembers current conversation
- Long-term Memory: Vector store of all past conversations  
- User Profile: Builds understanding of your patterns and growth areas

🔍 **Pattern Recognition**
- Identifies recurring themes in your life
- Tracks your growth areas over time
- Provides increasingly personalized advice

🎯 **Context-Aware Responses**
- Jim references your past conversations
- Acknowledges your behavioral patterns
- Challenges you based on your specific growth needs

🎤 **Voice Integration**
- ElevenLabs voice synthesis (Jim's voice)
- Audio responses alongside text

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Setup**
   ```bash
   python setup.py
   ```

3. **Configure API Keys**
   - Copy `.env.template` to `.env`
   - Add your OpenAI API key
   - Add your ElevenLabs API key and Jim Rohn voice ID

4. **Add Jim Rohn Materials**
   - Place your knowledge base files in `./jim_rohn_materials/`
   - Organize into subdirectories: `books/`, `transcripts/`, `seminars/`
   - Supported formats: `.txt` files

5. **Launch the Interface**
   ```bash
   python jim_rohn_system.py
   ```

## Directory Structure

```
jim/
├── jim_rohn_system.py          # Main coaching system
├── setup.py                    # Setup script
├── requirements.txt            # Python dependencies
├── jim_rohn_prompt.txt        # Jim Rohn personality prompt
├── .env                       # API keys (create from template)
├── jim_rohn_materials/        # Your knowledge base
│   ├── books/
│   ├── transcripts/
│   └── seminars/
├── jim_knowledge_db/          # Vector database (auto-created)
├── conversation_db/           # Conversation memory (auto-created)
└── my_profile.json           # Your user profile (auto-created)
```

## How It Works

1. **Knowledge Processing**: Your Jim Rohn materials are chunked and stored in a vector database
2. **Contextual Retrieval**: For each question, relevant Jim Rohn content and past conversations are retrieved
3. **Personalized Response**: AI generates responses using Jim's personality, relevant materials, and your personal patterns
4. **Memory Building**: Each conversation is analyzed and stored to build your personal profile
5. **Voice Synthesis**: Response is converted to Jim's voice using ElevenLabs

## Configuration

### Environment Variables
- `OPENAI_API_KEY`: Your OpenAI API key
- `ELEVENLABS_API_KEY`: Your ElevenLabs API key  
- `JIM_ROHN_VOICE_ID`: Your cloned Jim Rohn voice ID from ElevenLabs

### Knowledge Base Format
Place `.txt` files in the appropriate subdirectories:
- Books: Full text of Jim Rohn books
- Transcripts: Speech and seminar transcripts
- Seminars: Notes and content from seminars

## User Profile

The system builds a profile of you including:
- Recurring themes in your conversations
- Growth areas you need to work on
- Strengths you display
- Key challenges you face
- Conversation history and patterns

This enables increasingly personalized coaching over time.

## Web Interface

The Gradio interface provides:
- Text input for your situations/questions
- Jim's text response with full context
- Audio playback of Jim's voice
- Sources referenced from the knowledge base
- Your personal patterns and insights
- Session statistics

## Technical Architecture

- **RAG System**: LangChain + ChromaDB for intelligent content retrieval
- **Memory**: Multi-layered memory system with vector storage
- **AI**: OpenAI GPT-4 for response generation
- **Voice**: ElevenLabs for voice synthesis
- **Interface**: Gradio for web UI
- **Storage**: JSON for user profiles, ChromaDB for vectors

## Next Steps

1. Add your Jim Rohn knowledge base materials
2. Configure your API keys
3. Start having conversations with your AI Jim Rohn coach
4. Watch as the system learns your patterns and provides increasingly personalized guidance

The more you use it, the better it gets at understanding your specific challenges and growth areas!