#!/bin/bash
set -e

echo "📦 Installing Python 3.11..."
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev

echo "🔧 Creating virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build complete!"
