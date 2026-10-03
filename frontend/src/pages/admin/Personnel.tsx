import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Plus, Search, Pencil, ArrowRight, Phone, BadgeCheck } from 'lucide-react';
import client from '../../api/client';
import { User } from '../../types';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import Spinner from '../../components/ui/Spinner';
import PersonEditor from '../../components/admin/PersonEditor';
import Modal from '../../components/ui/Modal';

export default function Personnel() {
  const [params, setParams] = useSearchParams();
  const role = ['ADMIN', 'TECHNICIAN', 'READ_ONLY'].includes(params.get('rol') || '') ? params.get('rol')! : '';
  const [people, setPeople] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState<User | null>(null);
  const [open, setOpen] = useState(false);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [removal, setRemoval] = useState<User | null>(null);
  const [reason, setReason] = useState('');
  const [removalError, setRemovalError] = useState('');
  const [saving, setSaving] = useState(false);
  const sequence = useRef(0);
  const load = useCallback(async () => {
    const id = ++sequence.current;
    setLoading(true);
    setError('');
    try {
      const { data } = await client.get('/admin/users', { params: { role: role || undefined, search: query, page, size: 20, include_deleted: includeDeleted } });
      if (id !== sequence.current) return;
      const last = Math.max(1, data.pages);
      if (page > last) { setPage(last); return; }
      setPeople(data.items); setPages(last); setTotal(data.total);
    } catch (err: any) {
      if (id === sequence.current) setError(err.friendlyMessage || 'No se pudo cargar el personal.');
    } finally { if (id === sequence.current) setLoading(false); }
  }, [role, page, query, includeDeleted]);
  async function confirmRemoval() {
    if (!removal || saving) return;
    if (reason.trim().length < 3) { setRemovalError('Indica un motivo de al menos 3 caracteres.'); return; }
    setSaving(true); setRemovalError('');
    try {
      await client.post(`/admin/users/${removal.id}/${removal.deleted_at ? 'restore' : 'delete'}`, { reason: reason.trim() });
      setNotice(removal.deleted_at ? 'Técnico restaurado como inactivo. Puedes activar su acceso desde Editar.' : 'Técnico eliminado. Su historial se conserva y su acceso quedó bloqueado.');
      setRemoval(null); void load();
    } catch (err: any) { setRemovalError(err.friendlyMessage || 'No se pudo guardar el cambio.'); }
    finally { setSaving(false); }
  }
  useEffect(() => { void load(); return () => { sequence.current++; }; }, [load]);
  const filters = [{ value: '', label: 'Todos' }, { value: 'TECHNICIAN', label: 'Técnicos' }, { value: 'ADMIN', label: 'Administradores' }, { value: 'READ_ONLY', label: 'Solo lectura' }];
  return <div className="space-y-6 max-w-6xl mx-auto">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-2xl font-bold">Personal</h1><p className="text-muted mt-1">Administra los datos y el acceso de cada persona.</p></div>
      <Button onClick={() => { setEditing(null); setOpen(true); }}><Plus className="w-4 h-4 mr-2" />Agregar persona</Button>
    </div>
    <div className="flex flex-wrap gap-2" aria-label="Filtrar personal por rol">
      {filters.map(filter => <Button key={filter.value} variant={role === filter.value ? 'primary' : 'secondary'} aria-pressed={role === filter.value} onClick={() => { setPage(1); setParams(filter.value ? { rol: filter.value } : {}); }}>{filter.label}</Button>)}
    </div>
    <form className="flex gap-2" onSubmit={event => { event.preventDefault(); setPage(1); setQuery(search.trim()); }}>
      <input aria-label="Buscar personal" className="flex-1 min-w-0 border border-border rounded-lg p-2" placeholder="Nombre, usuario o correo" value={search} onChange={e => setSearch(e.target.value)} />
      <Button type="submit" variant="secondary"><Search className="w-4 h-4 mr-2" />Buscar</Button>
    </form>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={includeDeleted} onChange={e => { setPage(1); setIncludeDeleted(e.target.checked); }} />Mostrar también técnicos eliminados</label>
    {notice && <p role="status" className="text-green-800">{notice}</p>}
    {error && <div role="alert" className="text-red-700 flex gap-3 items-center"><p>{error}</p><Button variant="secondary" onClick={load}>Reintentar</Button></div>}
    {loading ? <div className="p-12 flex justify-center"><Spinner /></div> : <>
      <p className="text-sm text-muted" aria-live="polite">{total} {total === 1 ? 'persona' : 'personas'}</p>
      <div className="grid gap-4 lg:grid-cols-2">
        {people.map(person => <Card key={person.id} className="space-y-4">
          <div className="flex justify-between gap-3"><div className="min-w-0"><h2 className="font-semibold break-words">{person.full_name}</h2><p className="text-sm text-muted break-all">@{person.username} · {person.email}</p></div><div className="shrink-0"><Badge type="active" value={person.is_active} /></div></div>
          <Badge type="role" value={person.role} />
          {person.deleted_at && <p className="text-sm font-semibold text-red-700">Eliminado · historial conservado</p>}
          {person.technician && <div className="text-sm text-muted space-y-1"><p className="flex gap-2 items-center"><BadgeCheck className="w-4 h-4" />{person.technician.employee_number || 'Sin número de empleado'}</p><p className="flex gap-2 items-center"><Phone className="w-4 h-4" />{person.technician.phone || 'Sin teléfono'}</p></div>}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border">
            {!person.deleted_at && <Button variant="secondary" aria-label={`Editar a ${person.full_name}`} onClick={() => { setEditing(person); setOpen(true); }}><Pencil className="w-4 h-4 mr-2" />Editar</Button>}
            {person.role === 'TECHNICIAN' && <Button variant={person.deleted_at ? 'secondary' : 'danger'} aria-label={`${person.deleted_at ? 'Restaurar' : 'Eliminar'} a ${person.full_name}`} onClick={() => { setRemoval(person); setReason(''); setRemovalError(''); }}>{person.deleted_at ? 'Restaurar' : 'Eliminar técnico'}</Button>}
            {person.technician && <Link className="text-sm font-medium inline-flex items-center gap-1 underline" to={`/admin/personal/tecnico/${person.technician.id}`}>Jornada y tareas<ArrowRight className="w-4 h-4" /></Link>}
          </div>
        </Card>)}
      </div>
      {!people.length && !error && <p className="p-8 text-center text-muted">No hay personas que coincidan con los filtros.</p>}
    </>}
    <div className="flex items-center justify-between gap-2" aria-label="Paginación de personal"><Button variant="secondary" disabled={loading || page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button><span>{page} / {pages}</span><Button variant="secondary" disabled={loading || page >= pages} onClick={() => setPage(page + 1)}>Siguiente</Button></div>
    <PersonEditor isOpen={open} person={editing} onClose={() => setOpen(false)} onSaved={() => { setNotice('Datos guardados correctamente.'); void load(); }} />
    <Modal isOpen={!!removal} title={removal?.deleted_at ? 'Restaurar técnico' : 'Eliminar técnico'} onClose={() => { if (!saving) setRemoval(null); }} onConfirm={confirmRemoval} confirmText={removal?.deleted_at ? 'Restaurar técnico' : 'Eliminar técnico'} confirmVariant={removal?.deleted_at ? 'primary' : 'danger'} loading={saving}>
      <div className="space-y-4">
        <p><strong>{removal?.full_name}</strong></p>
        <p>{removal?.deleted_at ? 'Se restaurará como inactivo. Después podrás activar su acceso y configurar sus recordatorios desde Editar.' : 'Se bloqueará su acceso, se desactivarán sus recordatorios y dejará de aparecer en la lista habitual. Sus jornadas, tareas y reportes históricos se conservan. Si tiene una jornada abierta, primero debes cerrarla o anularla.'}</p>
        <label className="block">Motivo<textarea aria-label="Motivo del cambio" className="mt-1 w-full border border-border rounded-lg p-2" value={reason} onChange={e => setReason(e.target.value)} maxLength={1000} disabled={saving} /></label>
        {removalError && <p role="alert" className="text-red-700">{removalError}</p>}
      </div>
    </Modal>
  </div>;
}
