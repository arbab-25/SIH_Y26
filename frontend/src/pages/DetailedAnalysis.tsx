import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Edit3, CheckCircle2, AlertTriangle, AlertCircle, ExternalLink } from 'lucide-react';
import { ScanResult, ExtractedFieldItem } from '../types';
import { translations } from '../i18n/translations';
import { api } from '../utils/api';

interface DetailedAnalysisProps {
  scan: ScanResult;
  onScanUpdated: (updatedScan: ScanResult) => void;
  onNavigateToRule?: (ruleNumber: string) => void;
  lang: 'en' | 'hi';
}

export const DetailedAnalysis: React.FC<DetailedAnalysisProps> = ({
  scan,
  onScanUpdated,
  onNavigateToRule,
  lang,
}) => {
  const t = translations[lang];
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [overrideKey, setOverrideKey] = useState<string | null>(null);
  const [overrideValue, setOverrideValue] = useState<string>('');
  const [overrideReason, setOverrideReason] = useState<string>('');
  const [savingOverride, setSavingOverride] = useState(false);

  const toggleAccordion = (key: string) => {
    setExpandedKey(expandedKey === key ? null : key);
  };

  const handleStartOverride = (field: ExtractedFieldItem) => {
    setOverrideKey(field.field_key);
    setOverrideValue(field.field_value || '');
    setOverrideReason('Physical package label verified by inspector');
  };

  const handleSaveOverride = async (fieldKey: string) => {
    setSavingOverride(true);
    try {
      await api.patch(`/scans/${scan.scan_id || scan.id}/fields/${fieldKey}`, {
        new_value: overrideValue,
        reason: overrideReason,
      });

      // Refetch updated scan
      const res = await api.get(`/scans/${scan.scan_id || scan.id}`);
      onScanUpdated(res.data);
      setOverrideKey(null);
    } catch (err) {
      console.error('Failed to submit override:', err);
      alert('Could not record override. Check server connection.');
    } finally {
      setSavingOverride(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#12355B]">{t.analysisTitle}</h1>
          <p className="text-xs text-slate-500 mt-1">
            Examine per-declaration legal evaluations, quoted statutory text, and amend misread fields
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold text-slate-600">Overall Verdict:</span>
          <span className={`px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider ${
            scan.verdict === 'COMPLIANT'
              ? 'bg-[#16A34A] text-white'
              : scan.verdict === 'NON_COMPLIANT'
              ? 'bg-[#DC2626] text-white'
              : 'bg-[#D97706] text-white'
          }`}>
            {scan.verdict}
          </span>
        </div>
      </div>

      {/* Field Accordion List */}
      <div className="space-y-3">
        {scan.extracted_fields?.map((field) => {
          const isExpanded = expandedKey === field.field_key;
          const isEditing = overrideKey === field.field_key;

          // Find corresponding violation if any
          const viol = scan.violations?.find(
            (v) => v.field_key === field.field_key || field.field_key.includes(v.field_key)
          );

          const isCompliant = field.status === 'COMPLIANT';
          const isNonCompliant = field.status === 'NON_COMPLIANT';

          return (
            <div
              key={field.field_key}
              className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden transition-all"
            >
              {/* Accordion Row Header */}
              <div
                onClick={() => toggleAccordion(field.field_key)}
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                    isCompliant
                      ? 'bg-emerald-100 text-[#16A34A]'
                      : isNonCompliant
                      ? 'bg-rose-100 text-[#DC2626]'
                      : 'bg-amber-100 text-[#D97706]'
                  }`}>
                    {isCompliant ? (
                      <CheckCircle2 size={18} />
                    ) : isNonCompliant ? (
                      <AlertTriangle size={18} />
                    ) : (
                      <AlertCircle size={18} />
                    )}
                  </div>

                  <div className="truncate">
                    <h2 className="text-sm font-bold text-[#12355B] capitalize">
                      {field.field_key.replace(/_/g, ' ')}
                    </h2>
                    <p className="text-xs text-slate-500 truncate mt-0.5">
                      {field.field_value || <span className="italic text-slate-400">Not Detected</span>}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  {/* OCR Confidence Badge */}
                  <span className="hidden sm:inline-block text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                    {field.confidence.toFixed(1)}% conf
                  </span>

                  {/* Verdict Chip */}
                  <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${
                    isCompliant
                      ? 'bg-emerald-100 text-emerald-800'
                      : isNonCompliant
                      ? 'bg-rose-100 text-rose-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}>
                    {field.status}
                  </span>

                  {isExpanded ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
                </div>
              </div>

              {/* Accordion Content Details */}
              {isExpanded && (
                <div className="p-5 border-t border-slate-100 bg-slate-50/50 space-y-4 text-xs animate-fade-in">
                  {/* Quoted Rule Reference & Citation */}
                  {viol && (
                    <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-rose-900 uppercase tracking-wider flex items-center gap-1.5">
                          <AlertTriangle size={14} className="text-rose-600" />
                          Violation Notice: {viol.rule_ref.toUpperCase()}
                        </span>
                        {onNavigateToRule && (
                          <button
                            onClick={() => onNavigateToRule(viol.rule_ref)}
                            className="text-xs font-bold text-[#0E7490] hover:underline flex items-center gap-1"
                          >
                            <span>Read in Rule Book</span>
                            <ExternalLink size={12} />
                          </button>
                        )}
                      </div>
                      <p className="text-slate-800 font-medium">{viol.message_en}</p>
                      {viol.suggested_fix && (
                        <p className="text-[#0E7490] font-bold">
                          {t.suggestedFix}: {viol.suggested_fix}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Inspector Override Form per §7.3 */}
                  {isEditing ? (
                    <div className="p-4 bg-white border border-[#0E7490] rounded-xl space-y-3 shadow-sm">
                      <h3 className="font-bold text-[#12355B] uppercase tracking-wider">
                        Manual Inspector Override
                      </h3>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">
                          Correct Value (as stamped on physical carton)
                        </label>
                        <input
                          type="text"
                          value={overrideValue}
                          onChange={(e) => setOverrideValue(e.target.value)}
                          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs outline-none focus:border-[#0E7490]"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">
                          Reason for amendment
                        </label>
                        <input
                          type="text"
                          value={overrideReason}
                          onChange={(e) => setOverrideReason(e.target.value)}
                          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs outline-none focus:border-[#0E7490]"
                        />
                      </div>
                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setOverrideKey(null)}
                          className="px-3 py-1.5 text-slate-600 hover:bg-slate-100 rounded-lg text-xs font-semibold"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          disabled={savingOverride}
                          onClick={() => handleSaveOverride(field.field_key)}
                          className="px-4 py-1.5 bg-[#0E7490] hover:bg-[#0c6178] text-white rounded-lg text-xs font-bold shadow-xs"
                        >
                          {savingOverride ? 'Saving...' : 'Confirm & Re-evaluate'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-slate-500">
                        Extracted text bounding box detected with confidence ratio: {(field.confidence / 100).toFixed(2)}
                      </span>
                      <button
                        onClick={() => handleStartOverride(field)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-cyan-50 text-[#0E7490] border border-[#0E7490]/30 rounded-lg font-bold transition-colors min-h-[38px]"
                      >
                        <Edit3 size={13} />
                        <span>{t.overrideAction}</span>
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
