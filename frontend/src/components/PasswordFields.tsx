import { useState } from 'react';

export default function PasswordFields({password, confirm, onPassword, onConfirm}: {password: string; confirm: string; onPassword: (value: string) => void; onConfirm: (value: string) => void}) {
  const [show, setShow] = useState(false);
  return <>
    <label className="block text-sm">Nueva contraseña<input autoComplete="new-password" required minLength={12} maxLength={72} type={show ? 'text' : 'password'} className="block w-full border rounded-lg p-3 mt-1" value={password} onChange={e => onPassword(e.target.value)} /></label>
    <p className="text-xs text-slate-500">Usa al menos 12 caracteres. Puedes elegir una frase que recuerdes y que no uses en otros sitios.</p>
    <label className="block text-sm">Confirmar nueva contraseña<input autoComplete="new-password" required minLength={12} maxLength={72} type={show ? 'text' : 'password'} className="block w-full border rounded-lg p-3 mt-1" value={confirm} onChange={e => onConfirm(e.target.value)} /></label>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={show} onChange={e => setShow(e.target.checked)} />Mostrar nueva contraseña</label>
  </>;
}
