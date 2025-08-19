#!/bin/bash

echo "🧠 Starting Jim Rohn AI Coach - Multi-User Version"
echo "================================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "📋 Please copy .env.example to .env and fill in your API keys"
    echo ""
    echo "cp .env.example .env"
    echo "nano .env"
    exit 1
fi

# Check if requirements are installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing requirements..."
    pip3 install -r requirements_production.txt
fi

echo "✅ Starting server..."
echo "🌐 Multi-user interface: http://localhost:5001"
echo "🔧 Admin dashboard: http://localhost:5001/admin"
echo "🛑 To stop: Press Ctrl+C"
echo ""

python3 jim_server_multiuser.py