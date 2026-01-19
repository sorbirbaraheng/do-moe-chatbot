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

// Apple-inspired gradient colors
const COLORS = [
    '#007AFF', // Apple Blue
    '#34C759', // Apple Green
    '#FF9500', // Apple Orange
    '#FF3B30', // Apple Red
    '#AF52DE', // Apple Purple
    '#FF2D55', // Apple Pink
];

const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-white/95 backdrop-blur-xl px-4 py-3 rounded-2xl shadow-2xl border border-white/20 text-sm"
                style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.12)' }}>
                <p className="font-semibold text-gray-900 text-[13px]">{label || payload[0].name}</p>
                <p className="text-[#007AFF] font-bold text-lg mt-0.5">
                    {payload[0].value.toLocaleString()} <span className="text-xs font-medium text-gray-500">แห่ง</span>
                </p>
            </div>
        );
    }
    return null;
};

const ChartWidget: React.FC<ChartWidgetProps> = ({ type, data, title, colors = COLORS }) => {
    // Calculate dynamic height based on data count - more compact for small datasets
    const barHeight = data.length <= 2
        ? Math.max(100, data.length * 60 + 40) // Compact for 1-2 items
        : Math.max(200, data.length * 45);

    return (
        <div className="w-full mt-4 mb-3 bg-gradient-to-br from-white/80 to-white/60 backdrop-blur-xl rounded-2xl p-4 border border-white/30"
            style={{
                boxShadow: '0 4px 24px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
            }}>
            {title && (
                <div className="flex items-center gap-2 mb-4">
                    <span className="text-base">📊</span>
                    <h4 className="text-sm font-semibold text-gray-700 tracking-tight">
                        {title}
                    </h4>
                </div>
            )}

            <div className={`w-full ${data.length <= 2 ? 'min-w-[280px]' : 'min-w-[350px]'}`} style={{ height: type === 'pie' ? 300 : barHeight }}>
                <ResponsiveContainer width="100%" height="100%">
                    {type === 'bar' ? (
                        <BarChart
                            data={data}
                            layout="vertical"
                            margin={{ top: 0, right: 30, left: 10, bottom: 0 }}
                            barCategoryGap="20%"
                        >
                            <defs>
                                {data.map((entry, index) => (
                                    <linearGradient key={`gradient-${index}`} id={`colorGradient-${index}`} x1="0" y1="0" x2="1" y2="0">
                                        <stop offset="0%" stopColor={colors[index % colors.length]} stopOpacity={0.9} />
                                        <stop offset="100%" stopColor={colors[index % colors.length]} stopOpacity={1} />
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
                                    fill: '#374151',
                                    fontWeight: 500,
                                }}
                                width={100}
                                tickFormatter={(value) => value.length > 12 ? value.substring(0, 12) + '...' : value}
                            />
                            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,122,255,0.04)', radius: 8 }} />
                            <Bar
                                dataKey="value"
                                radius={[8, 8, 8, 8]}
                                barSize={28}
                            >
                                {data.map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={`url(#colorGradient-${index})`}
                                        style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))' }}
                                    />
                                ))}
                            </Bar>
                        </BarChart>
                    ) : (
                        <PieChart>
                            <defs>
                                {data.map((entry, index) => (
                                    <linearGradient key={`pie-gradient-${index}`} id={`pieGradient-${index}`} x1="0" y1="0" x2="1" y2="1">
                                        <stop offset="0%" stopColor={colors[index % colors.length]} stopOpacity={1} />
                                        <stop offset="100%" stopColor={colors[index % colors.length]} stopOpacity={0.8} />
                                    </linearGradient>
                                ))}
                            </defs>
                            <Pie
                                data={data}
                                cx="50%"
                                cy="45%"
                                innerRadius={60}
                                outerRadius={100}
                                paddingAngle={3}
                                dataKey="value"
                                stroke="rgba(255,255,255,0.8)"
                                strokeWidth={2}
                            >
                                {data.map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={`url(#pieGradient-${index})`}
                                        style={{ filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.15))' }}
                                    />
                                ))}
                            </Pie>
                            <Tooltip content={<CustomTooltip />} />
                            <Legend
                                layout="horizontal"
                                verticalAlign="bottom"
                                align="center"
                                iconType="circle"
                                iconSize={10}
                                formatter={(value, entry: any) => {
                                    const { payload } = entry;
                                    const count = payload?.value?.toLocaleString() || '';
                                    const displayName = value.length > 25 ? value.substring(0, 25) + '...' : value;
                                    return (
                                        <span className="text-gray-700 font-medium" style={{ fontSize: '11px' }}>
                                            {displayName} <span className="text-[#007AFF] font-bold">({count})</span>
                                        </span>
                                    );
                                }}
                                wrapperStyle={{
                                    paddingTop: '16px',
                                    lineHeight: '22px',
                                }}
                            />
                        </PieChart>
                    )}
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default React.memo(ChartWidget);
