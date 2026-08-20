"""pendencias

Revision ID: 0005_pendencias
Revises: 0004_contas_e_transferencias
Create Date: 2026-08-16

Cria a tabela `pendencias` e adiciona `pendencia_id`/`pendencia_referencia`
(nullable) em `movimentacoes` — ao contrário da migração de `conta_id` na
Fase 1, esta não quebra dados existentes: toda movimentação já criada
continua válida (pendencia_id nulo = "não veio de uma pendência").
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0005_pendencias"
down_revision = "0004_contas_e_transferencias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pendencias",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("descricao", sa.String(length=120), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("categoria_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("conta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contas.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("recorrente", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dia_vencimento", sa.Integer(), nullable=True),
        sa.Column("data_vencimento", sa.Date(), nullable=True),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.add_column(
        "movimentacoes",
        sa.Column("pendencia_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pendencias.id", ondelete="RESTRICT"), nullable=True),
    )
    op.add_column(
        "movimentacoes",
        sa.Column("pendencia_referencia", sa.Date(), nullable=True),
    )

    # Trava contra pagar o mesmo vencimento duas vezes — só entre as
    # movimentações que de fato vieram de uma pendência.
    op.create_index(
        "ix_movimentacoes_pendencia_ciclo_unico",
        "movimentacoes",
        ["pendencia_id", "pendencia_referencia"],
        unique=True,
        postgresql_where=sa.text("pendencia_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_movimentacoes_pendencia_ciclo_unico", table_name="movimentacoes")
    op.drop_column("movimentacoes", "pendencia_referencia")
    op.drop_column("movimentacoes", "pendencia_id")
    op.drop_table("pendencias")
