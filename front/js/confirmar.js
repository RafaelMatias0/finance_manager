/**
 * Substitui o confirm() nativo do navegador por um modal no mesmo estilo
 * do resto do app — o confirm() do navegador é a única caixa de diálogo
 * não-customizada da UI inteira. Cada página que apaga algo (Contas,
 * Controle, Pendências, Planos) inclui o markup do modal (#modal-confirmar)
 * e este script.
 *
 * Uso: `const ok = await confirmarAcao("Apagar X?"); if (!ok) return;`
 *
 * Mantém o que o confirm() nativo já dava de graça: Esc cancela, e o foco
 * abre no botão "Cancelar" (a opção mais segura) — sem isso seria uma
 * regressão de acessibilidade, não só uma troca de estilo.
 */
let resolverConfirmacao = null;

function confirmarAcao(mensagem) {
  const modal = document.getElementById("modal-confirmar");
  if (!modal) {
    // Página sem o modal incluído (não deveria acontecer) — cai pro
    // confirm() nativo como rede de segurança, em vez de travar a ação.
    return Promise.resolve(confirm(mensagem));
  }

  document.getElementById("confirmar-mensagem").textContent = mensagem;
  modal.classList.remove("oculto");
  document.getElementById("btn-confirmar-nao").focus();

  return new Promise((resolve) => {
    resolverConfirmacao = resolve;
  });
}

function fecharConfirmacao(resultado) {
  document.getElementById("modal-confirmar").classList.add("oculto");
  if (resolverConfirmacao) {
    resolverConfirmacao(resultado);
    resolverConfirmacao = null;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("modal-confirmar");
  if (!modal) return;

  document.getElementById("btn-confirmar-sim").addEventListener("click", () => fecharConfirmacao(true));
  document.getElementById("btn-confirmar-nao").addEventListener("click", () => fecharConfirmacao(false));
  modal.addEventListener("click", (evento) => {
    if (evento.target.id === "modal-confirmar") fecharConfirmacao(false);
  });
  document.addEventListener("keydown", (evento) => {
    if (!modal.classList.contains("oculto") && evento.key === "Escape") fecharConfirmacao(false);
  });
});
