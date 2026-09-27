import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import client from '../api/client';
import Button from '../components/ui/Button';
import PasswordFields from '../components/PasswordFields';

export default function Account() {
  const {user, logout} = useAuthStore();
  const navigate = useNavigate();
  const [changing, setChanging] = useState(false);
  const showPassword = !!user?.must_change_password || changing;
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    if (password !== confirm) { setError('Las contraseñas no coinciden.'); return; }
    setBusy(true);
    try {
      await client.post('/auth/change-password', {current_password: current, new_password: password});
      sessionStorage.setItem('mi-jornada-password-updated', '1');
      logout(); navigate('/login', {replace: true});
    } catch (e: any) { setError(e.friendlyMessage || 'No se pudo cambiar la contraseña.'); }
    finally { setBusy(false); }
  };
  return <main className="min-h-screen bg-slate-50 p-4 flex justify-center items-start sm:pt-12"><section className="w-full max-w-lg bg-white border rounded-xl p-6 space-y-4">
    <h1 className="text-2xl font-bold">{user?.must_change_password ? 'Establece tu contraseña personal' : 'Mi cuenta'}</h1>
    <p className="text-slate-600">{user?.full_name} · {user?.email}</p>
    <p className="text-sm">{user?.must_change_password ? 'Antes de continuar, cambia tu contraseña actual o temporal por una que solo tú conozcas.' : showPassword ? 'Al guardar la contraseña se cerrarán tus sesiones para que ingreses con la nueva.' : 'Consulta tus datos de acceso. Para corregir tus datos, contacta al administrador.'}</p>
    {!showPassword && <div className="space-y-3 rounded-lg bg-slate-50 p-4"><p><strong>Nombre:</strong> {user?.full_name}</p><p><strong>Usuario:</strong> {user?.username}</p><p><strong>Correo:</strong> {user?.email}</p><p><strong>Rol:</strong> {user?.role === 'ADMIN' ? 'Administrador' : user?.role === 'READ_ONLY' ? 'Solo lectura' : 'Técnico'}</p><Button onClick={() => setChanging(true)}>Cambiar contraseña</Button></div>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {showPassword && <form onSubmit={submit} className="space-y-4">
      <label className="block text-sm">Contraseña actual o temporal<input required type="password" autoComplete="current-password" className="block w-full border rounded-lg p-3 mt-1" value={current} onChange={e => setCurrent(e.target.value)} /></label>
      <PasswordFields password={password} confirm={confirm} onPassword={setPassword} onConfirm={setConfirm} />
      <Button fullWidth type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Guardar contraseña'}</Button>
    </form>}
    {showPassword && <Link className="block text-blue-700" to="/recuperar-contrasena">Olvidé mi contraseña</Link>}
    {changing && !user?.must_change_password && <Button variant="secondary" onClick={() => {setChanging(false); setCurrent(''); setPassword(''); setConfirm(''); setError('');}}>Cancelar cambio</Button>}
    {!user?.must_change_password && <Link className="block text-blue-700" to={user?.role !== 'TECHNICIAN' ? '/admin' : '/perfil'}>Volver</Link>}
    <Button variant="secondary" onClick={() => {logout(); navigate('/login');}}>Cerrar sesión</Button>
  </section></main>;
}
