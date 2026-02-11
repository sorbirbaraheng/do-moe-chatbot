import React, { useEffect, useState } from 'react';
import { fetchAuditLogs } from '../../../services/adminApi';

interface AuditLogItem {
  id?: string;
  timestamp?: string;
  action?: string;
  status?: string;
  role?: string;
  ip?: string;
  detail?: any;
}

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return '-';
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return new Intl.DateTimeFormat('th-TH', {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(parsed);
};

const formatValue = (value: any) => {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'string') return value.length > 200 ? `${value.slice(0, 200)}…` : value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.length > 10 ? `${value.slice(0, 10).join(', ')}…` : value.join(', ');
  try {
    const text = JSON.stringify(value);
    return text.length > 200 ? `${text.slice(0, 200)}…` : text;
  } catch {
    return String(value);
  }
};

const AdminAuditTab: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [hasMore, setHasMore] = useState(true);

  const loadLogs = async (reset = false) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAuditLogs(20, reset ? undefined : cursor);
      const nextCursor = result.nextCursor;
      const items = result.logs || [];
      setLogs(prev => (reset ? items : [...prev, ...items]));
      setCursor(nextCursor);
      setHasMore(result.hasMore ?? items.length === 20);
    } catch (err: any) {
      setError(err?.message || 'โหลดข้อมูลไม่สำเร็จ');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs(true);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800">🧾 Audit Logs</h2>
          <p className="text-sm text-gray-500 mt-1">ประวัติการใช้งานฝั่งผู้ดูแล</p>
        </div>
        <button
          onClick={() => loadLogs(true)}
          className="px-4 py-2 bg-blue-50 text-blue-600 rounded-xl font-medium hover:bg-blue-100 transition-colors flex items-center gap-2"
          disabled={loading}
        >
          รีเฟรช
        </button>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm font-medium">{error}</div>
      )}

      <div className="bg-white rounded-2xl border border-black/5 overflow-hidden">
        {logs.length === 0 && !loading && (
          <div className="py-12 text-center text-sm text-gray-500">ยังไม่มี Audit Log</div>
        )}
        {logs.map((log, idx) => (
          <div
            key={`${log.id || idx}`}
            className="px-5 py-4 border-b border-black/5 flex flex-col md:flex-row md:items-center md:justify-between gap-2"
          >
            <div>
              <div className="text-sm font-semibold text-[#1D1D1F]">
                {log.action || 'Unknown action'}
                <span className={`ml-2 px-2 py-0.5 text-[10px] rounded-full ${log.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                  {log.status || 'info'}
                </span>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {formatTimestamp(log.timestamp)} • {log.role || '-'} • {log.ip || '-'}
              </div>
              {log.detail && (
                <details className="mt-2 text-xs text-gray-600">
                  <summary className="cursor-pointer select-none text-[11px] text-blue-700">รายละเอียด</summary>
                  <div className="mt-2 grid gap-1">
                    {log.detail && typeof log.detail === 'object' && !Array.isArray(log.detail) ? (
                      Object.entries(log.detail).map(([key, value]) => (
                        <div key={key} className="flex items-start gap-2">
                          <span className="min-w-[120px] text-[11px] text-gray-500">{key}</span>
                          <span className="text-[11px] text-gray-700 break-words">{formatValue(value)}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-[11px] text-gray-700">{formatValue(log.detail)}</div>
                    )}
                  </div>
                </details>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-center">
        {hasMore && (
          <button
            onClick={() => loadLogs(false)}
            className="px-5 py-2 rounded-xl bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200 transition-colors"
            disabled={loading}
          >
            {loading ? 'กำลังโหลด...' : 'โหลดเพิ่ม'}
          </button>
        )}
      </div>
    </div>
  );
};

export default AdminAuditTab;
