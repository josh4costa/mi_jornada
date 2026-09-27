import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { Home, Clock, Calendar, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

const TechnicianLayout: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const getInitials = (name?: string) => {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
  };

  return (
    <div className="flex flex-col min-h-screen bg-bg">
      {/* Top bar */}
      <header className="bg-primary text-white p-4 shadow-md sticky top-0 z-40 flex items-center justify-between">
        <h1 className="text-xl font-bold">Mi Jornada</h1>
        <button 
          onClick={() => navigate('/perfil')}
          className="w-10 h-10 rounded-full bg-primary-dark flex items-center justify-center border-2 border-white/20 overflow-hidden"
          title="Mi Perfil"
        >
          <span className="text-sm font-bold">{getInitials(user?.full_name)}</span>
        </button>
      </header>

      {/* Main content area - takes remaining height and enables scrolling */}
      <main className="flex-1 overflow-y-auto pb-20">
        <div className="p-4 max-w-lg mx-auto">
          <Outlet />
        </div>
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 flex justify-around items-center h-[72px] pb-safe z-40 shadow-[0_-4px_6px_-1px_rgb(0,0,0,0.05)]">
        <NavLink 
          to="/" 
          end
          className={({ isActive }) => `flex flex-col items-center justify-center w-full h-full space-y-1 ${isActive ? 'text-primary' : 'text-muted'}`}
        >
          <Home className="w-6 h-6" />
          <span className="text-xs font-medium">Inicio</span>
        </NavLink>
        <NavLink 
          to="/historial" 
          className={({ isActive }) => `flex flex-col items-center justify-center w-full h-full space-y-1 ${isActive ? 'text-primary' : 'text-muted'}`}
        >
          <Clock className="w-6 h-6" />
          <span className="text-xs font-medium">Historial</span>
        </NavLink>
        <NavLink to="/ausencias" className={({ isActive }) => `flex flex-col items-center justify-center w-full h-full space-y-1 ${isActive ? 'text-primary' : 'text-muted'}`}><Calendar className="w-6 h-6" /><span className="text-xs font-medium">Ausencias</span></NavLink>
        <NavLink 
          to="/perfil" 
          className={({ isActive }) => `flex flex-col items-center justify-center w-full h-full space-y-1 ${isActive ? 'text-primary' : 'text-muted'}`}
        >
          <UserIcon className="w-6 h-6" />
          <span className="text-xs font-medium">Perfil</span>
        </NavLink>
      </nav>
    </div>
  );
};

export default TechnicianLayout;
