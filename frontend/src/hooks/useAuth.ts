import { useAuthStore } from '../store/authStore';

export const useAuth = () => {
  const { user, isAuthenticated, login, logout } = useAuthStore();
  
  const isAdmin = user?.role === 'ADMIN';
  const isTechnician = user?.role === 'TECHNICIAN';

  return {
    user,
    isAuthenticated,
    isAdmin,
    isReadOnly: user?.role === 'READ_ONLY',
    isTechnician,
    login,
    logout
  };
};
