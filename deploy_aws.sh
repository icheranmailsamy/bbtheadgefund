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
echo "[1/5] Installing Docker, Git, and build tools..."
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    docker.io \
    git \
    curl \
    htop \
    tzdata

# Install Docker Compose Plugin (Compatible with Ubuntu 22.04 & 24.04 Noble)
echo "[1b/5] Installing Docker Compose CLI Plugin..."
sudo mkdir -p /usr/local/lib/docker/cli-plugins /etc/docker/cli-plugins /usr/local/bin
DOCKER_COMPOSE_URL="https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)"
sudo curl -SL "$DOCKER_COMPOSE_URL" -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
sudo ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose

# 2. Configure Docker service
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# 3. Configure 2GB Swap Memory (Enables 100% Free Tier t3.micro support)
if [ $(free -m | awk '/^Mem:/{print $2}') -lt 1800 ] && [ ! -f /swapfile ]; then
    echo "[SETUP] Configuring 2GB virtual memory swap (Enabling 100% Free Tier t3.micro)..."
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# 4. Synchronize Timezone to America/New_York (NYSE / CME Market Hours)
echo "[2/5] Setting server timezone to America/New_York (EST)..."
sudo timedatectl set-timezone America/New_York

# 5. Clone or pull latest code
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

# 6. Ensure config.json exists
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
