#!/bin/bash
set -e

echo "=========================================================="
echo "    STARTING EQUILIBRIUM INSTITUTIONAL TRADING GATEWAY    "
echo "=========================================================="
echo "System Timezone: $(date)"
echo "Current EST Time: $(TZ=America/New_York date)"

# Ensure config.json exists
if [ ! -f config.json ] && [ -f config.example.json ]; then
    echo "[INIT] config.json not found. Generating default from config.example.json..."
    cp config.example.json config.json
fi

# Ensure SQLite tables exist
python3 -c "from engine.storage import init_db; init_db()"

# Launch background execution worker
echo "[INIT] Launching background trading bot..."
python3 bot.py &
BOT_PID=$!

# Launch Streamlit web dashboard
echo "[INIT] Launching Streamlit web control gateway on port ${PORT:-8501}..."
exec streamlit run app.py \
    --server.port "${PORT:-8501}" \
    --server.address "0.0.0.0" \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false
