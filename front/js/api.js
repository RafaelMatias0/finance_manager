/**
 * Camada fina sobre fetch: injeta o token, monta querystring, trata erros
 * de forma consistente. Se o token expirar/for inválido (401), dispara
 * o evento "sessao-expirada" para o app.js voltar pra tela de login.
 */
const TOKEN_KEY = "gf_access_token";

const Auth = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },
  setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
  },
  limparToken() {
    localStorage.removeItem(TOKEN_KEY);
  },
  estaLogado() {
    return Boolean(this.getToken());
  },
};

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : "Erro na requisição");
    this.status = status;
    this.detail = detail;
  }
}

function montarQueryString(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([chave, valor]) => {
    if (valor !== undefined && valor !== null && valor !== "") {
      query.append(chave, valor);
    }
  });
  const texto = query.toString();
  return texto ? `?${texto}` : "";
}

async function requisitar(method, path, { body, query, form, semAuth } = {}) {
  const headers = {};
  const opcoes = { method, headers };

  if (!semAuth) {
    const token = Auth.getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    opcoes.body = new URLSearchParams(body).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(body);
  }

  const url = API_BASE_URL + path + montarQueryString(query);

  let resposta;
  try {
    resposta = await fetch(url, opcoes);
  } catch (erroRede) {
    throw new ApiError(0, `Não foi possível conectar à API em ${API_BASE_URL}. Ela está rodando?`);
  }

  if (resposta.status === 204) return null;

  const contentType = resposta.headers.get("content-type") || "";
  const dados = contentType.includes("application/json") ? await resposta.json() : null;

  if (!resposta.ok) {
    if (resposta.status === 401 && !semAuth) {
      Auth.limparToken();
      document.dispatchEvent(new CustomEvent("sessao-expirada"));
    }
    throw new ApiError(resposta.status, dados?.detail ?? "Erro desconhecido");
  }

  return dados;
}

const Api = {
  login(email, senha) {
    return requisitar("POST", "/auth/login", {
      form: true,
      semAuth: true,
      body: { username: email, password: senha },
    });
  },
  cadastrar(nome, email, senha) {
    return requisitar("POST", "/usuarios", { semAuth: true, body: { nome, email, senha } });
  },
  meuUsuario() {
    return requisitar("GET", "/usuarios/me");
  },
  atualizarMeuUsuario(dados) {
    return requisitar("PATCH", "/usuarios/me", { body: dados });
  },
  saldo() {
    return requisitar("GET", "/saldo");
  },
  categorias() {
    return requisitar("GET", "/categorias");
  },
  criarCategoria(nome, tipo) {
    return requisitar("POST", "/categorias", { body: { nome, tipo } });
  },
  historico(filtros) {
    return requisitar("GET", "/movimentacoes", { query: filtros });
  },
  criarMovimentacao(dados) {
    return requisitar("POST", "/movimentacoes", { body: dados });
  },
  editarMovimentacao(id, dados) {
    return requisitar("PATCH", `/movimentacoes/${id}`, { body: dados });
  },
  apagarMovimentacao(id) {
    return requisitar("DELETE", `/movimentacoes/${id}`);
  },
  // ---------- Contas ----------
  contas() {
    return requisitar("GET", "/contas");
  },
  criarConta(dados) {
    return requisitar("POST", "/contas", { body: dados });
  },
  editarConta(id, dados) {
    return requisitar("PATCH", `/contas/${id}`, { body: dados });
  },
  apagarConta(id) {
    return requisitar("DELETE", `/contas/${id}`);
  },
  // ---------- Transferências ----------
  transferencias() {
    return requisitar("GET", "/transferencias");
  },
  criarTransferencia(dados) {
    return requisitar("POST", "/transferencias", { body: dados });
  },
  // ---------- Pendências ----------
  pendencias() {
    return requisitar("GET", "/pendencias");
  },
  criarPendencia(dados) {
    return requisitar("POST", "/pendencias", { body: dados });
  },
  editarPendencia(id, dados) {
    return requisitar("PATCH", `/pendencias/${id}`, { body: dados });
  },
  apagarPendencia(id) {
    return requisitar("DELETE", `/pendencias/${id}`);
  },
  pagarPendencia(id, dados) {
    return requisitar("POST", `/pendencias/${id}/pagar`, { body: dados });
  },
  // ---------- Planos ----------
  planos() {
    return requisitar("GET", "/planos");
  },
  criarPlano(dados) {
    return requisitar("POST", "/planos", { body: dados });
  },
  editarPlano(id, dados) {
    return requisitar("PATCH", `/planos/${id}`, { body: dados });
  },
  apagarPlano(id) {
    return requisitar("DELETE", `/planos/${id}`);
  },
  aportarPlano(id, dados) {
    return requisitar("POST", `/planos/${id}/aportar`, { body: dados });
  },
  // ---------- Relatórios ----------
  relatorioPersonalizado(filtros) {
    return requisitar("GET", "/relatorios/personalizado", { query: filtros });
  },
  porCategoria(filtros) {
    return requisitar("GET", "/relatorios/por-categoria", { query: filtros });
  },
  saldoDiarioPorConta() {
    return requisitar("GET", "/relatorios/saldo-diario-por-conta");
  },
  relatorioComparativo(filtros) {
    return requisitar("GET", "/relatorios/comparativo", { query: filtros });
  },
  listarRelatoriosAutomaticos() {
    return requisitar("GET", "/relatorios");
  },
  obterRelatorioAutomatico(id) {
    return requisitar("GET", `/relatorios/${id}`);
  },
  gerarRelatorioAgora(tipo) {
    return requisitar("POST", "/relatorios/gerar-agora", { query: { tipo } });
  },
};