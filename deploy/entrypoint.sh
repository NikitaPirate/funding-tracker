#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

# Default to single instance if not specified
export INSTANCE_COUNT=${INSTANCE_COUNT:-1}

echo "Starting supervisord with $INSTANCE_COUNT instance(s)..."
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf