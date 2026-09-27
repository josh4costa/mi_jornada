import { useEffect, useRef, useState } from 'react';
import client from '../../api/client';
import { User, UserRole } from '../../types';
import { useAuthStore } from '../../store/authStore';
import Modal from '../ui/Modal';

interface Props {
  isOpen: boolean;
  person: User | null;
  onClose: () => void;
  onSaved: () => void;
}
const empty = { full_name: '', username: '', email: '', password: '', role: 'TECHNICIAN' as UserRole, is_active: true, employee_number: '', phone: '', reminders_enabled: false };

export default function PersonEditor({ isOpen, person, onClose, onSaved }: Props) {
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const formRef = useRef<HTMLFormElement>(null);
  const currentUser = useAuthStore(state => state.user);
  const ownAccount = !!person && person.id === currentUser?.id;
  useEffect(() => {
    if (!isOpen) return;
    setForm(person ? { full_name: person.full_name, username: person.username, email: person.email, role: person.role, is_active: person.is_active, password: '', employee_number: person.technician?.employee_number || '', phone: person.technician?.phone || '', reminders_enabled: person.technician?.reminders_enabled || false } : { ...empty });
    setError('');
  }, [isOpen, person]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError('');
    const payload: Record<string, string | boolean | null> = {};
    for (const key of ['full_name', 'username', 'email', 'role', 'is_active'] as const) {
      const value = typeof form[key] === 'string' ? (form[key] as string).trim() : form[key];
      if (!person || value !== person[key]) payload[key] = value;
    }
    if (form.password) payload.password = form.password;
    if (form.role === 'TECHNICIAN') {
      if (!person || form.reminders_enabled !== !!person.technician?.reminders_enabled) payload.reminders_enabled = form.reminders_enabled;
      for (const key of ['phone', 'employee_number'] as const) {
        const value = form[key].trim() || null;
        if (!person || value !== (person.technician?.[key] ?? null)) payload[key] = value;
      }
    }
    try {
      const { data } = person
        ? await client.patch<User>(`/admin/users/${person.id}`, payload)
        : await client.post<User>('/admin/users', payload);
      if (ownAccount) useAuthStore.setState({ user: { ...currentUser!, ...data } });
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err.friendlyMessage || 'No se pudieron guardar los cambios. Intenta de nuevo.');
    } finally { setSaving(false); }
  }
  const inputClass = 'w-full border border-border rounded-lg p-2 mt-1 bg-white disabled:bg-ground';
  return <Modal isOpen={isOpen} title={person ? 'Editar persona' : 'Agregar persona'} onClose={onClose} onConfirm={() => formRef.current?.requestSubmit()} confirmText="Guardar" loading={saving}>
    <form ref={formRef} onSubmit={save}>
      <fieldset disabled={saving} className="space-y-4 py-2">
        {error && <p role="alert" className="text-red-700">{error}</p>}
        <label className="block">Nombre completo<input className={inputClass} required maxLength={150} value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} /></label>
        <label className="block">Usuario<input className={inputClass} required maxLength={50} autoCapitalize="none" autoComplete="off" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></label>
        <label className="block">Correo electrónico<input className={inputClass} required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label>
        <p className="text-xs text-slate-500">Al crear o restablecer el acceso, la persona debe elegir su contraseña personal en el próximo ingreso. Usa un correo al que tenga acceso para recuperación.</p>
        <label className="block">{person ? 'Restablecer con contraseña temporal (opcional)' : 'Contraseña temporal'}<input className={inputClass} type="password" required={!person} minLength={8} maxLength={72} autoComplete="new-password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></label>
        {person && <p className="text-sm text-muted">Deja la contraseña vacía para conservar la actual.</p>}
        <label className="block">Rol<select className={inputClass} disabled={ownAccount} value={form.role} onChange={e => setForm({ ...form, role: e.target.value as UserRole })}><option value="TECHNICIAN">Técnico</option><option value="READ_ONLY">Solo lectura</option><option value="ADMIN">Administrador</option></select></label>
        {form.role === 'TECHNICIAN' && <div className="border-t border-border pt-4 space-y-4">
          <p className="font-semibold">Datos del técnico</p>
          <label className="block">Número de empleado<input className={inputClass} maxLength={30} value={form.employee_number} onChange={e => setForm({ ...form, employee_number: e.target.value })} /></label>
          <label className="block">Teléfono de WhatsApp<input placeholder="+528112345678" className={inputClass} type="tel" maxLength={20} value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /></label>
          <label className="flex gap-2 items-center"><input type="checkbox" checked={form.reminders_enabled} onChange={e => setForm({ ...form, reminders_enabled: e.target.checked })} />Enviar recordatorios por WhatsApp</label>
          <p className="text-sm text-muted">Lun–vie 9:00–18:00 · Sáb 9:00–13:00. Avisos a las 9:10 y diez minutos después de la salida, si falta el registro. Domingos y ausencias aprobadas sin avisos.</p>
        </div>}
        <label className="flex items-center gap-2"><input type="checkbox" disabled={ownAccount} checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} />Cuenta activa</label>
        {ownAccount && <p className="text-sm text-muted">Tu rol y estado deben ser modificados por otro administrador.</p>}
      </fieldset>
    </form>
  </Modal>;
}
