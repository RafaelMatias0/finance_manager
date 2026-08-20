/**
 * Alterna entre tema claro e escuro. O atributo data-tema="escuro" em
 * <html> é o único gatilho — todo o resto (cores, ícones, rótulos) reage
 * via CSS puro (ver style.css). A escolha fica em localStorage e é
 * reaplicada assim que a página carrega, antes do usuário ver qualquer
 * cor (ver o script inline no <head> de cada página).
 */
const TEMA_KEY = "gf_tema";

function aplicarTema(tema) {
  if (tema === "escuro") {
    document.documentElement.setAttribute("data-tema", "escuro");
  } else {
    document.documentElement.removeAttribute("data-tema");
  }
  // Páginas com gráfico (Controle, Relatórios) escutam isso pra re-renderizar
  // com as cores do tema novo — Chart.js não reage sozinho a variável CSS.
  document.dispatchEvent(new CustomEvent("tema-alterado", { detail: { tema } }));
}

function inicializarAlternadorTema() {
  const botao = document.getElementById("btn-alternar-tema");
  if (!botao) return;

  botao.addEventListener("click", () => {
    const estaEscuro = document.documentElement.getAttribute("data-tema") === "escuro";
    const novoTema = estaEscuro ? "claro" : "escuro";
    aplicarTema(novoTema);
    try {
      localStorage.setItem(TEMA_KEY, novoTema);
    } catch (erro) {
      // localStorage indisponível (ex: modo privado) — troca só não persiste.
    }
  });
}

document.addEventListener("DOMContentLoaded", inicializarAlternadorTema);