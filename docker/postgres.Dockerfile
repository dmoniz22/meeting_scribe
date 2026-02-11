FROM pgvector/pgvector:pg17

# pgvector is already included in the base image
# We create an initialization script that will be run on first database startup
# Note: Extensions are created per-database, so we do it in init script

RUN echo "CREATE EXTENSION IF NOT EXISTS pgvector;" > /docker-entrypoint-initdb.d/01-enable-extensions.sql && \
    echo "CREATE EXTENSION IF NOT EXISTS pg_trgm;" >> /docker-entrypoint-initdb.d/01-enable-extensions.sql && \
    echo "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" >> /docker-entrypoint-initdb.d/01-enable-extensions.sql
