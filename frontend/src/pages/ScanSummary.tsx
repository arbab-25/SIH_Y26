import React, { useState } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { ShieldCheck, AlertTriangle, AlertCircle, FileText, Download, Send, ChevronRight, LogIn } from 'lucide-react';
import { ScanResult, User } from '../types';
import { translations } from '../i18n/translations';
import { api } from '../utils/api';
import { ReportProductModal } from '../components/ReportProductModal';

interface ScanSummaryProps {
  scan: ScanResult;
  compact?: boolean;
  onViewDetailedAnalysis: () => void;
  currentUser?: User | null;
  onRequireLogin?: () => void;
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
  compact = false,
  onViewDetailedAnalysis,
  currentUser,
  onRequireLogin,
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

  // Reports require an account — first report triggers the sign-in popup per §6
  const handleOpenReportModal = async () => {
    if (!currentUser) {
      onRequireLogin?.();
      return;
    }
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
  const violations = scan.violations ?? [];
  const nonCompliantCount = scan.extracted_fields?.filter((f) => f.status === 'NON_COMPLIANT').length ?? 0;
  // A declaration the engine found missing (for example an absent best before date,
  // or a manufacturer with no PIN code) has no extracted-field row of its own, so the
  // failed-declaration count must consider violations too — otherwise a scan the engine
  // rejected would still read as "all declarations are compliant" here.
  const failedDeclarationCount = Math.max(violations.length, nonCompliantCount);

  if (compact) {
    // Compact inline variant shown directly beneath the Scan / Upload workspace
    return (
      <div className="max-w-5xl mx-auto">
        <div className={`p-5 rounded-2xl border ${vStyle.bg} ${vStyle.border} shadow-sm space-y-4`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className={`h-11 w-11 rounded-xl flex items-center justify-center ${vStyle.badge}`}>
                <VerdictIcon size={24} />
              </div>
              <div>
                <span className={`inline-block text-[11px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider ${vStyle.badge}`}>
                  {vStyle.text}
                </span>
                <h3 className="text-sm font-bold text-[#12355B] mt-1 truncate max-w-[420px]">
                  {scan.product?.name || 'Product name not detected'}
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="bg-white px-3 py-1.5 rounded-xl border border-slate-200 text-center">
                <div className="text-[10px] font-bold text-slate-500 uppercase">{t.complianceScore}</div>
                <div className="text-base font-black text-[#0E7490]">
                  {typeof scan.compliance_score === 'number' ? `${scan.compliance_score.toFixed(1)}%` : '—'}
                </div>
              </div>
              <button
                onClick={onViewDetailedAnalysis}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-[#12355B] hover:bg-[#0F2C4C] text-white text-xs font-bold rounded-xl shadow transition-all min-h-[40px]"
              >
                <span>{t.viewDetailedAnalysis}</span>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>

          {/* Violation summary — non-compliances highlighted red */}
          {failedDeclarationCount > 0 ? (
            <div className="flex items-start gap-2.5 p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 font-semibold">
              <AlertTriangle size={16} className="text-rose-600 shrink-0 mt-0.5" />
              <span>
                {lang === 'hi'
                  ? `${failedDeclarationCount} घोषणाएँ नियमों का उल्लंघन करती हैं (लाल रंग में चिह्नित)।`
                  : `${failedDeclarationCount} declaration${failedDeclarationCount === 1 ? '' : 's'} violate statutory rules — highlighted in red below.`}
              </span>
            </div>
          ) : (
            <div className="flex items-start gap-2.5 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 font-semibold">
              <ShieldCheck size={16} className="text-emerald-600 shrink-0 mt-0.5" />
              <span>
                {lang === 'hi' ? 'सभी स्कैन की गई घोषणाएँ अनुपालित हैं।' : 'All scanned declarations are compliant.'}
              </span>
            </div>
          )}

          {/* Cited rule breaches, including declarations the engine found missing */}
          {violations.length > 0 && (
            <ul className="space-y-2">
              {violations.map((v, i) => (
                <li
                  key={v.id ?? `${v.field_key}-${i}`}
                  className="p-3 rounded-xl border border-rose-200 bg-white/80 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-rose-700 uppercase tracking-wider">
                      {v.rule_ref?.toUpperCase()}
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800">
                      {v.severity}
                    </span>
                  </div>
                  <p className="text-rose-900 font-semibold mt-1">
                    {lang === 'hi' && v.message_hi ? v.message_hi : v.message_en}
                  </p>
                  {v.suggested_fix && (
                    <p className="text-[#0E7490] font-bold mt-1">
                      {t.suggestedFix}: {v.suggested_fix}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* Key extracted fields with red highlighting on non-compliance */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {scan.extracted_fields?.slice(0, 6).map((f, i) => {
              const isNonComp = f.status === 'NON_COMPLIANT';
              return (
                <div
                  key={i}
                  className={`p-2.5 rounded-xl border text-xs ${
                    isNonComp
                      ? 'bg-rose-50 border-rose-300 text-rose-900'
                      : f.status === 'COMPLIANT'
                      ? 'bg-white border-slate-200 text-slate-700'
                      : 'bg-amber-50 border-amber-200 text-amber-900'
                  }`}
                >
                  <div className="text-[10px] font-bold uppercase tracking-wider opacity-70 truncate">
                    {f.field_key.replace(/_/g, ' ')}
                  </div>
                  <div className={`font-bold truncate mt-0.5 ${isNonComp ? 'text-rose-700' : ''}`}>
                    {f.field_value || <span className="italic opacity-60">Not Detected</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

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
            title={currentUser ? undefined : 'Sign in to report this product'}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl shadow transition-all min-h-[44px]"
          >
            {!currentUser && <LogIn size={15} />}
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
                    <tr key={i} className={`transition-colors ${isNonComp ? 'bg-rose-50/70 hover:bg-rose-50' : 'hover:bg-slate-50/80'}`}>
                      <td className={`py-2.5 font-bold capitalize ${isNonComp ? 'text-rose-700' : 'text-[#12355B]'}`}>
                        {f.field_key.replace(/_/g, ' ')}
                      </td>
                      <td className={`py-2.5 max-w-[220px] truncate font-medium ${isNonComp ? 'text-rose-800 font-bold' : 'text-slate-700'}`}>
                        {f.field_value || <span className="text-slate-400 italic">Not Detected</span>}
                      </td>
                      <td className="py-2.5 text-right">
                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                          isComp
                            ? 'bg-emerald-100 text-emerald-800'
                            : isNonComp
                            ? 'bg-rose-100 text-rose-800 ring-1 ring-rose-300'
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
