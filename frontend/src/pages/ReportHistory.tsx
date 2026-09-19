import React, { useState, useEffect, useCallback } from 'react';
import { Download, ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '../utils/api';
import { ReportItem } from '../types';
import { translations } from '../i18n/translations';

interface ReportHistoryProps {
  onViewReport: (reportNumber: string) => void;
  lang: 'en' | 'hi';
}

export const ReportHistory: React.FC<ReportHistoryProps> = ({ onViewReport, lang }) => {
  const t = translations[lang];
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [verdictFilter, setVerdictFilter] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    try {
      let url = `/reports?page=${page}&size=10`;
      if (verdictFilter) url += `&verdict=${verdictFilter}`;
      const res = await api.get(url);
      setReports(res.data?.items || []);
      setTotalPages(res.data?.pages || 1);
    } catch (err) {
      console.error('Failed to load reports:', err);
    } finally {
      setLoading(false);
    }
  }, [page, verdictFilter]);

  useEffect(() => {
    void fetchReports();
  }, [fetchReports]);

  const handleExportExcel = async () => {
    try {
      const res = await api.get('/reports?format=excel', { responseType: 'blob' });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'compliance_reports_codemaze.xlsx';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Failed to export Excel:', err);
      alert('Could not generate Excel export.');
    }
  };

  const handleDownloadSinglePdf = async (reportNumber: string) => {
    try {
      const res = await api.get(`/reports/${reportNumber}/pdf`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportNumber}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to download report PDF:', error);
      alert('PDF download failed.');
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header & Excel Export Action */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#12355B]">{t.reportHistoryTitle}</h1>
          <p className="text-xs text-slate-500 mt-1">
            Server-side paginated compliance dossiers with formal legal citations & PDF exports
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={verdictFilter}
            onChange={(e) => setVerdictFilter(e.target.value)}
            className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold outline-none focus:border-[#0E7490] min-h-[40px]"
          >
            <option value="">All Verdicts</option>
            <option value="COMPLIANT">Compliant</option>
            <option value="NON_COMPLIANT">Non-Compliant</option>
            <option value="NEEDS_REVIEW">Needs Review</option>
          </select>

          <button
            onClick={handleExportExcel}
            className="flex items-center gap-2 px-4 py-2 bg-[#0E7490] hover:bg-[#0c6178] text-white rounded-xl text-xs font-bold shadow-xs transition-colors min-h-[40px]"
          >
            <Download size={15} />
            <span>{t.exportExcel}</span>
          </button>
        </div>
      </div>

      {/* Reports Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider">
                <th className="p-4">{t.reportNumber}</th>
                <th className="p-4">{t.product}</th>
                <th className="p-4">{t.manufacturer}</th>
                <th className="p-4">Score</th>
                <th className="p-4">Verdict</th>
                <th className="p-4">{t.date}</th>
                <th className="p-4 text-right">{t.actions}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-400">Loading compliance reports...</td>
                </tr>
              ) : reports.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-400">No reports generated yet. Run a label scan to produce reports.</td>
                </tr>
              ) : (
                reports.map((r) => {
                  const isComp = r.verdict === 'COMPLIANT';
                  const isNonComp = r.verdict === 'NON_COMPLIANT';
                  return (
                    <tr key={r.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="p-4 font-bold text-[#0E7490]">{r.report_number}</td>
                      <td className="p-4 font-semibold text-[#12355B]">{r.product_name}</td>
                      <td className="p-4 text-slate-600 truncate max-w-[160px]">{r.manufacturer_name}</td>
                      <td className="p-4 font-bold text-slate-800">{(r.compliance_score || 0).toFixed(1)}%</td>
                      <td className="p-4">
                        <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          isComp
                            ? 'bg-emerald-100 text-emerald-800'
                            : isNonComp
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {r.verdict}
                        </span>
                      </td>
                      <td className="p-4 text-slate-500">{new Date(r.created_at).toLocaleDateString()}</td>
                      <td className="p-4 text-right space-x-2">
                        <button
                          onClick={() => onViewReport(r.report_number)}
                          className="px-2.5 py-1 text-[#0E7490] hover:bg-cyan-50 rounded font-bold"
                        >
                          View
                        </button>
                        <button
                          onClick={() => handleDownloadSinglePdf(r.report_number)}
                          className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-semibold inline-flex items-center gap-1"
                        >
                          <Download size={12} />
                          <span>PDF</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-30"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-30"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
