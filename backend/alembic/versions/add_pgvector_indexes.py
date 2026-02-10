"""
Migration to add pgvector support and HNSW indexes

Revision ID: add_pgvector_indexes
Create Date: 2026-02-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_pgvector_indexes'
down_revision = None  # This is the first migration if alembic is fresh
branch_labels = None
depends_on = None


def upgrade():
    """Add pgvector support and create HNSW indexes."""
    
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pgvector")
    
    # Add embedding columns to transcript_segments
    op.add_column(
        'transcript_segments',
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True)
    )
    
    # Add embedding columns to notes
    op.add_column(
        'notes',
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True)
    )
    
    # Create HNSW indexes for vector similarity search
    # Using pgvector's vector type and HNSW index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_segments_embedding 
        ON transcript_segments 
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_notes_embedding 
        ON notes 
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    
    # Create GIN index for text search (if not exists)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_segments_text_search 
        ON transcript_segments 
        USING gin (to_tsvector('english', text))
    """)
    
    print("✓ Migration complete: pgvector indexes created")


def downgrade():
    """Remove pgvector support and indexes."""
    
    # Drop indexes
    op.drop_index('idx_segments_embedding', table_name='transcript_segments')
    op.drop_index('idx_notes_embedding', table_name='notes')
    op.drop_index('idx_segments_text_search', table_name='transcript_segments')
    
    # Drop columns
    op.drop_column('transcript_segments', 'embedding')
    op.drop_column('notes', 'embedding')
    
    # Note: We don't drop the extension as it may be used by other databases
    print("✓ Downgrade complete: pgvector indexes removed")
