"""planos

Revision ID: 0006_planos
Revises: 0005_pendencias
Create Date: 2026-08-16

Adiciona numero_parcelas em pendencias (dívida em parcelas reaproveita
Pendencia recorrente, mas com fim definido), cria a tabela planos, e a
coluna plano_id em movimentacoes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0006_planos"
down_revision = "0005_pendencias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pendencias", sa.Column("numero_parcelas", sa.Integer(), nullable=True))

    op.create_table(
        "planos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("tipo", sa.Enum("guardar_dinheiro", "quitar_divida", name="tipo_plano"), nullable=False),
        sa.Column("conta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mes_inicio", sa.Date(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("guardar_modo", sa.Enum("simples", "reducao_categoria", name="guardar_modo"), nullable=True),
        sa.Column("criterio_reducao", sa.Enum("percentual_receita", "valor_fixo", name="criterio_reducao"), nullable=True),
        sa.Column("alvo_percentual", sa.Numeric(5, 2), nullable=True),
        sa.Column("alvo_valor_reducao", sa.Numeric(12, 2), nullable=True),
        sa.Column("divida_modo", sa.Enum("prazo", "parcelas", name="divida_modo"), nullable=True),
        sa.Column("pendencia_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pendencias.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("valor_alvo", sa.Numeric(12, 2), nullable=True),
        sa.Column("data_prazo", sa.Date(), nullable=True),
        sa.Column("categoria_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.add_column(
        "movimentacoes",
        sa.Column("plano_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("planos.id", ondelete="RESTRICT"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("movimentacoes", "plano_id")
    op.drop_table("planos")
    op.drop_column("pendencias", "numero_parcelas")

    # Tipos ENUM do Postgres não são removidos automaticamente pelo
    # Alembic ao dropar a tabela/coluna que os usava.
    sa.Enum(name="tipo_plano").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="guardar_modo").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="criterio_reducao").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="divida_modo").drop(op.get_bind(), checkfirst=True)
