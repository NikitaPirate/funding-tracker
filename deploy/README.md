# Docker Deployment

## Prerequisites

- Docker
- Docker Compose

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

### Environment Variables

- `DB_CONNECTION`: PostgreSQL connection string (required)
- `EXCHANGES`: Comma-separated list of exchanges to run (default: all, empty = run all)
- `DEBUG_EXCHANGES`: Comma-separated list for DEBUG logging (independent of execution)

### Multi-Instance Configuration

The application supports horizontal scaling by splitting exchanges across multiple worker instances.

- `INSTANCE_COUNT`: Number of worker instances (default: 3)
  - Exchanges are distributed evenly using round-robin
  - Each instance runs independently with autorestart
  - All instances log to stdout/stderr

Examples:

```bash
# Run with 1 instance (all exchanges on single worker)
INSTANCE_COUNT=1 docker-compose up

# Run with 3 instances (default)
docker-compose up

# Run with 5 instances
INSTANCE_COUNT=5 docker-compose up

# Check supervisord status
docker exec funding-tracker supervisorctl status
```

## Running

### Start all services

```bash
docker-compose up
```

### Start with specific exchanges

```bash
# Via .env file (add: EXCHANGES=hyperliquid,bybit)
docker-compose up

# Via environment variable before command
EXCHANGES=hyperliquid,bybit docker-compose up

# Single exchange
EXCHANGES=hyperliquid docker-compose up
```

### Enable debug logging

```bash
# Via .env file (add: DEBUG_EXCHANGES=hyperliquid,bybit)
docker-compose up

# Via environment variable before command
DEBUG_EXCHANGES=hyperliquid,bybit docker-compose up
```

### Combine options

```bash
EXCHANGES=hyperliquid DEBUG_EXCHANGES=hyperliquid,bybit docker-compose up
```

## Local Development

### Connect to local database

The `docker-compose.override.yaml` file exposes the database port for local development:

```bash
# Database accessible at localhost:5432
psql -h localhost -p 5432 -U postgres -d funding_tracker
```

### Run application locally with Docker database

```bash
# Start only database
docker-compose up timescaledb

# Run application locally (connects to Docker DB)
export DB_CONNECTION="postgresql+psycopg://postgres:postgres@localhost:5432/funding_tracker"
EXCHANGES=hyperliquid funding-tracker
```

### Override exchanges locally

Create or modify `docker-compose.override.yaml`:

```yaml
services:
  funding-tracker:
    environment:
      - EXCHANGES=hyperliquid,bybit
```

Then run normally:

```bash
docker-compose up
```

## Management

### View logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f funding-tracker
docker-compose logs -f timescaledb
```

### Stop services

```bash
docker-compose down
```

### Remove volumes (deletes all data)

```bash
docker-compose down -v
```

### Rebuild after code changes

```bash
docker-compose up --build
```

## Troubleshooting

### Database connection errors

Ensure database is healthy before application starts:

```bash
docker-compose ps
```

### Application not starting

Check logs:

```bash
docker-compose logs funding-tracker
```

### Unknown exchange IDs

Check available exchanges in main README or use `--help`:

```bash
funding-tracker --help
```
