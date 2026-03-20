#!/bin/bash

echo ""
echo "========================================"
echo "  DocFlow Setup - macOS/Linux"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8+ from https://www.python.org/"
    exit 1
fi

# Check Node
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed"
    echo "Please install Node.js 16+ from https://nodejs.org/"
    exit 1
fi

echo "Python and Node.js are installed!"
echo ""

# Setup Backend
echo "Setting up Backend..."
cd backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
fi

source venv/bin/activate
pip install -r requirements.txt -q
echo "Backend dependencies installed"

# Create .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "Please enter your API keys:"
    read -p "Enter ANTHROPIC_API_KEY: " ANTHROPIC_KEY
    read -p "Enter MERCURY_API_KEY: " MERCURY_KEY
    
    cat > .env << EOF
# API Keys
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
MERCURY_API_KEY=${MERCURY_KEY}
MERCURY_BASE_URL=https://api.inceptionlabs.ai/v1

# Database
DATABASE_URL=sqlite:///./docflow.db

# Application Settings
UPLOAD_FOLDER=./documents
MAX_RETRIES=3
CONFIDENCE_THRESHOLD=0.75
EOF
    echo ".env file created"
else
    echo ".env file already exists"
fi

cd ..

# Setup Frontend
echo ""
echo "Setting up Frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    npm install -q
    echo "Frontend dependencies installed"
else
    echo "node_modules already exists"
fi

cd ..

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "To start the application:"
echo ""
echo "1. Backend (from docflow/backend):"
echo "   source venv/bin/activate"
echo "   python -m uvicorn main:app --reload --port 8000"
echo ""
echo "2. Frontend (from docflow/frontend, in another terminal):"
echo "   npm run dev"
echo ""
echo "Backend API:        http://localhost:8000"
echo "Frontend:          http://localhost:5173"
echo "API Documentation: http://localhost:8000/docs"
echo ""
echo "First-time setup: Add your API keys in the Settings panel (⚙️)"
echo ""
