import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default marker icon issue (known bug)
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

interface MapViewProps {
  latitude: number;
  longitude: number;
  accuracy?: number;
  label?: string;  // Popup label text
  height?: string; // CSS height, default '300px'
}

const MapView: React.FC<MapViewProps> = ({ latitude, longitude, accuracy, label, height = '300px' }) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!mapRef.current) return;

    if (!leafletMapRef.current) {
      leafletMapRef.current = L.map(mapRef.current).setView([latitude, longitude], 15);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(leafletMapRef.current);
    } else {
      leafletMapRef.current.setView([latitude, longitude], 15);
    }

    // Clear existing layers (except tile layer)
    leafletMapRef.current.eachLayer((layer) => {
      if (layer instanceof L.Marker || layer instanceof L.Circle) {
        leafletMapRef.current?.removeLayer(layer);
      }
    });

    const marker = L.marker([latitude, longitude]).addTo(leafletMapRef.current);
    
    if (label) {
      marker.bindPopup(label).openPopup();
    }

    if (accuracy && accuracy > 0) {
      L.circle([latitude, longitude], {
        radius: accuracy,
        color: '#3b82f6',
        fillColor: '#3b82f6',
        fillOpacity: 0.2
      }).addTo(leafletMapRef.current);
    }

    return () => {
      if (leafletMapRef.current) {
        leafletMapRef.current.remove();
        leafletMapRef.current = null;
      }
    };
  }, [latitude, longitude, accuracy, label]);

  return (
    <div className="relative w-full flex flex-col gap-2">
      <div 
        ref={mapRef} 
        style={{ height, width: '100%' }} 
        className="rounded-lg overflow-hidden border border-slate-200 shadow-sm z-0 relative bg-slate-100 flex items-center justify-center"
      >
        <span className="text-slate-400 absolute">Abriendo en mapa...</span>
      </div>
      <div className="flex justify-end">
        <a 
          href={`https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=15/${latitude}/${longitude}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
        >
          Ver en OpenStreetMap
        </a>
      </div>
    </div>
  );
};

export default MapView;
