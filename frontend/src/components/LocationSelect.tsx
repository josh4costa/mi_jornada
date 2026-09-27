import { useEffect, useId, useState } from 'react';
import client from '../api/client';
export interface TaskLocation { id: string; group_name: string; name: string; is_active: boolean; revision: number }
export const LOCATION_GROUPS = ['EL POLLO LOCO', 'TACO PALENQUE', 'Otras ubicaciones'];

export default function LocationSelect({value, onChange, legacyName}: {value: string; onChange: (value: string) => void; legacyName?: string}) {
  const id = useId();
  const [items, setItems] = useState<TaskLocation[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const load = () => {
    setLoading(true); setError('');
    client.get<TaskLocation[]>('/locations').then(({data}) => setItems(data)).catch(() => setError('No se pudo cargar el catálogo.')).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const available = items.some(item => item.id === value);
  return <div className="space-y-1">
    <label htmlFor={id} className="block text-sm font-medium">Sucursal relacionada con la tarea *</label>
    <select id={id} required disabled={loading || !!error} className="w-full border border-slate-300 rounded-lg p-3" value={available ? value : ''} onChange={e => onChange(e.target.value)}>
      <option value="">{loading ? 'Cargando sucursales…' : 'Selecciona una sucursal'}</option>
      {LOCATION_GROUPS.map(group => <optgroup key={group} label={group}>{items.filter(item => item.group_name === group).map(item => <option key={item.id} value={item.id}>{group === 'Otras ubicaciones' ? item.name : `${group} · ${item.name}`}</option>)}</optgroup>)}
    </select>
    {!loading && !available && legacyName && <p className="text-xs text-amber-800">Ubicación anterior: {legacyName}. Selecciona una opción vigente del catálogo para guardar.</p>}
    {error && <p role="alert" className="text-sm text-red-700">{error} <button type="button" onClick={load} className="underline">Reintentar</button></p>}
  </div>;
}
