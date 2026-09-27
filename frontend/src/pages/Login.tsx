import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Briefcase, User as UserIcon, Lock, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { authApi } from '../api/client';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import { useOnlineStatus } from '../hooks/useOnlineStatus';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();
  const [passwordUpdated] = useState(() => sessionStorage.getItem('mi-jornada-password-updated') === '1');
  useEffect(() => { sessionStorage.removeItem('mi-jornada-password-updated'); }, []);
  const { login, isAuthenticated, user } = useAuthStore();
  const { isOnline } = useOnlineStatus();

  useEffect(() => {
    if (isAuthenticated && user) {
      if (user.must_change_password) { navigate('/mi-cuenta', {replace: true}); return; }
      if (user.role !== 'TECHNICIAN') {
        navigate('/admin', { replace: true });
      } else {
        navigate('/', { replace: true });
      }
    }
  }, [isAuthenticated, user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username || !password) {
      setError('Por favor, ingresa tu usuario y contraseña.');
      return;
    }

    if (!isOnline) {
      setError('Sin conexión a Internet. Verifica tu red e inténtalo de nuevo.');
      return;
    }

    setLoading(true);

    try {
      const response = await authApi.login(username, password);
      login(response.user, response.access_token, response.refresh_token, rememberMe);
      
      if (response.user.must_change_password) { navigate('/mi-cuenta', {replace: true}); return; }
      if (response.user.role !== 'TECHNICIAN') {
        navigate('/admin', { replace: true });
      } else {
        navigate('/', { replace: true });
      }
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError('Usuario o contraseña incorrectos. Inténtalo de nuevo.');
      } else if (err.response?.status === 423) {
        setError('Cuenta bloqueada temporalmente. Espera 15 minutos.');
      } else {
        setError(err.friendlyMessage || 'No pudimos iniciar sesión. Inténtalo de nuevo.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ground flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-shell rounded-full mb-6 shadow-sm">
            <Briefcase className="w-10 h-10 text-accent" />
          </div>
          <h1 className="text-4xl font-bold text-ink mb-2 tracking-tight">Mi Jornada</h1>
          <p className="text-muted text-lg">Control de Jornada Diaria</p>
        </div>

        <Card className="px-6 py-8">
          {passwordUpdated && <p role="status" className="mb-4 text-green-800">Contraseña guardada. Ingresa con tu nueva contraseña.</p>}
          {error && (
            <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="login-username" className="block text-sm font-medium text-slate-700 mb-2">
                Usuario o correo electrónico
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <UserIcon className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  id="login-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-primary sm:text-base outline-none transition-shadow"
                  autoComplete="username"
                  disabled={loading}
                  autoCapitalize="none"
                  autoCorrect="off"
                />
              </div>
            </div>

            <div>
              <label htmlFor="login-password" className="block text-sm font-medium text-slate-700 mb-2">
                Contraseña
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full pl-10 pr-12 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-primary sm:text-base outline-none transition-shadow"
                  autoComplete="current-password"
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 focus:outline-none"
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center">
              <input
                id="remember-me"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="h-5 w-5 text-primary focus:ring-primary border-slate-300 rounded rounded-md"
                disabled={loading}
              />
              <label htmlFor="remember-me" className="ml-2 block text-sm text-slate-700">
                Mantener sesión iniciada
              </label>
            </div>

            <Button
              type="submit"
              variant="primary"
              fullWidth
              loading={loading}
            >
              INICIAR SESIÓN
            </Button>
          </form>
          <Link className="block text-center text-blue-700 mt-5" to="/recuperar-contrasena">Olvidé mi contraseña</Link>
        </Card>
        
        <p className="text-center text-sm text-muted mt-8">
          © {new Date().getFullYear()} Mi Jornada. Todos los derechos reservados.
        </p>
      </div>
    </div>
  );
};

export default Login;
