import React from 'react';
import { TaskStatus, TaskPriority } from '../../types';

interface StateBadgeProps {
  type: 'status' | 'priority' | 'role' | 'active';
  value: TaskStatus | TaskPriority | string | boolean;
  className?: string;
}

type BadgeProps = StateBadgeProps | {
  variant: 'success' | 'warning' | 'secondary' | 'danger';
  children: React.ReactNode;
  className?: string;
};

const Badge: React.FC<BadgeProps> = (props) => {
  if ('variant' in props) {
    const colors = { success: 'bg-green-100 text-green-800', warning: 'bg-amber-100 text-amber-800', secondary: 'bg-slate-200 text-slate-800', danger: 'bg-red-100 text-red-800' };
    return <span className={`px-2 py-1 rounded-full text-xs font-semibold inline-flex items-center ${colors[props.variant]} ${props.className || ''}`}>{props.children}</span>;
  }
  const { type, value, className = '' } = props;
  let styles = 'px-2 py-1 rounded-full text-xs font-semibold inline-flex items-center';
  let text = String(value);

  if (type === 'status') {
    if (value === 'PENDING') {
      styles += ' bg-slate-200 text-slate-800';
      text = 'PENDIENTE';
    } else if (value === 'COMPLETED') {
      styles += ' bg-green-100 text-green-800';
      text = 'COMPLETADO';
    } else if (value === 'CANCELLED') {
      styles += ' bg-red-100 text-red-800';
      text = 'CANCELADO';
    }
  } else if (type === 'priority') {
    if (value === 'HIGH') {
      styles += ' bg-amber-100 text-amber-800';
      text = 'ALTA';
    } else {
      styles += ' bg-slate-100 text-slate-700';
      text = 'NORMAL';
    }
  } else if (type === 'role') {
    if (value === 'ADMIN') {
      styles += ' bg-blue-100 text-blue-800';
      text = 'ADMIN';
    } else if (value === 'READ_ONLY') {
      styles += ' bg-slate-100 text-slate-700'; text = 'SOLO LECTURA';
    } else {
      styles += ' bg-teal-100 text-teal-800';
      text = 'TÉCNICO';
    }
  } else if (type === 'active') {
    if (value === true || value === 'true') {
      styles += ' bg-green-100 text-green-800';
      text = 'Activo';
    } else {
      styles += ' bg-slate-200 text-slate-800';
      text = 'Inactivo';
    }
  }

  return (
    <span className={`${styles} ${className}`}>
      {text}
    </span>
  );
};

export default Badge;
