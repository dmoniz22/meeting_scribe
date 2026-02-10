FROM pgvector/pgvector:pg17

# pgvector is already included in the base image
# We just need to ensure the extensions are available

# Create initialization script to enable extensions
RUN echo "CREATE EXTENSION IF NOT EXISTS pgvector;" > /docker-entrypoint-initdb.d/01-enable-extensions.sql && \
    echo "CREATE EXTENSION IF NOT EXISTS pg_trgm;" >> /docker-entrypoint-initdb.d/01-enable-extensions.sql && \
    echo "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" >> /docker-entrypoint-initdb.d/01-enable-extensions.sql
