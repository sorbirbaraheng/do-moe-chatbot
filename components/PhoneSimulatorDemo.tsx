/**
 * Phone Simulator Demo Page
 * หน้าตัวอย่างการใช้งาน Phone Simulator
 */

import React, { useState } from 'react';
import { PhoneSimulator } from './common';

const PhoneSimulatorDemo: React.FC = () => {
    const [previewUrl, setPreviewUrl] = useState('');
    const [scale, setScale] = useState(0.7);
    const [frameColor, setFrameColor] = useState<'dark' | 'silver' | 'gold' | 'blue'>('dark');

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-800 to-gray-900 p-8">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-bold text-white mb-2">
                        📱 Phone Simulator
                    </h1>
                    <p className="text-gray-400">
                        ดู preview การออกแบบในรูปแบบ simulator มือถือ
                    </p>
                </div>

                {/* Settings Panel */}
                <div className="bg-white/5 backdrop-blur-xl rounded-2xl p-6 mb-8 border border-white/10">
                    <h2 className="text-white font-semibold mb-4">⚙️ การตั้งค่า</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {/* URL Input */}
                        <div>
                            <label className="block text-white/70 text-sm mb-2">Preview URL</label>
                            <input
                                type="url"
                                value={previewUrl}
                                onChange={(e) => setPreviewUrl(e.target.value)}
                                placeholder="https://example.com"
                                className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                            />
                        </div>

                        {/* Scale Slider */}
                        <div>
                            <label className="block text-white/70 text-sm mb-2">
                                Scale: {(scale * 100).toFixed(0)}%
                            </label>
                            <input
                                type="range"
                                min="0.4"
                                max="1"
                                step="0.05"
                                value={scale}
                                onChange={(e) => setScale(parseFloat(e.target.value))}
                                className="w-full accent-blue-500"
                            />
                        </div>

                        {/* Frame Color */}
                        <div>
                            <label className="block text-white/70 text-sm mb-2">สี Frame</label>
                            <div className="flex gap-2">
                                {(['dark', 'silver', 'gold', 'blue'] as const).map((color) => (
                                    <button
                                        key={color}
                                        onClick={() => setFrameColor(color)}
                                        className={`
                                            w-10 h-10 rounded-xl border-2 transition-all
                                            ${frameColor === color ? 'border-white scale-110' : 'border-white/20'}
                                            ${color === 'dark' ? 'bg-gray-800' : ''}
                                            ${color === 'silver' ? 'bg-gray-300' : ''}
                                            ${color === 'gold' ? 'bg-amber-300' : ''}
                                            ${color === 'blue' ? 'bg-blue-500' : ''}
                                        `}
                                        title={color}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Simulator Display */}
                <div className="flex justify-center">
                    <PhoneSimulator
                        src={previewUrl || undefined}
                        scale={scale}
                        frameColor={frameColor}
                        showControls={true}
                    >
                        {!previewUrl && (
                            <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 text-white p-6 text-center">
                                <div className="text-7xl mb-4">🎨</div>
                                <h3 className="text-2xl font-bold mb-3">MOE - One</h3>
                                <p className="text-white/80 text-sm mb-6">
                                    ใส่ URL ด้านบน หรือใช้ children component<br />
                                    เพื่อแสดง preview การออกแบบของคุณ
                                </p>
                                <div className="flex gap-3 flex-wrap justify-center">
                                    <span className="px-3 py-1.5 bg-white/20 rounded-full text-xs">iPhone 14</span>
                                    <span className="px-3 py-1.5 bg-white/20 rounded-full text-xs">Pro Max</span>
                                    <span className="px-3 py-1.5 bg-white/20 rounded-full text-xs">Android</span>
                                </div>
                            </div>
                        )}
                    </PhoneSimulator>
                </div>

                {/* Usage Guide */}
                <div className="mt-12 bg-white/5 backdrop-blur-xl rounded-2xl p-6 border border-white/10">
                    <h2 className="text-white font-semibold mb-4">📖 วิธีใช้งาน</h2>
                    <pre className="bg-black/30 rounded-xl p-4 text-sm text-green-400 overflow-x-auto">
                        {`import { PhoneSimulator } from './components/common';

// แบบ iframe (preview URL)
<PhoneSimulator 
    src="http://localhost:3000" 
    device="iphone-14"
    frameColor="dark"
    scale={0.8}
/>

// แบบ children component
<PhoneSimulator device="iphone-14-pro-max">
    <YourComponent />
</PhoneSimulator>`}
                    </pre>
                </div>
            </div>
        </div>
    );
};

export default PhoneSimulatorDemo;
