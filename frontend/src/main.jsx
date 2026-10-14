import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
// Fonte servida pelo próprio app (antes vinha do Google Fonts: dependência
// externa, dado de navegação enviado a terceiros e brecha na CSP).
import '@fontsource-variable/plus-jakarta-sans';
import App from './App';
import { AuthProvider } from './auth/AuthContext';
import { ConfirmarProvider } from './components/Confirmar';
import ErrorBoundary from './components/ErrorBoundary';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <ConfirmarProvider>
            <App />
          </ConfirmarProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);
