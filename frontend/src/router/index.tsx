import React from 'react';
import { createBrowserRouter, Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

// Layouts
import TechnicianLayout from '../components/layout/TechnicianLayout';
import AdminLayout from '../components/layout/AdminLayout';

// Pages
import Login from '../pages/Login';
import Account from '../pages/Account';
import PasswordRecovery from '../pages/PasswordRecovery';
import Locations from '../pages/admin/Locations';
import Attendance from '../pages/Attendance';
import TechnicianHome from '../pages/technician/Home';
import TechnicianHistory from '../pages/technician/History';
import TechnicianProfile from '../pages/technician/Profile';
import AdminDashboard from '../pages/admin/Dashboard';
import Personnel from '../pages/admin/Personnel';
import AdminTechnicians from '../pages/admin/Technicians';
import AdminTasks from '../pages/admin/Tasks';
import AdminWorkdays from '../pages/admin/Workdays';
import AdminReports from '../pages/admin/Reports';

const RequireAuth: React.FC<{ children: React.ReactNode; allowSetup?: boolean }> = ({ children, allowSetup }) => {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.must_change_password && !allowSetup) return <Navigate to="/mi-cuenta" replace />;
  return <>{children}</>;
};

const RequireRole: React.FC<{ role: 'ADMIN' | 'TECHNICIAN' | 'PANEL'; children: React.ReactNode }> = ({ role, children }) => {
  const { user } = useAuth();
  
  if (!(role === 'PANEL' ? ['ADMIN', 'READ_ONLY'].includes(user?.role || '') : user?.role === role)) {
    if (user?.role === 'ADMIN' || user?.role === 'READ_ONLY') return <Navigate to="/admin" replace />;
    if (user?.role === 'TECHNICIAN') return <Navigate to="/" replace />;
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

const LegacyTechnician = () => {
  const { id } = useParams();
  return <Navigate to={`/admin/personal/tecnico/${id}`} replace />;
};

const router = createBrowserRouter([
  {path: "/mi-cuenta", element: <RequireAuth allowSetup><Account /></RequireAuth>},
  {path: "/recuperar-contrasena", element: <PasswordRecovery />},
  {
    path: '/login',
    element: <Login />,
  },
  {
    path: '/',
    element: (
      <RequireAuth>
        <RequireRole role="TECHNICIAN">
          <TechnicianLayout />
        </RequireRole>
      </RequireAuth>
    ),
    children: [
      { index: true, element: <TechnicianHome /> },
      { path: 'historial', element: <TechnicianHistory /> },
      { path: 'perfil', element: <TechnicianProfile /> },
      { path: 'ausencias', element: <Attendance /> },
    ],
  },
  {
    path: '/admin',
    element: (
      <RequireAuth>
        <RequireRole role="PANEL">
          <AdminLayout />
        </RequireRole>
      </RequireAuth>
    ),
    children: [
      { index: true, element: <AdminDashboard /> },
      { path: 'personal', element: <RequireRole role="ADMIN"><Personnel /></RequireRole> },
      { path: 'personal/tecnico/:id', element: <AdminTechnicians /> },
      { path: 'usuarios', element: <Navigate to="/admin/personal" replace /> },
      { path: 'tecnicos', element: <Navigate to="/admin/personal?rol=TECHNICIAN" replace /> },
      { path: 'tecnicos/:id', element: <LegacyTechnician /> },
      { path: 'tareas', element: <AdminTasks /> },
      { path: 'jornadas', element: <AdminWorkdays /> },
      { path: 'reportes', element: <AdminReports /> },
      { path: 'sucursales', element: <RequireRole role="ADMIN"><Locations /></RequireRole> },
      { path: 'asistencia', element: <Attendance /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />
  }
]);

export default router;
