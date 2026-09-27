import React from 'react';
import { Link } from 'react-router-dom';
import { LogOut, User as UserIcon, Mail, Hash } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';

const Profile: React.FC = () => {
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
  };

  const getInitials = (name?: string) => {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
  };

  return (
    <div className="space-y-6 animate-in fade-in">
      <h1 className="text-2xl font-bold text-slate-800">Mi Perfil</h1>

      <Card className="flex flex-col items-center pt-8 pb-6">
        <div className="w-24 h-24 rounded-full bg-primary-dark flex items-center justify-center text-white text-3xl font-bold mb-4 shadow-md">
          {getInitials(user?.full_name)}
        </div>
        <h2 className="text-xl font-bold text-slate-800">{user?.full_name}</h2>
        <p className="text-slate-500 mb-3">@{user?.username}</p>
        <Badge type="role" value={user?.role || 'TECHNICIAN'} />
      </Card>

      <div className="space-y-4">
        <Card>
          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Información Personal</h3>
          
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center shrink-0">
                <UserIcon className="w-5 h-5 text-slate-500" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Nombre completo</p>
                <p className="font-medium text-slate-800">{user?.full_name}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center shrink-0">
                <Mail className="w-5 h-5 text-slate-500" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Correo electrónico</p>
                <p className="font-medium text-slate-800">{user?.email}</p>
              </div>
            </div>

            {/* As a technician, they might have an employee number, but it's part of the Technician model, not User directly, 
                assuming it's not available in user object yet, we can mock it or show if it exists */}
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center shrink-0">
                <Hash className="w-5 h-5 text-slate-500" />
              </div>
              <div>
                <p className="text-sm text-slate-500">ID de Usuario</p>
                <p className="font-medium text-slate-800 text-xs mt-1">{user?.id}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <Link className="block rounded-lg bg-white border p-4 text-blue-700" to="/mi-cuenta">Mi cuenta · Cambiar contraseña</Link>
      <div className="pt-4 pb-8">
        <Button 
          variant="danger" 
          fullWidth 
          onClick={handleLogout}
          className="flex items-center justify-center gap-2"
        >
          <LogOut className="w-5 h-5" />
          CERRAR SESIÓN
        </Button>
      </div>
    </div>
  );
};

export default Profile;
