import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Ultra-premium Apple Maps Style Marker
const appleMarkerIcon = new L.DivIcon({
    className: 'custom-apple-marker',
    html: `
    <div style="position: relative; width: 44px; height: 44px; display: flex; justify-content: center;">
      <!-- Pin Head -->
      <div style="
        position: relative;
        z-index: 2;
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, #FF3B30 0%, #FF2D55 100%);
        border: 2px solid white;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        box-shadow: 
          0 4px 12px rgba(255, 59, 48, 0.5),
          inset 0 2px 4px rgba(255, 255, 255, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
      ">
        <div style="
          transform: rotate(45deg);
          font-size: 20px;
          filter: drop-shadow(0 1px 2px rgba(0,0,0,0.1));
        ">🏫</div>
      </div>
      <!-- Pulse Effect -->
      <div style="
        position: absolute;
        bottom: 8px;
        width: 12px;
        height: 6px;
        background: rgba(0,0,0,0.2);
        border-radius: 50%;
        filter: blur(2px);
        transform: scale(1);
        animation: pin-shadow 2s infinite;
      "></div>
    </div>
  `,
    iconSize: [44, 44],
    iconAnchor: [22, 42],
    popupAnchor: [0, -42],
});

interface MapWidgetProps {
    latitude: number;
    longitude: number;
    schoolName: string;
    address?: string;
}

const MapWidget: React.FC<MapWidgetProps> = ({ latitude, longitude, schoolName, address }) => {
    const position: [number, number] = [latitude, longitude];

    return (
        <div className="mt-6 mb-2 rounded-[24px] overflow-hidden transition-all duration-300 hover:shadow-2xl" style={{
            background: '#FFFFFF',
            boxShadow: '0 12px 40px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04)',
            border: '1px solid rgba(0, 0, 0, 0.04)',
            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif'
        }}>
            {/* Refined Header - Apple Style: Clean & Minimal */}
            <div style={{
                padding: '18px 22px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'rgba(255, 255, 255, 0.8)',
                backdropFilter: 'blur(12px)',
                borderBottom: '1px solid rgba(0, 0, 0, 0.04)'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{
                        width: '42px',
                        height: '42px',
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, #007AFF 0%, #5856D6 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontSize: '20px',
                        boxShadow: '0 4px 12px rgba(0, 122, 255, 0.25)'
                    }}>
                        🗺️
                    </div>
                    <div>
                        <div style={{
                            fontSize: '17px',
                            fontWeight: 700,
                            color: '#1d1d1f',
                            letterSpacing: '-0.3px',
                            lineHeight: '1.2'
                        }}>
                            {schoolName}
                        </div>
                        <div style={{
                            fontSize: '13px',
                            color: '#86868b',
                            fontWeight: 500,
                            marginTop: '3px'
                        }}>
                            ตำแหน่งที่ตั้งโรงเรียน
                        </div>
                    </div>
                </div>

                {/* Live Indicator */}
                <div style={{
                    padding: '6px 12px',
                    borderRadius: '20px',
                    background: 'rgba(52, 199, 89, 0.1)',
                    color: '#34c759',
                    fontSize: '11px',
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    border: '1px solid rgba(52, 199, 89, 0.2)'
                }}>
                    <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                    </span>
                    LIVE
                </div>
            </div>

            {/* Map Content */}
            <div style={{ height: '320px', width: '100%', position: 'relative' }}>
                <MapContainer
                    center={position}
                    zoom={16}
                    scrollWheelZoom={false}
                    zoomControl={false}
                    style={{ height: '100%', width: '100%' }}
                >
                    {/* Esri World Street Map for a cleaner, more premium look similar to Apple Maps */}
                    <TileLayer
                        attribution='Tiles &copy; Esri'
                        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"
                    />
                    <Marker position={position} icon={appleMarkerIcon}>
                        {/* Minimal Popup removed for cleaner look as info is in header/footer */}
                    </Marker>
                </MapContainer>

                {/* Floating Action Button */}
                <a
                    href={`https://www.google.com/maps?q=${latitude},${longitude}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                        position: 'absolute',
                        bottom: '20px',
                        right: '20px',
                        zIndex: 1000,
                        background: 'white',
                        padding: '10px 18px',
                        borderRadius: '16px',
                        boxShadow: '0 8px 20px rgba(0, 0, 0, 0.12)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        textDecoration: 'none',
                        fontSize: '14px',
                        fontWeight: 600,
                        color: '#007AFF',
                        transition: 'transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)'
                    }}
                    className="hover:scale-105 active:scale-95"
                >
                    <span style={{ fontSize: '18px' }}>🧭</span>
                    นำทาง
                </a>
            </div>

            {/* Footer Info */}
            <div style={{
                background: '#FAFAFC',
                padding: '14px 22px',
                borderTop: '1px solid rgba(0,0,0,0.05)',
            }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <div style={{
                        minWidth: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: '#E5E5EA',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px'
                    }}>📍</div>
                    <div style={{ fontSize: '13px', color: '#424245', lineHeight: '1.5' }}>
                        {address || `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`}
                    </div>
                </div>
            </div>

            <style>{`
        @keyframes pin-shadow {
          0%, 100% { transform: scale(1); opacity: 0.5; }
          50% { transform: scale(1.5); opacity: 0.2; }
        }
      `}</style>
        </div>
    );
};

export default MapWidget;
