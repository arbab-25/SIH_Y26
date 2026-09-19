import React, { useState } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { ShieldCheck, AlertTriangle, AlertCircle, FileText, Download, Send, ChevronRight } from 'lucide-react';
import { ScanResult } from '../types';
import { translations } from '../i18n/translations';
import { api } from '../utils/api';
import { ReportProductModal } from '../components/ReportProductModal';

interface ScanSummaryProps {
  scan: ScanResult;
  onViewDetailedAnalysis: () => void;
  lang: 'en' | 'hi';
}

const ConfidenceTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: { color: string; name: string; value: number; fields?: string[] } }> }) => {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="bg-slate-900 text-white p-3 rounded-xl shadow-xl text-xs max-w-xs z-50">
      <p className="font-bold mb-1" style={{ color: data.color }}>{data.name}: {data.value} fields</p>
      {data.fields?.length ? <div className="space-y-0.5 text-slate-300 text-[11px]">
        {data.fields.map((field) => <div key={field}>• {field}</div>)}
      </div> : null}
    </div>
  );
};

export const ScanSummary: React.FC<ScanSummaryProps> = ({
  scan,
  onViewDetailedAnalysis,
  lang,
}) => {
  const t = translations[lang];
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [reportNumber, setReportNumber] = useState<string | null>(null);

  const verdict = scan.verdict || 'NEEDS_REVIEW';

  const getVerdictStyle = () => {
    switch (verdict) {
      case 'COMPLIANT':
        return {
          bg: 'bg-emerald-50',
          border: 'border-emerald-300',
          badge: 'bg-[#16A34A] text-white',
          icon: ShieldCheck,
          text: t.verdictCompliant,
        };
      case 'NON_COMPLIANT':
        return {
          bg: 'bg-rose-50',
          border: 'border-rose-300',
          badge: 'bg-[#DC2626] text-white',
          icon: AlertTriangle,
          text: t.verdictNonCompliant,
        };
      default:
        return {
          bg: 'bg-amber-50',
          border: 'border-amber-300',
          badge: 'bg-[#D97706] text-white',
          icon: AlertCircle,
          text: t.verdictNeedsReview,
        };
    }
  };

  const vStyle = getVerdictStyle();
  const VerdictIcon = vStyle.icon;

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      // First ensure report record is created
      let repNum = reportNumber;
      if (!repNum) {
        const repRes = await api.post('/reports', { scan_id: scan.scan_id || scan.id });
        repNum = repRes.data?.report_number;
        setReportNumber(repNum);
      }

      if (repNum) {
        const pdfRes = await api.get(`/reports/${repNum}/pdf`, { responseType: 'blob' });
        const blob = new Blob([pdfRes.data], { type: 'application/pdf' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${repNum}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Failed to download PDF:', error);
      alert('Could not download PDF. Please check server logs.');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleOpenReportModal = async () => {
    if (!reportNumber) {
      try {
        const repRes = await api.post('/reports', { scan_id: scan.scan_id || scan.id });
        setReportNumber(repRes.data?.report_number);
      } catch (error) {
        console.error('Error generating report number:', error);
      }
    }
    setReportModalOpen(true);
  };

  const pieData = scan.confidence_pie?.length > 0 ? scan.confidence_pie : [];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Banner: Big Verdict Pill & Quick Scores per §7.2 */}
      <div className={`p-6 rounded-2xl border ${vStyle.bg} ${vStyle.border} shadow-sm flex flex-col md:flex-row items-center justify-between gap-6`}>
        <div className="flex items-center gap-4">
          <div className={`h-14 w-14 rounded-2xl flex items-center justify-center ${vStyle.badge}`}>
            <VerdictIcon size={32} />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <span className={`text-base font-black px-3.5 py-1 rounded-full uppercase tracking-wider ${vStyle.badge}`}>
                {vStyle.text}
              </span>
              <span className="text-xs text-slate-500 font-semibold">
                {scan.processing_time_ms ? `Processed in ${scan.processing_time_ms}ms` : 'Processing time not available'}
              </span>
            </div>
            <h2 className="text-xl font-bold text-[#12355B] mt-1.5">
              {scan.product?.name || 'Product name not detected'}
            </h2>
            <p className="text-xs text-slate-600">
              {scan.product?.manufacturer_name || 'Manufacturer details not detected'}
            </p>
          </div>
        </div>

        {/* Score & Actions */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="bg-white px-4 py-2 rounded-xl border border-slate-200 text-center shadow-xs">
            <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{t.complianceScore}</div>
            <div className="text-xl font-black text-[#0E7490]">
                {typeof scan.compliance_score === 'number' ? `${scan.compliance_score.toFixed(1)}%` : '—'}
            </div>
          </div>

          <button
            onClick={onViewDetailedAnalysis}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-[#12355B] hover:bg-[#0F2C4C] text-white text-xs font-bold rounded-xl shadow transition-all min-h-[44px]"
          >
            <span>{t.viewDetailedAnalysis}</span>
            <ChevronRight size={16} />
          </button>

          <button
            onClick={handleDownloadPdf}
            disabled={downloadingPdf}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 text-xs font-bold rounded-xl shadow-xs transition-all min-h-[44px]"
          >
            <Download size={16} className="text-[#0E7490]" />
            <span>{downloadingPdf ? 'Generating...' : t.downloadPdf}</span>
          </button>

          <button
            onClick={handleOpenReportModal}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl shadow transition-all min-h-[44px]"
          >
            <Send size={15} />
            <span>{t.reportThisProduct}</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Extracted Data Table (Left) + OCR Confidence Pie Chart (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Extracted Data Table (7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-[#12355B] uppercase tracking-wider flex items-center gap-2">
              <FileText size={16} className="text-[#0E7490]" />
              {t.extractedDeclarations}
            </h3>
            <span className="text-xs text-slate-500 font-medium">
              {scan.extracted_fields?.length || 0} fields analyzed
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider">
                  <th className="pb-2.5">{t.fieldName}</th>
                  <th className="pb-2.5">{t.extractedValue}</th>
                  <th className="pb-2.5 text-right">{t.status}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {scan.extracted_fields?.map((f, i) => {
                  const isComp = f.status === 'COMPLIANT';
                  const isNonComp = f.status === 'NON_COMPLIANT';
                  return (
                    <tr key={i} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-2.5 font-bold text-[#12355B] capitalize">
                        {f.field_key.replace(/_/g, ' ')}
                      </td>
                      <td className="py-2.5 text-slate-700 max-w-[220px] truncate font-medium">
                        {f.field_value || <span className="text-slate-400 italic">Not Detected</span>}
                      </td>
                      <td className="py-2.5 text-right">
                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                          isComp
                            ? 'bg-emerald-100 text-emerald-800'
                            : isNonComp
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {f.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* OCR Confidence Distribution Pie Chart per §7.2 (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col justify-between space-y-4">
          <div>
            <h3 className="text-sm font-bold text-[#12355B] uppercase tracking-wider">
              {t.confidenceDistribution}
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              OCR Engine word-level confidence distribution over applicable fields
            </p>
          </div>

          {pieData.length > 0 ? (
            <div className="h-56 w-full relative flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={4} dataKey="value">
                    {pieData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                  </Pie>
                  <Tooltip content={<ConfidenceTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-56 rounded-xl border border-dashed border-slate-200 bg-slate-50 flex items-center justify-center text-center px-6 text-sm text-slate-500">
              OCR confidence distribution is unavailable for this scan.
            </div>
          )}

          {/* Average OCR Confidence & Slices Legend */}
          <div className="pt-3 border-t border-slate-100 space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-slate-700">
              <span>{t.avgConfidence}:</span>
              <span className="text-base text-[#0E7490]">
                {typeof scan.avg_ocr_confidence === 'number' ? `${scan.avg_ocr_confidence.toFixed(1)}%` : '—'}
              </span>
            </div>

            <div className="flex flex-wrap gap-2 text-[11px]">
              {pieData.map((slice, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: slice.color }} />
                  <span className="text-slate-600">{slice.name} ({slice.value})</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Visible Legal Disclaimer per §3 */}
      <div className="p-4 bg-slate-100 border border-slate-300 rounded-2xl text-xs text-slate-600 text-center font-medium">
        <strong>Statutory Notice:</strong> {scan.disclaimer || t.disclaimer}
      </div>

      {/* Escalation Modal */}
      <ReportProductModal
        isOpen={reportModalOpen}
        onClose={() => setReportModalOpen(false)}
        reportNumber={reportNumber || scan.scan_id?.substring(0, 8) || 'CMD-REPORT'}
        productName={scan.product?.name || 'Pre-packaged Commodity'}
        lang={lang}
      />
    </div>
  );
};
