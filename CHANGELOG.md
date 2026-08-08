# Changelog

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
