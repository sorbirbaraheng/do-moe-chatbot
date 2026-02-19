import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend
} from 'recharts';

interface ChartWidgetProps {
    type: 'bar' | 'pie';
    data: any[];
    title?: string;
    colors?: string[];
}

// ✨ Apple-inspired Premium Gradients & Colors
const COLORS = [
    '#007AFF', // Apple Blue
    '#34C759', // Apple Green
    '#FF9500', // Apple Orange
    '#FF3B30', // Apple Red
    '#AF52DE', // Apple Purple
    '#5856D6', // Indigo
];

// Comparison specific colors for 2-item comparison
const COMPARE_COLORS = [
    '#007AFF', // Blue for first item
    '#FF9500', // Orange for second item (High contrast)
];

const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-white/90 backdrop-blur-2xl px-4 py-3 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.12)] border border-white/40 text-sm">
                <p className="font-semibold text-gray-900 text-[13px] mb-1">{label || payload[0].name}</p>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: payload[0].fill }}></div>
                    <p className="text-[#1d1d1f] font-bold text-lg leading-none">
                        {payload[0].value.toLocaleString()}
                        <span className="text-[11px] font-medium text-gray-500 ml-1.5 align-middle">รายการ</span>
                    </p>
                </div>
            </div>
        );
    }
    return null;
};

const ChartWidget: React.FC<ChartWidgetProps> = ({ type, data, title, colors = COLORS }) => {
    // Determine if this is a comparison (2 items) to use distinct colors
    const isComparison = type === 'bar' && data.length === 2;
    const chartColors = isComparison ? COMPARE_COLORS : colors;

    // Dynamic height calculation
    const barHeight = data.length <= 2
        ? 180 // Better height for comparison
        : Math.max(200, data.length * 50);

    return (
        <div className="w-full mt-5 mb-4 group animate-fade-in-up">
            <div className="relative bg-gradient-to-br from-white/80 via-white/60 to-white/40 backdrop-blur-xl rounded-[24px] p-5 border border-white/60 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.05),inset_0_0_0_1px_rgba(255,255,255,0.2)] hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)] transition-all duration-500">

                {/* Glass Glare Effect */}
                <div className="absolute top-0 left-0 w-full h-full rounded-[24px] bg-gradient-to-br from-white/40 to-transparent pointer-events-none opacity-50"></div>

                {title && (
                    <div className="relative flex items-center gap-2.5 mb-5 pl-1">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/20 text-xs">
                            {type === 'bar' ? '📊' : '🍩'}
                        </div>
                        <h4 className="text-[15px] font-bold text-[#1d1d1f] tracking-tight">
                            {title}
                        </h4>
                    </div>
                )}

                <div className={`relative w-full ${data.length <= 2 ? 'min-w-[280px]' : 'min-w-[350px]'}`} style={{ height: type === 'pie' ? 300 : barHeight }}>
                    <ResponsiveContainer width="100%" height="100%">
                        {type === 'bar' ? (
                            <BarChart
                                data={data}
                                layout="vertical"
                                margin={{ top: 0, right: 20, left: 10, bottom: 0 }}
                                barCategoryGap="25%"
                            >
                                <defs>
                                    {data.map((entry, index) => (
                                        <linearGradient key={`gradient-${index}`} id={`colorGradient-${index}`} x1="0" y1="0" x2="1" y2="0">
                                            <stop offset="0%" stopColor={chartColors[index % chartColors.length]} stopOpacity={0.8} />
                                            <stop offset="100%" stopColor={chartColors[index % chartColors.length]} stopOpacity={1} />
                                        </linearGradient>
                                    ))}
                                </defs>
                                <XAxis type="number" hide />
                                <YAxis
                                    dataKey="name"
                                    type="category"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{
                                        fontSize: 13,
                                        fill: '#424245',
                                        fontWeight: 600,
                                    }}
                                    width={110}
                                    tickFormatter={(value) => value.length > 15 ? value.substring(0, 15) + '...' : value}
                                />
                                <Tooltip
                                    content={<CustomTooltip />}
                                    cursor={{ fill: 'rgba(0,0,0,0.03)', radius: 12 }}
                                />
                                <Bar
                                    dataKey="value"
                                    radius={[0, 12, 12, 0]} // Modern rounded right edge
                                    barSize={32}
                                    animationDuration={1500}
                                    animationEasing="ease-out"
                                >
                                    {data.map((entry, index) => (
                                        <Cell
                                            key={`cell-${index}`}
                                            fill={`url(#colorGradient-${index})`}
                                            style={{ filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.1))' }}
                                        />
                                    ))}
                                </Bar>
                            </BarChart>
                        ) : (
                            <PieChart>
                                <defs>
                                    {data.map((entry, index) => (
                                        <linearGradient key={`pie-gradient-${index}`} id={`pieGradient-${index}`} x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor={colors[index % colors.length]} stopOpacity={1} />
                                            <stop offset="100%" stopColor={colors[index % colors.length]} stopOpacity={0.85} />
                                        </linearGradient>
                                    ))}
                                </defs>
                                <Pie
                                    data={data}
                                    cx="50%"
                                    cy="45%"
                                    innerRadius={65}
                                    outerRadius={105}
                                    paddingAngle={4}
                                    dataKey="value"
                                    stroke="rgba(255,255,255,0.5)"
                                    strokeWidth={3}
                                    animationDuration={1500}
                                    animationEasing="ease-out"
                                >
                                    {data.map((entry, index) => (
                                        <Cell
                                            key={`cell-${index}`}
                                            fill={`url(#pieGradient-${index})`}
                                            style={{ filter: 'drop-shadow(0 8px 16px rgba(0,0,0,0.15))' }}
                                        />
                                    ))}
                                </Pie>
                                <Tooltip content={<CustomTooltip />} />
                                <Legend
                                    layout="horizontal"
                                    verticalAlign="bottom"
                                    align="center"
                                    iconType="circle"
                                    iconSize={8}
                                    formatter={(value, entry: any) => {
                                        const { payload } = entry;
                                        const count = payload?.value?.toLocaleString() || '';
                                        const displayName = value.length > 20 ? value.substring(0, 20) + '...' : value;
                                        return (
                                            <span className="text-gray-600 font-medium ml-1" style={{ fontSize: '12px' }}>
                                                {displayName} <span className="text-black font-bold">({count})</span>
                                            </span>
                                        );
                                    }}
                                    wrapperStyle={{
                                        paddingTop: '20px',
                                    }}
                                />
                            </PieChart>
                        )}
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
};

export default React.memo(ChartWidget);
