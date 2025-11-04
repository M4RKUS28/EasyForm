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

# Parse command line arguments
FORCE_INSTALL=false
RELOAD=true

if [ $# -gt 0 ]; then
    for arg in "$@"; do
        case "${arg}" in
            u|update)
                FORCE_INSTALL=true
                ;;
            s|static)
                RELOAD=false
                ;;
            h|help|--help|-h)
                echo "Usage: ./run.sh [u|update] [s|static]"
                echo "  u|update  Force re-install of requirements"
                echo "  s|static  Run without uvicorn reload"
                exit 0
                ;;
            *)
                echo "Unknown option: ${arg}"
                echo "Use './run.sh help' for usage information."
                exit 1
                ;;
        esac
    done
fi

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

# Install requirements if venv was just created or update requested
if [ "${VENV_CREATED}" = true ] || [ "${FORCE_INSTALL}" = true ]; then
    echo "Installing requirements..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Failed to install requirements."
        exit 1
    fi
    echo "Requirements installed successfully."
else
    echo "Skipping requirements installation (use './run.sh u' to force)."
fi

# Get port from environment variable or use default
PORT=${PORT:-8080}

if [ "${RELOAD}" = true ]; then
    echo "Starting server on port ${PORT} with reload enabled..."
else
    echo "Starting server on port ${PORT} with reload disabled (static mode)..."
fi

if [ "${RELOAD}" = true ]; then
    RELOAD_VALUE="true"
else
    RELOAD_VALUE="false"
fi

# Run uvicorn server
EASYFORM_RELOAD_FLAG=${RELOAD_VALUE} python -c "
import uvicorn
import os

port = int(os.getenv('PORT', $PORT))
reload = os.getenv('EASYFORM_RELOAD_FLAG', 'true').lower() == 'true'
uvicorn.run('src.main:app', host='0.0.0.0', port=port, reload=reload)
"
