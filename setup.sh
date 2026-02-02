#!/bin/bash
#
# Setup script for Vertex AI Reasoning Proxy
#

set -e

echo "=== Vertex AI Reasoning Proxy Setup ==="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✓ Found Python $PYTHON_VERSION"

# Check gcloud
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud is not installed"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
echo "✓ Found gcloud"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip > /dev/null
pip install -r requirements.txt > /dev/null

echo ""
echo "✓ Dependencies installed"

# Configure environment
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file..."
    read -p "Enter your GCP Project ID: " PROJECT_ID
    read -p "Enter Vertex AI region [us-west1]: " REGION
    REGION=${REGION:-us-west1}

    cat > .env <<EOF
# Vertex AI Configuration
VERTEX_AI_PROJECT=$PROJECT_ID
VERTEX_AI_REGION=$REGION

# Proxy Configuration
PROXY_HOST=127.0.0.1
PROXY_PORT=8000
EOF
    echo "✓ Created .env file"
else
    echo "✓ .env file already exists"
fi

# Test gcloud auth
echo ""
echo "Testing gcloud authentication..."
if gcloud auth application-default print-access-token > /dev/null 2>&1; then
    echo "✓ gcloud authentication working"
else
    echo "⚠ gcloud not authenticated"
    echo "Run: gcloud auth application-default login"
fi

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "To start the proxy:"
echo "  source venv/bin/activate"
echo "  python proxy.py"
echo ""
echo "To test:"
echo "  ./test_proxy.sh"
echo ""
