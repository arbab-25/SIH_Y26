import React, { useState } from 'react';
import { X, Send, AlertTriangle, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../utils/api';
import { translations } from '../i18n/translations';

interface ReportProductModalProps {
  isOpen: boolean;
  onClose: () => void;
  reportNumber: string;
  productName: string;
  lang: 'en' | 'hi';
}

export const ReportProductModal: React.FC<ReportProductModalProps> = ({
  isOpen,
  onClose,
  reportNumber,
  productName,
  lang
}) => {
  const t = translations[lang];
  const [reason, setReason] = useState('Confirmed Non-Compliance with Legal Metrology Rules');
  const [remarks, setRemarks] = useState('');
  const [attachPdf, setAttachPdf] = useState(true);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatusMsg(null);

    try {
      const res = await api.post(`/reports/${reportNumber}/email`, {
        reason,
        remarks,
        attach_pdf: attachPdf,
        recipient_email: 'arbab.momin.2008@gmail.com'
      });

      if (res.data?.status === 'sent') {
        setStatusMsg({
          type: 'success',
          text: 'Notice dispatched successfully to Enforcement Desk (arbab.momin.2008@gmail.com)!'
        });
        setTimeout(() => {
          onClose();
        }, 2500);
      } else {
        setStatusMsg({
          type: 'error',
          text: `Delivery status: ${res.data?.status || 'retrying'} — ${res.data?.error || 'Check mailbox logs'}`
        });
      }
    } catch (err: any) {
      setStatusMsg({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to dispatch report email. Please retry.'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="bg-[#12355B] p-5 text-white flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="text-amber-400" size={20} />
            <div>
              <h2 className="font-bold text-base">{t.reportModalTitle}</h2>
              <p className="text-xs text-cyan-200">{reportNumber} — {productName}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-300 hover:text-white rounded-lg min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="Close"
          >
            <X size={19} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {statusMsg && (
            <div className={`flex items-start gap-2.5 p-3.5 rounded-xl text-xs ${
              statusMsg.type === 'success'
                ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                : 'bg-rose-50 border border-rose-200 text-rose-800'
            }`}>
              {statusMsg.type === 'success' ? (
                <CheckCircle size={16} className="text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle size={16} className="text-rose-600 shrink-0 mt-0.5" />
              )}
              <span>{statusMsg.text}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              {t.reportReason}
            </label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:bg-white focus:border-[#0E7490] focus:ring-1 focus:ring-[#0E7490] outline-none min-h-[44px]"
            >
              <option value="Confirmed Non-Compliance with Legal Metrology Rules">{t.reasonNonCompliance}</option>
              <option value="Misleading or Altered MRP Declaration">{t.reasonMisleadingMrp}</option>
              <option value="Suspected Short Weight / Underfilled Quantity">{t.reasonShortQuantity}</option>
              <option value="Suspected Counterfeit or Unregistered Packer">{t.reasonCounterfeit}</option>
              <option value="Other Statutory Breach">{t.reasonOther}</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              {t.remarks}
            </label>
            <textarea
              rows={3}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="Provide field observations, store details, or package defect notes..."
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] focus:ring-1 focus:ring-[#0E7490] outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="attachPdf"
              checked={attachPdf}
              onChange={(e) => setAttachPdf(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-[#0E7490] focus:ring-[#0E7490]"
            />
            <label htmlFor="attachPdf" className="text-xs font-semibold text-slate-700 select-none">
              Attach generated official compliance PDF report to escalation email
            </label>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 text-slate-600 hover:bg-slate-100 rounded-xl text-sm font-semibold transition-colors min-h-[44px]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2.5 bg-[#DC2626] hover:bg-[#B91C1C] text-white rounded-xl text-sm font-bold shadow transition-all min-h-[44px] disabled:opacity-50"
            >
              {loading ? (
                <span>{t.sending}</span>
              ) : (
                <>
                  <Send size={15} />
                  <span>{t.sendReportAction}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
