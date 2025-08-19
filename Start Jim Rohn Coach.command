#!/bin/bash

# Jim Rohn AI Coach - Double-click to start
echo "🧠 Starting Jim Rohn AI Coach..."
echo "=================================="

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Check if required files exist
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Please make sure your API keys are set up"
    read -p "Press enter to close..."
    exit 1
fi

if [ ! -f "jim_server_working.py" ]; then
    echo "❌ Error: jim_server_working.py not found"
    read -p "Press enter to close..."
    exit 1
fi

echo "✅ Files found, starting server..."
echo ""
echo "🌐 Your Jim Rohn AI Coach will open automatically"
echo "🛑 To stop: Close this window or press Ctrl+C"
echo ""
echo "=================================="

# Start the server
python3 jim_server_working.py