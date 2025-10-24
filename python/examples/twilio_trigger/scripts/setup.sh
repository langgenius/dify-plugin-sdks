#!/bin/bash

# Twilio Plugin Setup Script
# This script helps you set up and run the Twilio trigger plugin

set -e

echo "🚀 Twilio Plugin Setup"
echo "===================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Step 1: Check Python version
echo "📌 Step 1: Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"
echo ""

# Step 2: Install dependencies
echo "📌 Step 2: Installing dependencies..."
if pip3 install -r requirements.txt; then
    echo -e "${GREEN}✅ Dependencies installed successfully${NC}"
else
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi
echo ""

# Step 3: Check for .env file
echo "📌 Step 3: Checking environment configuration..."
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✅ .env file created${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Please edit .env and add your Twilio credentials:${NC}"
    echo "   - TWILIO_ACCOUNT_SID"
    echo "   - TWILIO_AUTH_TOKEN"
    echo ""
    echo "You can get these from: https://console.twilio.com"
    echo ""
    read -p "Press Enter after you've updated .env file..."
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi
echo ""

# Step 4: Validate .env file
echo "📌 Step 4: Validating environment variables..."
if grep -q "TWILIO_ACCOUNT_SID=AC" .env 2>/dev/null; then
    echo -e "${GREEN}✅ TWILIO_ACCOUNT_SID configured${NC}"
else
    echo -e "${YELLOW}⚠️  TWILIO_ACCOUNT_SID not configured in .env${NC}"
fi

if grep -q "TWILIO_AUTH_TOKEN=" .env 2>/dev/null && ! grep -q "TWILIO_AUTH_TOKEN=$" .env; then
    echo -e "${GREEN}✅ TWILIO_AUTH_TOKEN configured${NC}"
else
    echo -e "${YELLOW}⚠️  TWILIO_AUTH_TOKEN not configured in .env${NC}"
fi
echo ""

# Step 5: Summary
echo "===================="
echo "✨ Setup Complete!"
echo "===================="
echo ""
echo "Next steps:"
echo "1. Make sure your Twilio credentials are in .env"
echo "2. Run the plugin:"
echo "   ${GREEN}python3 main.py${NC}"
echo ""
echo "3. For local testing with ngrok:"
echo "   ${GREEN}ngrok http 5000${NC}"
echo ""
echo "4. See QUICKSTART.md for detailed instructions"
echo ""
