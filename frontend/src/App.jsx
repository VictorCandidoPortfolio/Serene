import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import Layout from './components/Layout';
import { Carregando } from './components/ui';
import Colecoes from './pages/Colecoes';
import Conhecimento from './pages/Conhecimento';
import Conta from './pages/Conta';
import CriacaoDetalhe from './pages/CriacaoDetalhe';
import Criacoes from './pages/Criacoes';
import Essencias from './pages/Essencias';
import Formulacao from './pages/Formulacao';
import Home from './pages/Home';
import Login from './pages/Login';
import Mapa from './pages/Mapa';
import Perfis from './pages/Perfis';
import RegistrarTeste from './pages/RegistrarTeste';

export default function App() {
  const { user, carregando } = useAuth();

  if (carregando)
    return (
      <div className="tela">
        <Carregando texto="Abrindo seu mapa olfativo…" />
      </div>
    );
  if (!user) return <Login />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="essencias" element={<Essencias />} />
        <Route path="criacoes" element={<Criacoes />} />
        <Route path="criacoes/:id" element={<CriacaoDetalhe />} />
        <Route path="formulacao" element={<Formulacao />} />
        <Route path="perfis" element={<Perfis />} />
        <Route path="colecoes" element={<Colecoes />} />
        <Route path="conta" element={<Conta />} />
        <Route path="mapa" element={<Mapa />} />
        <Route path="conhecimento" element={<Conhecimento />} />
      </Route>
      <Route path="criacoes/:id/teste" element={<RegistrarTeste />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
