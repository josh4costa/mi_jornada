import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import client from '../api/client';
import { useAuthStore } from '../store/authStore';
import Button from '../components/ui/Button';
import PasswordFields from '../components/PasswordFields';

export default function PasswordRecovery() {
  const [token, setToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [done, setDone] = useState(false);
  useEffect(() => { if (window.location.hash) window.history.replaceState(null, '', window.location.pathname); }, []);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setMessage('');
    if (token && password !== confirm) { setError('Las contraseñas no coinciden.'); return; }
    setBusy(true);
    try {
      const {data} = await client.post(token ? '/auth/reset-password' : '/auth/forgot-password', token ? {token, new_password: password} : {email});
      setMessage(data.message);
      if (token) { useAuthStore.getState().logout(); setToken(''); setDone(true); }
    } catch (e: any) { setError(e.friendlyMessage || 'No se pudo procesar la solicitud.'); }
    finally { setBusy(false); }
  };
  return <main className="min-h-screen bg-slate-50 p-4 flex justify-center sm:pt-12"><section className="w-full max-w-lg bg-white border rounded-xl p-6 space-y-4 self-start">
    <h1 className="text-2xl font-bold">Recuperar contraseña</h1>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {!done && <form onSubmit={submit} className="space-y-4">
      {token ? <PasswordFields password={password} confirm={confirm} onPassword={setPassword} onConfirm={setConfirm} /> : <>
        <p className="text-sm">Escribe el correo registrado en tu cuenta. Recibirás un enlace válido por 30 minutos. Si no tienes acceso a ese correo, solicita al administrador una contraseña temporal.</p>
        <label className="block text-sm">Correo electrónico<input type="email" required autoComplete="email" className="block w-full border rounded-lg p-3 mt-1" value={email} onChange={e => setEmail(e.target.value)} /></label>
      </>}
      <Button type="submit" fullWidth disabled={busy}>{busy ? 'Procesando…' : token ? 'Guardar nueva contraseña' : 'Solicitar enlace'}</Button>
    </form>}
    {token && <button className="text-blue-700" onClick={() => {setToken(''); setError('');}}>Solicitar otro enlace</button>}
    <Link className="block text-blue-700" to="/login">Volver al inicio de sesión</Link>
  </section></main>;
}
