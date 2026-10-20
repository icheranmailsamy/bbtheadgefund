#!/bin/bash
# ==============================================================================
# AWS EC2 LOW-LATENCY 1-COMMAND DEPLOYMENT SCRIPT
# Strategy: The Morning Sniper (Option B + 3-Loss Stop + 0 Slippage + C++ Core)
# Region: AWS us-east-2 (Ohio) -> Sub-5ms network transit to CME Aurora/Chicago
# ==============================================================================

set -e

echo "=================================================================="
echo "    DEPLOYING EQUILIBRIUM MORNING SNIPER TO AWS EC2 INSTANCE      "
echo "=================================================================="

# 1. Update OS packages and install core build & docker dependencies
echo "[1/5] Installing Docker, Docker Compose, Git, and build tools..."
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    docker.io \
    docker-compose-plugin \
    git \
    curl \
    htop \
    tzdata

# 2. Configure Docker service
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# 3. Synchronize Timezone to America/New_York (NYSE / CME Market Hours)
echo "[2/5] Setting server timezone to America/New_York (EST)..."
sudo timedatectl set-timezone America/New_York

# 4. Clone or pull latest code
REPO_DIR="bbtheadgefund"
if [ -d "$REPO_DIR" ]; then
    echo "[3/5] Updating existing repository..."
    cd "$REPO_DIR"
    git pull origin main
else
    echo "[3/5] Cloning repository from GitHub..."
    git clone https://github.com/icheranmailsamy/bbtheadgefund.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# 5. Ensure config.json exists
if [ ! -f config.json ]; then
    echo "[4/5] Initializing config.json from template..."
    cp config.example.json config.json
fi

# 6. Build and launch Docker container
echo "[5/5] Building C++20 engine & starting Docker container..."
sudo docker compose down || true
sudo docker compose up -d --build

PUBLIC_IP=$(curl -s https://ifconfig.me || curl -s https://api.ipify.org)

echo "=================================================================="
echo "  ✓ DEPLOYMENT COMPLETE! BOT IS RUNNING 24/7 IN THE CLOUD         "
echo "=================================================================="
echo "  Web Gateway URL:     http://${PUBLIC_IP}:8501"
echo "  Server Time (EST):   $(date)"
echo "  Container Status:    $(sudo docker ps --format '{{.Names}} ({{.Status}})')"
echo ""
echo "  To view live bot logs:   sudo docker logs -f equilibrium_trading_bot"
echo "  To restart bot:          sudo docker compose restart"
echo "=================================================================="
