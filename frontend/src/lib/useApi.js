import { useCallback, useEffect, useState } from 'react';

/**
 * Carrega dados de uma função assíncrona e expõe { data, error, loading, reload }.
 * `deps` funciona como no useEffect: quando mudam, a carga é refeita.
 */
export function useApi(loader, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    let vivo = true;
    setLoading(true);
    setError(null);
    loader()
      .then((d) => vivo && setData(d))
      .catch((e) => vivo && setError(e))
      .finally(() => vivo && setLoading(false));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, versao]);

  const reload = useCallback(() => setVersao((v) => v + 1), []);
  return { data, error, loading, reload, setData };
}
