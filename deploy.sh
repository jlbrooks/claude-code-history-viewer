#!/bin/bash

# Deploy script for Claude Logs to fly.io

set -e

echo "🚀 Deploying Claude Logs to fly.io"

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl is not installed. Please install it first:"
    echo "   curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if user is logged in to fly.io
if ! flyctl auth whoami &> /dev/null; then
    echo "🔐 Please log in to fly.io first:"
    echo "   flyctl auth login"
    exit 1
fi

echo "📋 Setting up the application..."

# Create the app if it doesn't exist
if ! flyctl apps list | grep -q "claude-logs"; then
    echo "🔧 Creating new fly.io app..."
    flyctl apps create claude-logs
fi

# Set secrets
echo "🔑 Setting up secrets..."

# Generate SECRET_KEY if not provided
if [ -z "$SECRET_KEY" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi

# Check for required Supabase environment variables
if [ -z "$SUPABASE_URL" ]; then
    echo "❗ SUPABASE_URL environment variable is required"
    echo "   Set it with: export SUPABASE_URL=your-supabase-project-url"
    exit 1
fi

if [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "❗ SUPABASE_SERVICE_KEY environment variable is required"
    echo "   Set it with: export SUPABASE_SERVICE_KEY=your-supabase-service-key"
    exit 1
fi

# Set all secrets
flyctl secrets set \
    SECRET_KEY="$SECRET_KEY" \
    SUPABASE_URL="$SUPABASE_URL" \
    SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY"

echo "📦 Deploying application..."
flyctl deploy

echo "🌐 Opening application..."
flyctl open

echo "✅ Deployment complete!"
echo ""
echo "📊 Useful commands:"
echo "   flyctl logs          - View application logs"
echo "   flyctl ssh console   - SSH into the application"
echo "   flyctl status        - Check application status"
echo "   flyctl scale count 1 - Scale to 1 instance"
echo ""
echo "🌍 Your app is available at: https://claude-logs.fly.dev"