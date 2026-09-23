import React, { useState, useEffect } from 'react';
import { Clock, RefreshCw, Eye, AlertTriangle, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../utils/api';
import { translations } from '../i18n/translations';
import { ScanResult } from '../types';

interface ScanHistoryProps {
  onSelectScan: (scan: ScanResult) => void;
  lang: 'en' | 'hi';
}

export const ScanHistory: React.FC<ScanHistoryProps> = ({ onSelectScan, lang }) => {
  const t = translations[lang];
  const [scans, setScans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [rerunningId, setRerunningId] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    fetchScans();
  }, []);

  // While any scan is still processing (server answers 202 + background
  // worker), poll every 5s so finished scans appear here on their own —
  // no manual "check again later" step. Stops as soon as all are terminal.
  useEffect(() => {
    if (!autoRefresh) return;
    const id = window.setInterval(fetchScans, 5000);
    return () => window.clearInterval(id);
  }, [autoRefresh]);

  // Refetch when the tab regains focus — cheap staleness guard.
  useEffect(() => {
    const onFocus = () => fetchScans();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, []);

  const fetchScans = async () => {
    try {
      const res = await api.get('/scans?page=1&size=20');
      const items = res.data?.items || [];
      setScans(items);
      // A scan still in flight reports no processing time yet.
      const anyPending = items.some((s: any) => s.processing_time_ms == null);
      setAutoRefresh(anyPending);
    } catch (err) {
      console.error('Failed to load scans:', err);
      setAutoRefresh(false);
    } finally {
      setLoading(false);
    }
  };

  const handleRerun = async (id: string) => {
    setRerunningId(id);
    try {
      const res = await api.get(`/scans/${id}`);
      onSelectScan(res.data);
    } catch (e) {
      alert('Failed to re-run scan.');
    } finally {
      setRerunningId(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#12355B]">{t.scanHistoryTitle}</h1>
          <p className="text-xs text-slate-500 mt-1">
            Complete log of label processing attempts, OCR latency, confidence scores, and re-evaluation actions per §7.7
          </p>
        </div>
        <button
          onClick={fetchScans}
          className="flex items-center gap-2 px-3.5 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 transition-colors shrink-0 self-start sm:self-auto min-h-[40px]"
          aria-label="Refresh scan history"
        >
          <RefreshCw size={14} className={autoRefresh ? 'animate-spin text-[#0E7490]' : ''} />
          <span>{autoRefresh ? 'Live — updating…' : 'Refresh'}</span>
        </button>
      </div>

      {/* Scans Grid */}
      {loading ? (
        <div className="text-center py-16 text-xs text-slate-400">Loading scan history...</div>
      ) : scans.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 text-slate-400 text-xs">
          No label scans recorded yet. Use the Scan/Upload page to run an automated check.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {scans.map((s) => {
            const isComp = s.verdict === 'COMPLIANT';
            const isNonComp = s.verdict === 'NON_COMPLIANT';

            return (
              <div
                key={s.id}
                className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs hover:shadow-md transition-all flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                      isComp
                        ? 'bg-emerald-100 text-emerald-800'
                        : isNonComp
                        ? 'bg-rose-100 text-rose-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}>
                      {s.verdict}
                    </span>
                    <span className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Clock size={12} />
                      {new Date(s.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  <h3 className="font-bold text-sm text-[#12355B] truncate">{s.product_name}</h3>
                  <p className="text-xs text-slate-500 truncate mt-0.5">{s.manufacturer_name}</p>

                  <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-bold">Score</span>
                      <div className="font-bold text-slate-800">{(s.compliance_score || 0).toFixed(1)}%</div>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-bold">OCR Conf</span>
                      <div className="font-bold text-[#0E7490]">{(s.avg_ocr_confidence || 0).toFixed(1)}%</div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <span className="text-[11px] text-slate-400 font-mono">
                    {s.processing_time_ms ? `${s.processing_time_ms}ms` : '< 1s'}
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleRerun(s.id)}
                      disabled={rerunningId === s.id}
                      className="px-3 py-1.5 bg-[#12355B] hover:bg-[#0F2C4C] text-white rounded-lg text-xs font-bold transition-colors flex items-center gap-1 min-h-[36px]"
                    >
                      <Eye size={13} />
                      <span>View & Amend</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
