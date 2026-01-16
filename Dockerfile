FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install git for dependencies from GitHub and supervisor for process management
RUN apt-get update && apt-get install -y git supervisor && rm -rf /var/lib/apt/lists/*

# Copy dependency files and README (required for package metadata)
COPY pyproject.toml uv.lock README.md ./

# Copy application code
COPY . .

# Copy supervisord configuration
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Install dependencies
RUN uv sync --frozen --no-dev

# Add venv to PATH so we can call scripts directly
ENV PATH="/app/.venv/bin:$PATH"

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]