import { Component } from 'react';

/**
 * Rede de segurança da interface: sem isto, qualquer erro durante a
 * renderização deixava a tela inteira em branco, sem explicação.
 * Mostra uma mensagem e um botão para recarregar.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { erro: null };
  }

  static getDerivedStateFromError(erro) {
    return { erro };
  }

  componentDidCatch(erro, info) {
    // Fica no console do navegador para depuração; nada é enviado a terceiros.
    console.error('[Sérené] erro na interface:', erro, info?.componentStack);
  }

  render() {
    if (!this.state.erro) return this.props.children;
    return (
      <div className="tela tela-erro" role="alert">
        <div className="vazio">
          <strong>Algo deu errado nesta tela.</strong>
          <p>Seus dados estão salvos. Recarregue a página para continuar.</p>
          <button className="btn btn-primario" onClick={() => window.location.reload()}>
            Recarregar
          </button>
        </div>
      </div>
    );
  }
}
