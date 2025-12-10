#!/bin/bash
# Proper Git-based deployment to Debian server
# Usage: ./deploy-git.sh

set -e  # Exit on error

SERVER="mirko@192.168.178.55"
PROJECT_DIR="/opt/trading/traderunner"
BRANCH="feature/v2-architecture"
SERVICE="trading-dashboard-v2"

echo "=========================================="
echo "Git-Based Deployment to Debian Server"
echo "=========================================="

# Step 1: Ensure local changes are committed
echo ""
echo "Step 1: Checking for uncommitted changes..."
if [[ -n $(git status -s) ]]; then
    echo "❌ ERROR: You have uncommitted changes. Commit them first!"
    git status -s
    exit 1
fi
echo "✅ Working directory clean"

# Step 2: Ensure pushed to GitHub
echo ""
echo "Step 2: Checking if pushed to GitHub..."
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/$BRANCH)

if [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
    echo "❌ ERROR: Local commits not pushed to GitHub!"
    echo "Run: git push origin $BRANCH"
    exit 1
fi
echo "✅ Latest changes pushed to GitHub"

# Step 3: Deploy to server via Git pull
echo ""
echo "Step 3: Deploying to server via Git..."
ssh $SERVER << EOF
    set -e
    cd $PROJECT_DIR
    
    echo "📥 Pulling latest changes from GitHub..."
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
    
    echo "📊 Current commit:"
    git log -1 --oneline
    
    echo "📦 Installing dependencies..."
    source .venv/bin/activate
    pip install -q -r requirements.txt
    
    echo "♻️  Restarting service..."
    sudo systemctl restart $SERVICE
    
    echo "⏳ Waiting for service to start..."
    sleep 3
    
    echo "✅ Checking service status..."
    sudo systemctl is-active --quiet $SERVICE && echo "✅ Service running" || echo "❌ Service failed"
EOF

# Step 4: Verify deployment
echo ""
echo "Step 4: Verifying deployment..."
DEPLOYED_COMMIT=$(ssh $SERVER "cd $PROJECT_DIR && git rev-parse HEAD")

if [ "$LOCAL_COMMIT" = "$DEPLOYED_COMMIT" ]; then
    echo "✅ Deployment successful!"
    echo "   Local:    $LOCAL_COMMIT"
    echo "   Deployed: $DEPLOYED_COMMIT"
else
    echo "❌ Deployment mismatch!"
    echo "   Local:    $LOCAL_COMMIT"
    echo "   Deployed: $DEPLOYED_COMMIT"
    exit 1
fi

# Step 5: Health check
echo ""
echo "Step 5: Health check..."
if curl -sf http://192.168.178.55:9001 > /dev/null; then
    echo "✅ Dashboard responding at http://192.168.178.55:9001"
else
    echo "⚠️  Dashboard not responding (may take a moment to start)"
fi

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo "Dashboard: http://192.168.178.55:9001"
echo "Deployed commit: $DEPLOYED_COMMIT"
echo ""
