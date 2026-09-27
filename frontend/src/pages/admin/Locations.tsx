import { useEffect, useState } from 'react';
import client from '../../api/client';
import Button from '../../components/ui/Button';
import { LOCATION_GROUPS, TaskLocation } from '../../components/LocationSelect';

export default function Locations() {
  const [items, setItems] = useState<TaskLocation[]>([]);
  const [group, setGroup] = useState(LOCATION_GROUPS[0]);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const load = async () => {
    try { setItems((await client.get<TaskLocation[]>('/locations?include_inactive=true')).data); setLoaded(true); }
    catch { setError('No se pudo cargar el catálogo.'); }
  };
  useEffect(() => { void load(); }, []);
  const add = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError('');
    try { await client.post('/locations', {group_name: group, name}); setName(''); await load(); }
    catch (e: any) { setError(e.friendlyMessage || 'No se pudo guardar.'); }
    finally { setBusy(false); }
  };
  const toggle = async (item: TaskLocation) => {
    setBusy(true); setError('');
    try { await client.patch(`/locations/${item.id}`, {is_active: !item.is_active, revision: item.revision}); await load(); }
    catch (e: any) { setError(e.friendlyMessage || 'No se pudo actualizar.'); }
    finally { setBusy(false); }
  };
  return <div className="space-y-6">
    <h1 className="text-2xl font-bold">Sucursales y ubicaciones</h1>
    <p className="text-sm text-slate-600">Las ubicaciones desactivadas dejan de estar disponibles para asignar tareas. Las tareas anteriores conservan su ubicación.</p>
    {error && <p role="alert" className="text-red-700">{error} <button onClick={load} className="underline">Recargar</button></p>}
    <form onSubmit={add} className="bg-white border rounded-lg p-4 space-y-4">
      <h2 className="font-semibold">Agregar ubicación</h2>
      <label className="block">Grupo<select className="block w-full border rounded p-2" value={group} onChange={e => setGroup(e.target.value)}>{LOCATION_GROUPS.map(g => <option key={g}>{g}</option>)}</select></label>
      <label className="block">Nombre<input required maxLength={100} className="block w-full border rounded p-2" value={name} onChange={e => setName(e.target.value)} /></label>
      <Button type="submit" disabled={busy}>Agregar ubicación</Button>
    </form>
    {!loaded && <p>Cargando catálogo…</p>}
    {LOCATION_GROUPS.map(g => <section key={g} className="bg-white border rounded-lg p-4"><h2 className="font-semibold mb-3">{g}</h2><ul className="divide-y">{items.filter(i => i.group_name === g).map(item => <li key={item.id} className="flex items-center justify-between gap-3 py-3"><div>{item.name}<p className="text-xs text-slate-500">{item.is_active ? 'Activa' : 'Inactiva'}</p></div><Button variant="secondary" disabled={busy} onClick={() => toggle(item)}>{item.is_active ? 'Desactivar' : 'Activar'}</Button></li>)}</ul></section>)}
  </div>;
}
