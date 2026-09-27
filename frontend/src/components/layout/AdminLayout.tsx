import React, { useEffect, useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Users, ClipboardList, Calendar, BarChart2, Menu, X, LogOut } from 'lucide-react';
import client from '../../api/client';
import { useAuth } from '../../hooks/useAuth';

const AdminLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [pending, setPending] = useState(0);
  useEffect(() => {
    let active = true;
    const refresh = () => client.get('/attendance/summary').then(({ data }) => { if (active) setPending((data.incidents || 0) + (data.leaves || 0) + (data.nights || 0)); }).catch(() => {});
    void refresh();
    const interval = window.setInterval(refresh, 60000);
    return () => { active = false; window.clearInterval(interval); };
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/admin', icon: LayoutDashboard, label: 'Operación', end: true },
    { to: '/admin/personal', icon: Users, label: 'Personal' },
    { to: '/admin/tareas', icon: ClipboardList, label: 'Tareas' },
    { to: '/admin/jornadas', icon: Calendar, label: 'Jornadas' },
    { to: '/admin/asistencia', icon: Calendar, label: `Ausencias y asistencia${pending ? ` (${pending})` : ''}` },
    { to: '/admin/reportes', icon: BarChart2, label: 'Reportes' },
    { to: '/admin/sucursales', icon: ClipboardList, label: 'Sucursales' },
    { to: '/mi-cuenta', icon: Users, label: 'Mi cuenta' },
  ].filter(item => user?.role === 'ADMIN' || !['/admin/personal', '/admin/sucursales'].includes(item.to));

  return (
    <div className="flex h-screen bg-ground font-sans text-ink">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-64 bg-shell text-surface h-full z-20">
        <div className="p-6">
          <h1 className="text-xl font-bold tracking-tight">Mi Jornada</h1>
          <p className="text-sm text-muted mt-1">Panel de operación</p>
        </div>
        <nav className="flex-1 space-y-1 mt-4">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => 
                `flex items-center gap-3 py-3 transition-colors ${
                  isActive 
                    ? 'bg-shell-2 text-surface font-medium border-l-[3px] border-accent pl-[21px] pr-4' 
                    : 'text-muted hover:bg-shell-2 hover:text-surface border-l-[3px] border-transparent pl-[21px] pr-4'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-shell-2">
          <div className="flex items-center gap-3 mb-4 px-2 text-sm">
            <div className="w-8 h-8 rounded-full bg-shell-2 flex items-center justify-center font-bold text-muted">
              {user?.full_name?.charAt(0).toUpperCase() || 'A'}
            </div>
            <div className="truncate flex-1">
              <p className="font-medium truncate text-surface">{user?.full_name}</p>
              <p className="text-xs text-muted truncate">{user?.email}</p>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-4 py-2 text-sm text-muted hover:text-surface hover:bg-shell-2 rounded-btn transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </aside>

      {/* Mobile Header & Sidebar overlay */}
      <div className="md:hidden">
        {sidebarOpen && (
          <div className="fixed inset-0 bg-ink/50 z-30" onClick={() => setSidebarOpen(false)} />
        )}
        <div className={`fixed inset-y-0 left-0 w-64 bg-shell text-surface z-40 transform transition-transform duration-300 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
          <div className="flex items-center justify-between p-6">
            <h1 className="text-xl font-bold tracking-tight">Mi Jornada</h1>
            <button onClick={() => setSidebarOpen(false)} className="text-muted hover:text-surface p-1">
              <X className="w-6 h-6" />
            </button>
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) => 
                  `flex items-center gap-3 py-3 ${
                    isActive 
                      ? 'bg-shell-2 text-surface font-medium border-l-[3px] border-accent pl-[21px] pr-4' 
                      : 'text-muted border-l-[3px] border-transparent pl-[21px] pr-4'
                  }`
                }
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="absolute bottom-0 w-full p-4 border-t border-shell-2">
            <button 
              onClick={handleLogout}
              className="flex items-center justify-center gap-2 w-full px-4 py-3 bg-shell-2 hover:bg-shell-2/80 text-surface rounded-btn"
            >
              <LogOut className="w-5 h-5" />
              <span>Cerrar sesión</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="md:hidden bg-surface shadow-sm h-16 flex items-center justify-between px-4 z-10 border-b border-border">
          <button onClick={() => setSidebarOpen(true)} className="p-2 text-ink">
            <Menu className="w-6 h-6" />
          </button>
          <h1 className="text-lg font-bold text-ink">Mi Jornada</h1>
          <div className="w-8 h-8 rounded-full bg-shell-2 flex items-center justify-center text-muted font-bold">
            {user?.full_name?.charAt(0).toUpperCase() || 'A'}
          </div>
        </header>
        <main className="flex-1 overflow-y-auto bg-ground p-4 md:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;
