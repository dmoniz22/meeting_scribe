FROM pgvector/pgvector:pg17

# pgvector extension should already be available in this image
# We create an initialization script that will be run on first database startup

RUN echo "CREATE EXTENSION IF NOT EXISTS vector;" > /docker-entrypoint-initdb.d/01-enable-extensions.sql && \
    echo "CREATE EXTENSION IF NOT EXISTS pg_trgm;" >> /docker-entrypoint-initdb.d/01-enable-extensions.sql && \
    echo "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" >> /docker-entrypoint-initdb.d/01-enable-extensions.sql
