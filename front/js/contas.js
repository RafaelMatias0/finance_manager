/**
 * Página de Contas: criação/edição/exclusão de contas bancárias,
 * transferências entre contas e o histórico delas. Antes vivia embutido
 * no dashboard (index.html/app.js); virou página própria pra deixar o
 * Início mais enxuto (lá só sobra um resumo de saldo por conta, só leitura).
 */

// Se não estiver logado, nem tenta — manda de volta pro login.
if (!Auth.estaLogado()) {
  window.location.href = "index.html";
}

document.addEventListener("sessao-expirada", () => {
  toast("Sessão expirada. Faça login de novo.", "erro");
  window.location.href = "index.html";
});

// O botão "Sair" agora vive na sidebar (js/sidebar.js cuida dele, já que
// ela é compartilhada entre todas as páginas logadas).

let contas = [];

function contaPorId(id) {
  return contas.find((c) => c.id === id);
}

// ---------- Contas bancárias ----------

async function carregarContas() {
  try {
    contas = await Api.contas();
  } catch (erro) {
    toast(erro.message, "erro");
    return;
  }
  renderizarListaContas();
  preencherSelectsConta();
}

function renderizarListaContas() {
  const lista = document.getElementById("lista-contas");
  const vazio = document.getElementById("contas-vazio");
  lista.innerHTML = "";

  if (contas.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  contas.forEach((conta) => {
    const div = document.createElement("div");
    div.className = "cartao-conta";
    const classeSaldo = Number(conta.saldo_atual) < 0 ? "valor--despesa" : "valor--receita";
    div.innerHTML = `
      <div class="cartao-conta__info">
        <span class="cartao-conta__banco">${escaparHtml(conta.nome_banco)}</span>
        ${conta.apelido ? `<span class="cartao-conta__apelido">${escaparHtml(conta.apelido)}</span>` : ""}
      </div>
      <span class="cartao-conta__saldo ${classeSaldo}">${formatarMoeda(conta.saldo_atual)}</span>
      <div class="cartao-conta__acoes">
        <button type="button" class="btn-editar-conta">Editar</button>
        <button type="button" class="btn-apagar-conta">Apagar</button>
      </div>
    `;
    div.querySelector(".btn-editar-conta").addEventListener("click", () => abrirFormConta(conta));
    div.querySelector(".btn-apagar-conta").addEventListener("click", () => apagarConta(conta));
    lista.appendChild(div);
  });
}

function preencherSelectsConta() {
  const origem = document.getElementById("select-conta-origem");
  const destino = document.getElementById("select-conta-destino");

  [origem, destino].forEach((el) => {
    const valorAtual = el.value;
    el.innerHTML = "";
    contas.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
      el.appendChild(opt);
    });
    if (valorAtual) el.value = valorAtual;
  });

  // Transferência precisa de duas contas diferentes selecionadas por padrão
  if (contas.length > 1) {
    origem.value = contas[0].id;
    destino.value = contas[1].id;
  }
}

let contaEmEdicao = null;

function abrirFormConta(conta = null) {
  contaEmEdicao = conta;
  limparErro("erro-conta");
  const form = document.getElementById("form-conta");
  form.reset();

  document.getElementById("titulo-modal-conta").textContent = conta ? "Editar conta" : "Nova conta";
  if (conta) {
    form.elements["id"].value = conta.id;
    form.elements["nome_banco"].value = conta.nome_banco;
    form.elements["apelido"].value = conta.apelido ?? "";
    form.elements["saldo_inicial"].value = conta.saldo_inicial;
  } else {
    form.elements["id"].value = "";
    form.elements["saldo_inicial"].value = "0";
  }

  document.getElementById("modal-form-conta").classList.remove("oculto");
}

function fecharFormConta() {
  document.getElementById("modal-form-conta").classList.add("oculto");
  contaEmEdicao = null;
}

document.getElementById("btn-nova-conta").addEventListener("click", () => abrirFormConta());
document.getElementById("btn-cancelar-conta").addEventListener("click", fecharFormConta);
document.getElementById("modal-form-conta").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-form-conta") fecharFormConta();
});

document.getElementById("form-conta").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-conta");
  const dados = new FormData(evento.target);
  const id = dados.get("id");

  const corpo = {
    nome_banco: dados.get("nome_banco"),
    apelido: dados.get("apelido") || null,
    saldo_inicial: dados.get("saldo_inicial") || "0",
  };

  const destravar = travarBotaoEnvio(evento.target);
  try {
    if (id) {
      await Api.editarConta(id, corpo);
      toast("Conta atualizada.");
    } else {
      await Api.criarConta(corpo);
      toast("Conta criada.");
    }
    fecharFormConta();
    await carregarContas();
  } catch (erro) {
    mostrarErro("erro-conta", erro.message);
  } finally {
    destravar();
  }
});

async function apagarConta(conta) {
  const rotulo = conta.apelido ? `${conta.nome_banco} (${conta.apelido})` : conta.nome_banco;
  const confirmado = await confirmarAcao(`Apagar a conta "${rotulo}"? Isso só é possível se ela não tiver movimentações ou transferências.`);
  if (!confirmado) return;
  try {
    await Api.apagarConta(conta.id);
    await carregarContas();
    toast("Conta apagada.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

// ---------- Transferência entre contas ----------

document.getElementById("btn-abrir-transferencia").addEventListener("click", () => {
  if (contas.length < 2) {
    toast("Cadastre pelo menos duas contas pra poder transferir.", "erro");
    return;
  }
  limparErro("erro-transferencia");
  const form = document.getElementById("form-transferencia");
  form.reset();
  form.elements["data"].value = hojeISO();
  preencherSelectsConta();
  document.getElementById("modal-transferencia").classList.remove("oculto");
});

document.getElementById("btn-cancelar-transferencia").addEventListener("click", () => {
  document.getElementById("modal-transferencia").classList.add("oculto");
});
document.getElementById("modal-transferencia").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-transferencia") {
    document.getElementById("modal-transferencia").classList.add("oculto");
  }
});

document.getElementById("form-transferencia").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-transferencia");
  const dados = new FormData(evento.target);

  const origem = dados.get("conta_origem_id");
  const destino = dados.get("conta_destino_id");
  if (origem === destino) {
    mostrarErro("erro-transferencia", "Escolha duas contas diferentes.");
    return;
  }

  const destravar = travarBotaoEnvio(evento.target);
  try {
    await Api.criarTransferencia({
      conta_origem_id: origem,
      conta_destino_id: destino,
      valor: dados.get("valor"),
      descricao: dados.get("descricao") || null,
      data: dados.get("data"),
    });
    document.getElementById("modal-transferencia").classList.add("oculto");
    await carregarContas();
    await carregarTransferencias();
    toast("Transferência realizada.");
  } catch (erro) {
    mostrarErro("erro-transferencia", erro.message);
  } finally {
    destravar();
  }
});

// ---------- Histórico de transferências ----------

async function carregarTransferencias() {
  let lista;
  try {
    lista = await Api.transferencias();
  } catch (erro) {
    toast(erro.message, "erro");
    return;
  }
  renderizarTransferencias(lista);
}

function renderizarTransferencias(lista) {
  const corpo = document.getElementById("corpo-transferencias");
  const vazio = document.getElementById("transferencias-vazio");
  corpo.innerHTML = "";

  if (lista.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  lista.forEach((transf) => {
    const origem = contaPorId(transf.conta_origem_id);
    const destino = contaPorId(transf.conta_destino_id);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td data-label="Data">${formatarDataBR(transf.data)}</td>
      <td data-label="De"><span class="etiqueta-conta">${escaparHtml(origem?.nome_banco ?? "—")}</span></td>
      <td data-label="Para"><span class="etiqueta-conta">${escaparHtml(destino?.nome_banco ?? "—")}</span></td>
      <td data-label="Descrição">${transf.descricao ? escaparHtml(transf.descricao) : '<span style="color:var(--tinta-suave)">—</span>'}</td>
      <td data-label="Valor" class="alinhar-direita celula-valor">${formatarMoeda(transf.valor)}</td>
    `;
    corpo.appendChild(tr);
  });
}

// ---------- Inicialização ----------

(async function iniciar() {
  await carregarContas();
  await carregarTransferencias();

  // Vem do botão "+ criar conta" do Início (contas.html?criar=1) — abre
  // o formulário direto, sem o usuário precisar procurar "+ nova conta"
  // na página. Limpa o parâmetro da URL pra um refresh não reabrir sozinho.
  if (new URLSearchParams(window.location.search).get("criar")) {
    abrirFormConta();
    window.history.replaceState({}, "", window.location.pathname);
  }
})();