import React, { useState } from 'react';
import { Sparkles, ArrowRight, Check } from 'lucide-react';

interface GuidedTourProps {
  isOpen: boolean;
  onClose: () => void;
  lang: 'en' | 'hi';
}

export const GuidedTour: React.FC<GuidedTourProps> = ({ isOpen, onClose, lang }) => {
  const [step, setStep] = useState(0);

  if (!isOpen) return null;

  const steps = [
    {
      title: lang === 'en' ? 'Step 1: Capture or Upload Package' : 'चरण 1: पैकेज फोटो लें या अपलोड करें',
      desc: lang === 'en'
        ? 'Click "Capture from Camera" on your phone or upload label pictures from files. Select the commodity category (Food, Cosmetics, etc.) to trigger specialized rules.'
        : 'अपने फोन के कैमरे से फोटो लें या फाइलों से अपलोड करें। संबंधित नियमों को सक्रिय करने के लिए वस्तु श्रेणी चुनें।'
    },
    {
      title: lang === 'en' ? 'Step 2: Instant Compliance Verdict' : 'चरण 2: त्वरित विधिक अनुपालन निर्णय',
      desc: lang === 'en'
        ? 'Our deterministic rule engine cross-checks declarations against the Legal Metrology Rules, 2011 and displays an OCR confidence distribution pie chart.'
        : 'हमारा नियम इंजन विधिक माप विज्ञान नियम, 2011 के विरुद्ध घोषणाओं की जांच करता है और विश्वसनीयता पाई चार्ट दिखाता है।'
    },
    {
      title: lang === 'en' ? 'Step 3: Override, PDF & Email Escalation' : 'चरण 3: संशोधन, पीडीएफ एवं ईमेल रिपोर्ट',
      desc: lang === 'en'
        ? 'Correct misread fields with inspector overrides, download an official PDF report with cited rules, or escalate non-compliances via email in one click.'
        : 'निरीक्षक संशोधन द्वारा मान सुधारें, पीडीएफ रिपोर्ट डाउनलोड करें या एक क्लिक में प्राधिकारी को ईमेल भेजें।'
    }
  ];

  const handleNext = () => {
    if (step < steps.length - 1) {
      setStep(step + 1);
    } else {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md bg-white rounded-2xl p-6 shadow-2xl border border-slate-200">
        <div className="flex items-center gap-2 text-[#0E7490] font-bold text-xs uppercase tracking-wider mb-2">
          <Sparkles size={16} />
          <span>Inspector Quick Tour ({step + 1} of {steps.length})</span>
        </div>

        <h3 className="text-lg font-bold text-[#12355B] mb-2">{steps[step].title}</h3>
        <p className="text-sm text-slate-600 leading-relaxed mb-6">{steps[step].desc}</p>

        <div className="flex items-center justify-between pt-4 border-t border-slate-100">
          <div className="flex gap-1.5">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`h-2 rounded-full transition-all ${
                  i === step ? 'w-6 bg-[#0E7490]' : 'w-2 bg-slate-200'
                }`}
              />
            ))}
          </div>

          <button
            onClick={handleNext}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#12355B] hover:bg-[#0F2C4C] text-white rounded-xl text-xs font-bold shadow transition-all min-h-[44px]"
          >
            <span>{step === steps.length - 1 ? (lang === 'en' ? 'Finish Tour' : 'समाप्त') : (lang === 'en' ? 'Next' : 'आगे')}</span>
            {step === steps.length - 1 ? <Check size={16} /> : <ArrowRight size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
};
