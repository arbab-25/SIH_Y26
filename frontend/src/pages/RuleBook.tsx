import React, { useState, useEffect, useCallback } from 'react';
import { Search, Bookmark } from 'lucide-react';
import { api } from '../utils/api';
import { RuleItem } from '../types';
import { translations } from '../i18n/translations';

interface RuleBookProps {
  initialRule?: string | null;
  lang: 'en' | 'hi';
}

export const RuleBook: React.FC<RuleBookProps> = ({ initialRule, lang }) => {
  const t = translations[lang];
  const [activeTab, setActiveTab] = useState<'rules' | 'schedules'>('rules');
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedChapter, setSelectedChapter] = useState<string>('all');
  const [selectedRule, setSelectedRule] = useState<RuleItem | null>(null);
  const [loading, setLoading] = useState(false);

  // Schedules state
  const [activeScheduleTab, setActiveScheduleTab] = useState<'second' | 'table1' | 'fifth'>('second');
  const [scheduleData, setScheduleData] = useState<any>(null);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      let url = '/rules';
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (selectedChapter !== 'all') params.append('chapter', selectedChapter);
      if (params.toString()) url += `?${params.toString()}`;

      const res = await api.get(url);
      setRules(res.data || []);

      if (initialRule) {
        const matched = res.data.find(
          (r: RuleItem) => r.rule_number.toLowerCase() === initialRule.toLowerCase()
        );
        if (matched) setSelectedRule(matched);
      } else {
        setSelectedRule((current) => current ?? res.data[0] ?? null);
      }
    } catch (err) {
      console.error('Failed to load rules:', err);
    } finally {
      setLoading(false);
    }
  }, [initialRule, searchQuery, selectedChapter]);

  const fetchScheduleData = useCallback(async (type: string) => {
    try {
      const res = await api.get(`/schedules/${type}`);
      setScheduleData(res.data);
    } catch (err) {
      console.error('Failed to load schedule:', err);
    }
  }, []);

  useEffect(() => {
    void fetchRules();
  }, [fetchRules]);

  useEffect(() => {
    void fetchScheduleData(activeScheduleTab);
  }, [activeScheduleTab, fetchScheduleData]);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#12355B]">{t.ruleBookTitle}</h1>
          <p className="text-xs text-slate-500 mt-1">{t.ruleBookSubtitle}</p>
        </div>

        {/* Top Tab Switcher */}
        <div className="flex bg-slate-100 p-1 rounded-xl shrink-0">
          <button
            onClick={() => setActiveTab('rules')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all min-h-[40px] ${
              activeTab === 'rules' ? 'bg-white text-[#12355B] shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Statutory Rules
          </button>
          <button
            onClick={() => setActiveTab('schedules')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all min-h-[40px] ${
              activeTab === 'schedules' ? 'bg-white text-[#12355B] shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {t.schedulesTab}
          </button>
        </div>
      </div>

      {activeTab === 'rules' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Search & Rules List (5 cols) */}
          <div className="lg:col-span-5 bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
            {/* Search Input */}
            <div className="relative">
              <Search size={16} className="absolute left-3.5 top-3.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t.searchRules}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:bg-white focus:border-[#0E7490]"
              />
            </div>

            {/* Chapter Filter */}
            <div className="flex gap-2 overflow-x-auto pb-1 text-xs">
              {['all', 'Chapter II', 'Chapter III', 'Chapter IV'].map((ch) => (
                <button
                  key={ch}
                  onClick={() => setSelectedChapter(ch)}
                  className={`px-3 py-1.5 rounded-lg font-semibold shrink-0 transition-colors ${
                    selectedChapter === ch
                      ? 'bg-[#12355B] text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {ch === 'all' ? 'All Chapters' : ch}
                </button>
              ))}
            </div>

            {/* Rules List */}
            <div className="space-y-1.5 max-h-[580px] overflow-y-auto pr-1">
              {loading ? (
                <div className="text-center py-8 text-xs text-slate-400">Loading statutory rules...</div>
              ) : rules.length === 0 ? (
                <div className="text-center py-8 text-xs text-slate-400">No matching rules found.</div>
              ) : (
                rules.map((r) => {
                  const isSelected = selectedRule?.id === r.id;
                  return (
                    <div
                      key={r.id}
                      onClick={() => setSelectedRule(r)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-cyan-50/80 border-[#0E7490] text-[#12355B] shadow-xs'
                          : 'border-slate-100 hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs uppercase tracking-wider text-[#0E7490]">
                          {r.rule_number}
                        </span>
                        <span className="text-[10px] text-slate-400">{r.chapter}</span>
                      </div>
                      <h4 className="font-semibold text-xs mt-1 truncate">{r.title}</h4>
                      {r.highlight && (
                        <p className="text-[11px] text-slate-500 italic mt-1 line-clamp-2">
                          {r.highlight}
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Quoted Text Viewer (7 cols) */}
          <div className="lg:col-span-7 bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
            {selectedRule ? (
              <div className="space-y-4">
                <div className="border-b border-slate-100 pb-4">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#0E7490] uppercase tracking-wider">
                    <Bookmark size={14} />
                    <span>{selectedRule.chapter} — {selectedRule.rule_number.toUpperCase()}</span>
                  </div>
                  <h2 className="text-lg font-bold text-[#12355B] mt-1">{selectedRule.title}</h2>
                </div>

                {/* Quoted Rule Text */}
                <div className="p-5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 leading-relaxed font-mono whitespace-pre-wrap">
                  {selectedRule.full_text}
                </div>

                {/* Statutory Reference Metadata */}
                <div className="pt-2 text-xs text-slate-500 flex flex-wrap gap-4 border-t border-slate-100">
                  {selectedRule.schedule_ref && (
                    <div>
                      <strong>Schedule Ref:</strong> {selectedRule.schedule_ref}
                    </div>
                  )}
                  {selectedRule.source_page && (
                    <div>
                      <strong>Source Page:</strong> Page {selectedRule.source_page} of RULE_BOOK.pdf
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-20 text-slate-400 text-xs">
                Select any rule on the left to read full official statutory text.
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Structured Schedules Tab per §7.4 */
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6">
          <div className="flex gap-2 border-b border-slate-200 pb-3">
            <button
              onClick={() => setActiveScheduleTab('second')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-colors ${
                activeScheduleTab === 'second'
                  ? 'bg-[#0E7490] text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {t.secondScheduleTitle}
            </button>
            <button
              onClick={() => setActiveScheduleTab('table1')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-colors ${
                activeScheduleTab === 'table1'
                  ? 'bg-[#0E7490] text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {t.tableOneTitle}
            </button>
          </div>

          {activeScheduleTab === 'second' && (
            <div className="space-y-3">
              <h3 className="font-bold text-sm text-[#12355B]">
                Second Schedule: Permitted Standard Pack Sizes for 19 Regulated Commodity Groups
              </h3>
              <p className="text-xs text-slate-500">
                Rule 5 mandates that retail packages in these 19 commodity groups must strictly conform to allowed standard quantities:
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500 font-bold uppercase">
                      <th className="pb-2">Commodity Group</th>
                      <th className="pb-2">Standard Quantities</th>
                      <th className="pb-2">Unit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {Array.isArray(scheduleData) &&
                      scheduleData.map((comm: any, i: number) => (
                        <tr key={i} className="hover:bg-slate-50">
                          <td className="py-2.5 font-bold text-[#12355B]">{comm.commodity}</td>
                          <td className="py-2.5 text-slate-700">
                            {comm.allowed_values?.slice(0, 12).join(', ')}... (multiples of 500g/ml)
                          </td>
                          <td className="py-2.5 text-slate-500">{comm.unit}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeScheduleTab === 'table1' && (
            <div className="space-y-3">
              <h3 className="font-bold text-sm text-[#12355B]">
                Rule 7(2) Table-I: Minimum Height of Numerals and Letters
              </h3>
              <p className="text-xs text-slate-500">
                Mandatory glyph height required on the Principal Display Panel (PDP):
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500 font-bold uppercase">
                      <th className="pb-2">Principal Display Panel Area (A in sq cm)</th>
                      <th className="pb-2">Min Height (Normal)</th>
                      <th className="pb-2">Min Height (Blown/Moulded/Perforated)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    <tr className="hover:bg-slate-50">
                      <td className="py-2.5 font-medium">A ≤ 50 sq cm</td>
                      <td className="py-2.5 font-bold text-[#0E7490]">1.0 mm</td>
                      <td className="py-2.5 text-slate-600">1.5 mm</td>
                    </tr>
                    <tr className="hover:bg-slate-50">
                      <td className="py-2.5 font-medium">50 &lt; A ≤ 100 sq cm</td>
                      <td className="py-2.5 font-bold text-[#0E7490]">1.5 mm</td>
                      <td className="py-2.5 text-slate-600">3.0 mm</td>
                    </tr>
                    <tr className="hover:bg-slate-50">
                      <td className="py-2.5 font-medium">100 &lt; A ≤ 500 sq cm</td>
                      <td className="py-2.5 font-bold text-[#0E7490]">2.5 mm</td>
                      <td className="py-2.5 text-slate-600">4.0 mm</td>
                    </tr>
                    <tr className="hover:bg-slate-50">
                      <td className="py-2.5 font-medium">500 &lt; A ≤ 2500 sq cm</td>
                      <td className="py-2.5 font-bold text-[#0E7490]">4.0 mm</td>
                      <td className="py-2.5 text-slate-600">6.0 mm</td>
                    </tr>
                    <tr className="hover:bg-slate-50">
                      <td className="py-2.5 font-medium">A &gt; 2500 sq cm</td>
                      <td className="py-2.5 font-bold text-[#0E7490]">6.0 mm</td>
                      <td className="py-2.5 text-slate-600">6.0 mm</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
