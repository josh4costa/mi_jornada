import os

# Patch Workdays.tsx styling to match semantic tokens
p1 = 'frontend/src/pages/admin/Workdays.tsx'
with open(p1, 'r', encoding='utf-8') as f:
    c1 = f.read()
c1 = c1.replace('text-slate-800', 'text-ink')
c1 = c1.replace('text-slate-700', 'text-ink')
c1 = c1.replace('text-slate-600', 'text-muted')
c1 = c1.replace('text-slate-500', 'text-muted')
c1 = c1.replace('text-slate-400', 'text-muted')
c1 = c1.replace('bg-slate-100', 'bg-ground')
c1 = c1.replace('bg-slate-50', 'bg-surface')
c1 = c1.replace('bg-white', 'bg-surface')
with open(p1, 'w', encoding='utf-8') as f:
    f.write(c1)

# Patch Technicians.tsx to display true completion time rather than scheduled DB defaults
p2 = 'frontend/src/pages/admin/Technicians.tsx'
with open(p2, 'r', encoding='utf-8') as f:
    c2 = f.read()
old_task_time = '{task.scheduled_time && <span className="text-xs text-muted bg-ground px-2 py-1 rounded">{task.scheduled_time}</span>}'
new_task_time = '{task.completed_at ? <span className="text-xs font-mono text-muted bg-ground px-2 py-1 rounded">{formatTime(task.completed_at)}</span> : (task.scheduled_time && <span className="text-xs font-mono text-muted bg-ground px-2 py-1 rounded">{task.scheduled_time}</span>)}'
c2 = c2.replace(old_task_time, new_task_time)
with open(p2, 'w', encoding='utf-8') as f:
    f.write(c2)
