"""AI tags, places and rotation

Revision ID: e37165b0c62f
Revises: 61f2fc468c85
Create Date: 2026-11-15 16:06:45.168205
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e37165b0c62f'
down_revision = '61f2fc468c85'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('app_settings',
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('tag_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('model', sa.String(), nullable=False),
    sa.Column('prompt_version', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('requests', sa.Integer(), nullable=False),
    sa.Column('succeeded', sa.Integer(), nullable=False),
    sa.Column('errored', sa.Integer(), nullable=False),
    sa.Column('est_cost_usd', sa.Float(), nullable=False),
    sa.Column('cost_usd', sa.Float(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('batch_id')
    )
    op.create_index(op.f('ix_tag_runs_status'), 'tag_runs', ['status'], unique=False)
    op.create_table('tags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(), nullable=False),
    sa.Column('value', sa.String(), nullable=False),
    sa.Column('hidden', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('merged_into_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['merged_into_id'], ['tags.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('category', 'value')
    )
    op.create_table('photo_ai',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('photo_id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('base_rotation', sa.SmallInteger(), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=True),
    sa.Column('output_tokens', sa.Integer(), nullable=True),
    sa.Column('cache_read_tokens', sa.Integer(), nullable=True),
    sa.Column('cache_write_tokens', sa.Integer(), nullable=True),
    sa.Column('cost_usd', sa.Float(), nullable=True),
    sa.Column('best', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('flags', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['tag_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'photo_id')
    )
    op.create_index(op.f('ix_photo_ai_photo_id'), 'photo_ai', ['photo_id'], unique=False)
    op.create_index(op.f('ix_photo_ai_run_id'), 'photo_ai', ['run_id'], unique=False)
    op.create_table('photo_tags',
    sa.Column('photo_id', sa.Integer(), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('removed', sa.Boolean(), server_default='false', nullable=False),
    sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('photo_id', 'tag_id')
    )
    op.create_index(op.f('ix_photo_tags_tag_id'), 'photo_tags', ['tag_id'], unique=False)
    op.add_column('photos', sa.Column('place_country', sa.String(), nullable=True))
    op.add_column('photos', sa.Column('place_region', sa.String(), nullable=True))
    op.add_column('photos', sa.Column('place_city', sa.String(), nullable=True))
    op.add_column('photos', sa.Column('place_source', sa.String(), nullable=True))
    op.add_column('photos', sa.Column('rotation', sa.SmallInteger(), server_default='0', nullable=False))
    op.add_column('photos', sa.Column('tag_status', sa.String(), server_default='pending', nullable=False))
    op.add_column('photos', sa.Column('tag_attempts', sa.SmallInteger(), server_default='0', nullable=False))
    op.add_column('photos', sa.Column('tag_source_id', sa.Integer(), nullable=True))
    op.add_column('photos', sa.Column('ai_id', sa.Integer(), nullable=True))
    op.add_column('photos', sa.Column('caption', sa.Text(), nullable=True))
    op.add_column('photos', sa.Column('scene', sa.String(), nullable=True))
    op.add_column('photos', sa.Column('setting', sa.String(), nullable=True))
    op.add_column('photos', sa.Column('aesthetic', sa.SmallInteger(), nullable=True))
    op.add_column('photos', sa.Column('ai_terms', sa.Text(), nullable=True))
    op.add_column('photos', sa.Column('ai_tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', coalesce(ai_terms, ''))", persisted=True), nullable=True))
    op.create_index(op.f('ix_photos_aesthetic'), 'photos', ['aesthetic'], unique=False)
    op.create_index('ix_photos_ai_tsv', 'photos', ['ai_tsv'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_photos_place_country'), 'photos', ['place_country'], unique=False)
    op.create_index(op.f('ix_photos_place_region'), 'photos', ['place_region'], unique=False)
    op.create_index(op.f('ix_photos_tag_status'), 'photos', ['tag_status'], unique=False)
    op.create_foreign_key('photos_tag_source_id_fkey', 'photos', 'photos', ['tag_source_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('photos_ai_id_fkey', 'photos', 'photo_ai', ['ai_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('photos_ai_id_fkey', 'photos', type_='foreignkey')
    op.drop_constraint('photos_tag_source_id_fkey', 'photos', type_='foreignkey')
    op.drop_index(op.f('ix_photos_tag_status'), table_name='photos')
    op.drop_index(op.f('ix_photos_place_region'), table_name='photos')
    op.drop_index(op.f('ix_photos_place_country'), table_name='photos')
    op.drop_index('ix_photos_ai_tsv', table_name='photos', postgresql_using='gin')
    op.drop_index(op.f('ix_photos_aesthetic'), table_name='photos')
    op.drop_column('photos', 'ai_tsv')
    op.drop_column('photos', 'ai_terms')
    op.drop_column('photos', 'aesthetic')
    op.drop_column('photos', 'setting')
    op.drop_column('photos', 'scene')
    op.drop_column('photos', 'caption')
    op.drop_column('photos', 'ai_id')
    op.drop_column('photos', 'tag_source_id')
    op.drop_column('photos', 'tag_attempts')
    op.drop_column('photos', 'tag_status')
    op.drop_column('photos', 'rotation')
    op.drop_column('photos', 'place_source')
    op.drop_column('photos', 'place_city')
    op.drop_column('photos', 'place_region')
    op.drop_column('photos', 'place_country')
    op.drop_index(op.f('ix_photo_tags_tag_id'), table_name='photo_tags')
    op.drop_table('photo_tags')
    op.drop_index(op.f('ix_photo_ai_run_id'), table_name='photo_ai')
    op.drop_index(op.f('ix_photo_ai_photo_id'), table_name='photo_ai')
    op.drop_table('photo_ai')
    op.drop_table('tags')
    op.drop_index(op.f('ix_tag_runs_status'), table_name='tag_runs')
    op.drop_table('tag_runs')
    op.drop_table('app_settings')
