const formatadorMoeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function formatarMoeda(valor) {
  return formatadorMoeda.format(Number(valor));
}

function formatarDataBR(isoDate) {
  const [ano, mes, dia] = isoDate.split("-");
  return `${dia}/${mes}/${ano}`;
}

function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

function toast(mensagem, tipo = "sucesso") {
  const regiao = document.getElementById("regiao-toast");
  const el = document.createElement("div");
  el.className = "toast" + (tipo === "erro" ? " toast--erro" : "");
  el.textContent = mensagem;
  regiao.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function mostrarErro(elementoId, mensagem) {
  const el = document.getElementById(elementoId);
  el.textContent = mensagem;
  el.classList.add("is-visivel");
}

function limparErro(elementoId) {
  const el = document.getElementById(elementoId);
  el.textContent = "";
  el.classList.remove("is-visivel");
}
