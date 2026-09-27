import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';

const OfflineBanner: React.FC = () => {
  const { isOnline } = useOnlineStatus();

  if (isOnline) return null;

  return (
    <div className="bg-amber-100 text-amber-800 px-4 py-2 flex items-center justify-center gap-2 text-sm font-medium sticky top-0 z-50">
      <AlertTriangle className="w-5 h-5" />
      <span>Sin conexión. Conéctate para consultar y registrar tu jornada.</span>
    </div>
  );
};

export default OfflineBanner;
