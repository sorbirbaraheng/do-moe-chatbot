/**
 * Phone Simulator Component
 * แสดง frame มือถือสไตล์ iPhone สำหรับ preview การออกแบบ
 */

import React, { useState } from 'react';

interface PhoneSimulatorProps {
    /** URL หรือ path ที่จะแสดงใน simulator */
    src?: string;
    /** ขนาดหน้าจอ */
    device?: 'iphone-14' | 'iphone-14-pro-max' | 'iphone-se' | 'android';
    /** สีของ frame (dark/silver/gold/blue) */
    frameColor?: 'dark' | 'silver' | 'gold' | 'blue';
    /** แสดง notch หรือ dynamic island */
    showNotch?: boolean;
    /** scale ของ simulator (0.5 - 1.5) */
    scale?: number;
    /** children component ที่จะแสดงแทน iframe */
    children?: React.ReactNode;
    /** แสดง rotation buttons */
    showControls?: boolean;
}

// Device dimensions (width x height in CSS pixels)
const DEVICES = {
    'iphone-14': { width: 390, height: 844, name: 'iPhone 14', notchType: 'dynamic-island' },
    'iphone-14-pro-max': { width: 430, height: 932, name: 'iPhone 14 Pro Max', notchType: 'dynamic-island' },
    'iphone-se': { width: 375, height: 667, name: 'iPhone SE', notchType: 'none' },
    'android': { width: 412, height: 915, name: 'Android', notchType: 'notch' },
} as const;

const FRAME_COLORS = {
    dark: {
        frame: 'bg-gradient-to-b from-gray-800 to-gray-900',
        border: 'border-gray-700',
        buttons: 'bg-gray-700',
        shadow: 'shadow-[0_25px_80px_-12px_rgba(0,0,0,0.5)]',
    },
    silver: {
        frame: 'bg-gradient-to-b from-gray-200 to-gray-300',
        border: 'border-gray-400',
        buttons: 'bg-gray-400',
        shadow: 'shadow-[0_25px_80px_-12px_rgba(0,0,0,0.3)]',
    },
    gold: {
        frame: 'bg-gradient-to-b from-amber-200 to-amber-300',
        border: 'border-amber-400',
        buttons: 'bg-amber-400',
        shadow: 'shadow-[0_25px_80px_-12px_rgba(180,130,60,0.4)]',
    },
    blue: {
        frame: 'bg-gradient-to-b from-blue-400 to-blue-600',
        border: 'border-blue-500',
        buttons: 'bg-blue-500',
        shadow: 'shadow-[0_25px_80px_-12px_rgba(59,130,246,0.4)]',
    },
};

const PhoneSimulator: React.FC<PhoneSimulatorProps> = ({
    src,
    device = 'iphone-14',
    frameColor = 'dark',
    showNotch = true,
    scale = 0.75,
    children,
    showControls = true,
}) => {
    const [isLandscape, setIsLandscape] = useState(false);
    const [currentDevice, setCurrentDevice] = useState<keyof typeof DEVICES>(device);

    const deviceSpec = DEVICES[currentDevice];
    const colors = FRAME_COLORS[frameColor];

    const screenWidth = isLandscape ? deviceSpec.height : deviceSpec.width;
    const screenHeight = isLandscape ? deviceSpec.width : deviceSpec.height;

    return (
        <div className="flex flex-col items-center gap-6">
            {/* Controls */}
            {showControls && (
                <div className="flex items-center gap-4 p-3 bg-white/10 backdrop-blur-xl rounded-2xl border border-white/20">
                    {/* Device Selector */}
                    <select
                        value={currentDevice}
                        onChange={(e) => setCurrentDevice(e.target.value as keyof typeof DEVICES)}
                        className="px-4 py-2 bg-white/20 border border-white/30 rounded-xl text-white text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer transition-all hover:bg-white/30"
                    >
                        {Object.entries(DEVICES).map(([key, spec]) => (
                            <option key={key} value={key} className="text-gray-900">
                                {spec.name}
                            </option>
                        ))}
                    </select>

                    {/* Rotation Button */}
                    <button
                        onClick={() => setIsLandscape(!isLandscape)}
                        className="p-2.5 bg-white/20 border border-white/30 rounded-xl text-white hover:bg-white/30 transition-all group"
                        title="หมุนหน้าจอ"
                    >
                        <svg
                            className={`w-5 h-5 transition-transform duration-300 ${isLandscape ? 'rotate-90' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                    </button>

                    {/* Device Info */}
                    <div className="text-white/70 text-sm">
                        {screenWidth} × {screenHeight}
                    </div>
                </div>
            )}

            {/* Phone Frame */}
            <div
                className={`
                    relative rounded-[3rem] p-3 ${colors.frame} ${colors.shadow}
                    border-4 ${colors.border}
                    transition-all duration-500 ease-out
                `}
                style={{
                    transform: `scale(${scale})`,
                    transformOrigin: 'top center',
                }}
            >
                {/* Side Buttons - Left (Silent Switch & Volume) */}
                <div className="absolute -left-1.5 top-28 flex flex-col gap-3">
                    {/* Silent Switch */}
                    <div className={`w-1.5 h-8 rounded-full ${colors.buttons}`} />
                    {/* Volume Up */}
                    <div className={`w-1.5 h-14 rounded-full ${colors.buttons}`} />
                    {/* Volume Down */}
                    <div className={`w-1.5 h-14 rounded-full ${colors.buttons}`} />
                </div>

                {/* Side Button - Right (Power) */}
                <div className="absolute -right-1.5 top-40">
                    <div className={`w-1.5 h-20 rounded-full ${colors.buttons}`} />
                </div>

                {/* Screen Container */}
                <div
                    className="relative bg-black rounded-[2.5rem] overflow-hidden"
                    style={{
                        width: screenWidth,
                        height: screenHeight,
                    }}
                >
                    {/* Dynamic Island / Notch */}
                    {showNotch && deviceSpec.notchType === 'dynamic-island' && (
                        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20">
                            <div className="w-28 h-8 bg-black rounded-full flex items-center justify-center gap-2 shadow-lg">
                                {/* Camera */}
                                <div className="w-3 h-3 rounded-full bg-gray-800 ring-1 ring-gray-700">
                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-900 m-0.5" />
                                </div>
                            </div>
                        </div>
                    )}

                    {showNotch && deviceSpec.notchType === 'notch' && (
                        <div className="absolute top-0 left-1/2 -translate-x-1/2 z-20">
                            <div className="w-40 h-7 bg-black rounded-b-3xl" />
                        </div>
                    )}

                    {/* Status Bar */}
                    <div className="absolute top-0 left-0 right-0 h-12 z-10 flex items-center justify-between px-8 text-white text-sm font-medium">
                        <span>9:41</span>
                        <div className="flex items-center gap-1">
                            {/* Signal */}
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                <rect x="1" y="14" width="4" height="6" rx="1" />
                                <rect x="7" y="10" width="4" height="10" rx="1" />
                                <rect x="13" y="6" width="4" height="14" rx="1" />
                                <rect x="19" y="2" width="4" height="18" rx="1" />
                            </svg>
                            {/* WiFi */}
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 18c1.1 0 2 .9 2 2s-.9 2-2 2-2-.9-2-2 .9-2 2-2zm0-4c2.2 0 4.2.9 5.7 2.3l-1.4 1.4C15.1 16.6 13.6 16 12 16s-3.1.6-4.3 1.7l-1.4-1.4C7.8 14.9 9.8 14 12 14zm0-4c3.3 0 6.3 1.3 8.5 3.5l-1.4 1.4C17.1 12.9 14.6 12 12 12s-5.1.9-7.1 2.9l-1.4-1.4C5.7 11.3 8.7 10 12 10zm0-4c4.4 0 8.4 1.8 11.3 4.7l-1.4 1.4C19.3 9.5 15.8 8 12 8S4.7 9.5 2.1 12.1L.7 10.7C3.6 7.8 7.6 6 12 6z" />
                            </svg>
                            {/* Battery */}
                            <div className="flex items-center gap-0.5">
                                <div className="w-6 h-3 border border-white rounded-sm p-0.5">
                                    <div className="h-full w-full bg-green-500 rounded-xs" />
                                </div>
                                <div className="w-0.5 h-1.5 bg-white rounded-r" />
                            </div>
                        </div>
                    </div>

                    {/* Content Area */}
                    <div className="w-full h-full bg-white">
                        {children ? (
                            <div className="w-full h-full overflow-auto">
                                {children}
                            </div>
                        ) : src ? (
                            <iframe
                                src={src}
                                className="w-full h-full border-0"
                                title="Phone Preview"
                            />
                        ) : (
                            /* Default Placeholder */
                            <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-b from-blue-500 to-purple-600 text-white p-8">
                                <div className="text-6xl mb-4">📱</div>
                                <h3 className="text-xl font-bold mb-2">Phone Simulator</h3>
                                <p className="text-white/80 text-center text-sm">
                                    ใส่ URL หรือ children component<br />
                                    เพื่อแสดงเนื้อหา
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Home Indicator */}
                    {deviceSpec.notchType !== 'none' && (
                        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-20">
                            <div className="w-32 h-1 bg-white/30 rounded-full" />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default PhoneSimulator;
