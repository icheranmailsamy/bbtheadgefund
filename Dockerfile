FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/New_York \
    PORT=8501

# Install core build dependencies, C++ compiler, timezone database, and SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    tzdata \
    curl \
    sqlite3 \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/

# Compile native C++ shared library for Linux (x86_64 or aarch64)
RUN cd /app/cpp && g++ -std=c++20 -O3 -shared -fPIC engine_c_api.cpp -o libmorningsniper.so

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8501}/_stcore/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
