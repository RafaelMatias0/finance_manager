"""contas e transferencias

Revision ID: 0004_contas_e_transferencias
Revises: <AJUSTE_PARA_O_HEAD_ATUAL>
Create Date: 2026-08-15

IMPORTANTE: troque o valor de `down_revision` abaixo pelo revision id da
sua migração mais recente (rode `alembic heads` pra descobrir). Como
combinado, esta migração assume que não há dados reais a preservar — ela
cria conta_id como NOT NULL diretamente. Se você já tiver dados de teste
que queira manter, rode `alembic downgrade base` antes do `upgrade head`,
ou popule as contas manualmente antes de aplicar o NOT NULL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_contas_e_transferencias"
down_revision = "58d42cc2789d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome_banco", sa.String(length=80), nullable=False),
        sa.Column("apelido", sa.String(length=80), nullable=True),
        sa.Column("saldo_inicial", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "transferencias",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conta_origem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("conta_destino_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=True),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.add_column(
        "movimentacoes",
        sa.Column("conta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contas.id", ondelete="RESTRICT"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("movimentacoes", "conta_id")
    op.drop_table("transferencias")
    op.drop_table("contas")