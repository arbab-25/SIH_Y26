import React from 'react';
import { X, BookOpen, AlertCircle, Shield, CheckCircle } from 'lucide-react';
import { translations } from '../i18n/translations';

interface HelpDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onStartTour: () => void;
  lang: 'en' | 'hi';
}

export const HelpDrawer: React.FC<HelpDrawerProps> = ({
  isOpen,
  onClose,
  onStartTour,
  lang,
}) => {
  const t = translations[lang];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/50 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col justify-between overflow-y-auto">
        <div>
          {/* Header */}
          <div className="p-5 bg-[#12355B] text-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="text-cyan-400" size={20} />
              <h2 className="font-bold text-base">{t.helpDrawerTitle}</h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-slate-300 hover:text-white rounded-lg min-h-[44px] min-w-[44px] flex items-center justify-center"
              aria-label="Close"
            >
              <X size={20} />
            </button>
          </div>

          {/* Body Guide */}
          <div className="p-6 space-y-6 text-sm text-slate-700">
            <div>
              <h3 className="font-bold text-[#12355B] mb-2 flex items-center gap-2">
                <CheckCircle size={16} className="text-[#16A34A]" />
                How to photograph packages
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Position the package on a flat, well-lit surface. Align the principal display panel (PDP) straight inside the camera guide without heavy shadows or reflections. If the image is blurry, hold steady and retake.
              </p>
            </div>

            <div>
              <h3 className="font-bold text-[#12355B] mb-2 flex items-center gap-2">
                <AlertCircle size={16} className="text-[#0E7490]" />
                Verdicts & Fail-Closed Logic
              </h3>
              <ul className="text-xs text-slate-600 space-y-1.5 list-disc pl-4">
                <li><strong className="text-[#16A34A]">COMPLIANT:</strong> All mandatory Rule 6 declarations pass regex and standard size checks.</li>
                <li><strong className="text-[#DC2626]">NON-COMPLIANT:</strong> At least one statutory rule violated (e.g. non-standard pack size, missing tax statement).</li>
                <li><strong className="text-[#D97706]">NEEDS REVIEW:</strong> Field confidence &lt; 75% or missing dimension input. Manual inspector inspection required.</li>
              </ul>
            </div>

            <div>
              <h3 className="font-bold text-[#12355B] mb-2 flex items-center gap-2">
                <BookOpen size={16} className="text-amber-600" />
                Statutory Citations
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                All non-compliances link directly to the exact legal text in the official Rule Book parsed from RULE_BOOK.pdf. Statutory penalty ranges (Rule 32 & 32A) are displayed for reference.
              </p>
            </div>

            <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900">
              <strong>Mandatory Notice:</strong> Always verify against physical packaging before serving compounding notices or making seizures.
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            onClick={onStartTour}
            className="text-xs font-bold text-[#0E7490] hover:underline"
          >
            Launch 3-Step Guided Tour
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#12355B] text-white rounded-xl text-xs font-semibold"
          >
            Close Guide
          </button>
        </div>
      </div>
    </div>
  );
};
