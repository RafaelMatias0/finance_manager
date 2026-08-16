# Changelog

## v2.3.0 — Fase 3: Pendências

- **Pendências** (`Pendencia`): contas recorrentes (aluguel, assinaturas
  — um vencimento por mês, dia fixo) ou avulsas (um vencimento único).
  Sem campo `tipo` redundante — vem de `pendencia.categoria.tipo`, mesmo
  princípio de `Movimentacao`.
- **Status pago/pendente nunca é guardado** — é sempre calculado a partir
  de existir ou não uma `Movimentacao` vinculada a um vencimento
  específico. Se o usuário ficar meses sem marcar uma recorrente como
  paga, cada mês aparece como um ciclo atrasado separado (a dívida
  acumulada fica visível).
- **"Marcar como paga" cria uma Movimentação de verdade**
  (`POST /pendencias/{id}/pagar`) — não é um toggle desacoplado do
  histórico real. `Movimentacao` ganhou dois campos novos:
  `pendencia_id` e `pendencia_referencia` (o vencimento quitado,
  separado da data real do pagamento — permite pagar atrasado sem perder
  essa informação). Índice único parcial trava, no banco, contra pagar o
  mesmo vencimento duas vezes.
- **Rotas novas**: `GET/POST/PATCH/DELETE /pendencias` e `POST
  /pendencias/{id}/pagar`. `DELETE` bloqueado (`409`) se a pendência já
  tiver pagamentos — use `PATCH ativa=false` pra "pausar" em vez de
  apagar.
- **Front-end**: página nova `pendencias.html` (criar, editar,
  pausar/reativar recorrentes, apagar, marcar vencimento como pago); o
  item "Pendências" da sidebar deixou de ser "em breve" em todas as
  páginas; o card de Pendências no grid do Início deixou de ser
  placeholder — mostra as pendências mais urgentes (atrasadas primeiro),
  só leitura, com link pra página dedicada.
- **Correção**: as relações protegidas por `ON DELETE RESTRICT`
  (`Categoria.movimentacoes`, `Conta.movimentacoes`, `Pendencia.
  pagamentos`) não tinham `passive_deletes=True` — o SQLAlchemy tentava
  "desvincular" as linhas filhas (setar a FK pra `NULL`) antes do delete,
  em vez de deixar o `RESTRICT` do banco barrar a operação. Em
  Categoria/Conta isso não tinha efeito visível (a coluna é `NOT NULL`,
  então a tentativa falhava por outro motivo, e o `409` acontecia mesmo
  assim, por acidente); em Pendencia (coluna opcional) o bug era real —
  apagar uma pendência com pagamentos já feitos funcionava
  silenciosamente. Corrigido nas três.
- **Correção**: o schema `MovimentacaoOut` não expunha os campos novos
  (`pendencia_id`/`pendencia_referencia`) na resposta da API — corrigido.
- Sem subcategorias nesta fase (decisão de escopo já registrada desde a
  Fase 2).

## v2.2.0 — Fase 2: Divisão Início / Controle

- **Início enxuto**: o painel de Histórico saiu daqui — o Início agora é só
  resumo/atalhos do dia a dia: card de saldo por conta (só leitura) e o
  formulário de nova movimentação, lado a lado com os dois placeholders "em
  breve" (Pendências, envio de arquivo).
- **Página nova `controle.html`**: recebeu o Histórico completo (filtros,
  paginação, edição via modal — mesma funcionalidade de antes, só mudou de
  página) e ganhou duas peças de análise por categoria: um gráfico de pizza
  dos gastos do mês atual, e uma tabela-resumo por categoria (total, % do
  total do tipo, mínimo/média/máximo por movimentação, e o total de cada um
  dos últimos 3 meses). Novo item "Controle" na sidebar, entre Início e
  Relatórios.
- **Rota nova `GET /relatorios/por-categoria`**: agregação em SQL
  (`GROUP BY`, não em Python) por escalabilidade, já que pode cobrir "todo
  o histórico" do usuário — mesmo padrão de `calcular_saldos_contas`.
  Parâmetros opcionais (`data_inicio`, `data_fim`, `tipo`,
  `meses_recentes`) cobrem tanto o gráfico (mês atual, despesas) quanto a
  tabela (histórico completo, últimos 3 meses).
- **Subcategorias**: consideradas e adiadas de propósito — exigiriam
  mudança de schema (hierarquia em `Categoria`), então ficaram fora desta
  fase; a tabela de Controle agrupa só por categoria.
- **Paleta do gráfico de pizza**: validada com a skill de dataviz (8
  matizes categóricas em ordem fixa, checadas contra o fundo do card —
  `--papel-cartao` — pra separação sob daltonismo e contraste); acima de 8
  categorias com gasto no mês, as menores agrupam em "Outras" em vez de
  gerar uma cor nova.
- **Correção**: `test_jwt.py` e `test_relatorios.py` criavam movimentações
  sem `conta_id` — campo que ficou obrigatório desde a v2.1.0 (Fase 1) e
  nunca tinha sido atualizado nos testes, então ambos os arquivos estavam
  quebrados (todo POST /movimentacoes vinha 422). Corrigido: os dois
  criam uma conta de teste antes de lançar qualquer movimentação.

## v2.1.1 — Ajustes finos da Fase 1

- **Nova página `contas.html`**: criar/editar/apagar conta e transferir
  entre contas saíram do Início e ganharam página própria, com um link
  "Contas" normal na sidebar (antes era um botão com comportamento
  especial — abria modal ou rolava a tela dependendo da página). A nova
  página também mostra, pela primeira vez no front-end, o **histórico de
  transferências** já feitas (a rota `GET /transferencias` já existia no
  backend desde a v2.1.0, mas nunca tinha sido consumida pela tela).
- **Início reorganizado**: o resumo de Receitas/Despesas/Saldo deu lugar a
  um grid de 4 blocos — saldo por conta (só leitura, com link "Gerenciar
  contas" para a nova página), o histórico completo de movimentações
  (com filtros/paginação, que só mudou de lugar), e dois placeholders
  "em breve" (Pendências — já prevista na Fase 3 do roadmap — e uma área
  de envio de arquivo, ainda sem escopo definido). Os totais de
  Receitas/Despesas/Saldo não aparecem mais no Início por enquanto; a
  rota `GET /saldo` continua existindo no backend, só não é mais chamada
  pelo front-end.
- **Hambúrguer duplicado removido**: existiam dois botões de
  recolher/expandir a sidebar (um na própria sidebar, outro no header do
  conteúdo). Ficou só o da sidebar.

## v2.1.0 — Fase 1: Contas bancárias + Sidebar

- **Contas bancárias** (`Conta`): registro "de visão" — nome do banco, apelido
  opcional e saldo inicial configurável. Sem qualquer integração real com
  bancos. Rotas `GET/POST/PATCH/DELETE /contas` (delete bloqueado com `409`
  se a conta tiver movimentações/transferências vinculadas).
- **`Movimentacao.conta_id` passou a ser obrigatório** — toda movimentação
  agora pertence a uma conta. `ON DELETE RESTRICT`, mesmo padrão já usado
  em `categoria_id`.
- **Transferências entre contas** (`Transferencia`): modelo novo, separado
  de `Movimentacao` de propósito — não é receita nem despesa, então não
  entra nos relatórios (que derivam o tipo a partir de `Categoria.tipo`).
  Só afeta o saldo calculado das duas contas envolvidas. Rotas
  `GET/POST /transferencias`.
- **Saldo por conta**: `GET /contas` já retorna `saldo_atual` calculado
  (saldo inicial + receitas − despesas + transferências recebidas −
  enviadas) por conta. `GET /saldo` (total do usuário) passou a somar
  também os saldos iniciais de todas as contas.
- **Front-end**: nova sidebar recolhível, compartilhada entre as páginas
  logadas (`js/sidebar.js`), com os itens Início, Relatórios, Contas,
  e Pendências/Planos e Metas marcados como "em breve" (ainda sem página —
  fases seguintes). Formulário de nova movimentação e modal de edição
  passaram a exigir conta; histórico ganhou coluna e filtro de conta;
  novo painel "Contas" no dashboard (criar/editar/apagar conta, transferir
  entre contas).
- **Correção**: removidas duas duplicações de rota que existiam no
  `main.py` (`PATCH /categorias/{id}` e `PATCH /movimentacoes/{id}`
  estavam definidas duas vezes cada — o FastAPI só registrava a última;
  agora só existe uma definição de cada).
- **Breaking change de schema**: como combinado, o banco precisa ser
  resetado (`alembic downgrade base` + `alembic upgrade head`) — não há
  migração de dados antigos sem conta, já que `conta_id` é `NOT NULL`.

## v2.0.0

- Sistema de relatórios:
  - **Automáticos**: semanal (toda segunda 01:00, cobre a semana anterior)
    e mensal (todo dia 1 às 01:00, cobre o mês anterior) — rodam via
    scheduler in-process (APScheduler) e ficam salvos, visíveis numa lista
    no app
  - **Personalizado**: período (data inicial/final), filtro por tipo
    (receita/despesa/todos) e por categoria (participação dela no total do
    mesmo tipo) — histórico, saldo do período, gráfico de barras por dia,
    gráfico de pizza de participação
  - **Comparativo**: compara duas categorias — histórico combinado,
    gráfico de linhas por dia; se as categorias forem de tipos diferentes,
    mostra a diferença de saldo entre elas; se forem do mesmo tipo, mostra
    a soma e dois gráficos de pizza (participação individual e combinada
    no total daquele tipo)
  - Rota `POST /relatorios/gerar-agora` para gerar um automático na hora,
    sem esperar o agendamento (útil pra testar/demonstrar)
- Front-end: nova página `relatorios.html` com os três modos, usando
  Chart.js (via CDN) para os gráficos

## v1.1.0

- Responsividade mobile no front-end:
  - Tabela do histórico vira lista de "cards" empilhados abaixo de 600px
    (5 colunas não cabem numa tela de celular)
  - Alvos de toque com altura mínima de 44px (botões, campos, abas)
  - Campos de formulário com `font-size: 16px` no mobile, evitando o zoom
    automático que o iOS faz ao focar um input com fonte menor que essa
  - Filtros do histórico empilham em coluna única no mobile
  - Ajustes de espaçamento/tamanho de fonte em telas estreitas

## v1.0.0

- Modelagem do banco (Usuario, Categoria, Movimentacao) com Alembic
- Backend FastAPI: CRUD de movimentações, categorias, saldo
- Autenticação JWT (login, cadastro, rotas protegidas, isolamento entre usuários)
- Paginação e ordenação no histórico
- Front-end HTML/CSS/JS puro com design "livro-razão"