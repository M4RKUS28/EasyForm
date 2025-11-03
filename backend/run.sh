#!/bin/bash

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    CYGWIN*|MINGW*|MSYS*|MINGW32*|MINGW64*)     MACHINE=Windows;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

echo "Detected OS: ${MACHINE}"

# Check if venv folder exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating venv..."
    python -m venv venv
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment."
        exit 1
    fi
    echo "Virtual environment created successfully."
    VENV_CREATED=true
else
    echo "Virtual environment already exists."
    VENV_CREATED=false
fi

# Activate virtual environment based on OS
echo "Activating virtual environment..."
if [ "${MACHINE}" = "Windows" ]; then
    # Windows (Git Bash, MSYS, MinGW)
    if ! source venv/Scripts/activate 2>/dev/null; then
        echo "Failed to activate virtual environment on Windows."
        exit 1
    fi
else
    # Linux and Mac
    if ! source venv/bin/activate 2>/dev/null; then
        echo "Failed to activate virtual environment on ${MACHINE}."
        exit 1
    fi
fi

echo "Virtual environment activated."

# Install requirements if venv was just created
if [ "${VENV_CREATED}" = true ]; then
    echo "Installing requirements..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Failed to install requirements."
        exit 1
    fi
    echo "Requirements installed successfully."
fi

# Get port from environment variable or use default
PORT=${PORT:-8080}

echo "Starting server on port ${PORT}..."

# Run uvicorn server
python -c "
import uvicorn
import os

port = int(os.getenv('PORT', $PORT))
uvicorn.run('src.main:app', host='0.0.0.0', port=port, reload=True)
"
