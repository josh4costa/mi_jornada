import { useState } from 'react';

export interface GeoPosition {
  latitude: number;
  longitude: number;
  accuracy: number;
}

export function useGeolocation() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getPosition = (): Promise<GeoPosition> => {
    return new Promise((resolve, reject) => {
      setLoading(true);
      setError(null);

      if (!navigator.geolocation) {
        const msg = 'Geolocalización no disponible en este dispositivo';
        setError(msg);
        setLoading(false);
        reject(new Error(msg));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLoading(false);
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
          });
        },
        (err) => {
          setLoading(false);
          let msg = 'No se pudo obtener la ubicación. Verifica que el GPS esté activado.';
          if (err.code === err.PERMISSION_DENIED) {
            msg = 'Necesitamos tu ubicación para registrar la entrada. Por favor, permite el acceso.';
          }
          setError(msg);
          reject(new Error(msg));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0,
        }
      );
    });
  };

  return { getPosition, loading, error };
}
