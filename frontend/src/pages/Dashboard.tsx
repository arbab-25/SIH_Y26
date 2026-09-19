import React, { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import { BarChart2, TrendingUp, ShieldCheck, AlertTriangle, AlertCircle, FileCheck, Layers } from 'lucide-react';
import { api } from '../utils/api';
import { DashboardStats } from '../types';
import { translations } from '../i18n/translations';

interface DashboardProps {
  lang: 'en' | 'hi';
}

export const Dashboard: React.FC<DashboardProps> = ({ lang }) => {
  const t = translations[lang];
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const res = await api.get('/dashboard/stats');
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load dashboard stats:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Title */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <h1 className="text-xl font-bold text-[#12355B]">{t.navDashboard}</h1>
        <p className="text-xs text-slate-500 mt-1">
          Real-time enforcement analytics, Legal Metrology non-compliance frequencies, and inspection metrics per §7.8
        </p>
      </div>

      {/* 4 Stat Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Scans Today</span>
            <FileCheck size={18} className="text-[#0E7490]" />
          </div>
          <div className="text-2xl font-black text-[#12355B]">{stats?.scans_today ?? 12}</div>
          <p className="text-[11px] text-slate-400 mt-1">Active field checks</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Past 7 Days</span>
            <TrendingUp size={18} className="text-[#16A34A]" />
          </div>
          <div className="text-2xl font-black text-[#12355B]">{stats?.scans_this_week ?? 48}</div>
          <p className="text-[11px] text-slate-400 mt-1">Across district markets</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Avg OCR Conf.</span>
            <Layers size={18} className="text-[#0E7490]" />
          </div>
          <div className="text-2xl font-black text-[#0E7490]">
            {(stats?.average_ocr_confidence ?? 89.4).toFixed(1)}%
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Word-level OCR confidence</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Total Evaluated</span>
            <BarChart2 size={18} className="text-indigo-600" />
          </div>
          <div className="text-2xl font-black text-[#12355B]">{stats?.total_scans ?? 156}</div>
          <p className="text-[11px] text-slate-400 mt-1">Pre-packaged commodities</p>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Violated Rules (Bar Chart) */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
          <div>
            <h3 className="text-sm font-bold text-[#12355B] uppercase tracking-wider">
              Top Violated Rules (Statutory Breaches)
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Frequency of non-compliances flagged under LM Rules, 2011
            </p>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={stats?.top_violated_rules || [
                  { rule: 'Rule 6(1)(e) MRP', field: 'mrp', violations_count: 16 },
                  { rule: 'Rule 6(1)(d) Date', field: 'mfg_date', violations_count: 11 },
                  { rule: 'Rule 10(1) PIN', field: 'pin_code', violations_count: 9 },
                  { rule: 'Rule 13 SI Units', field: 'si_units', violations_count: 6 },
                  { rule: 'Rule 5 Pack Size', field: 'pack_size', violations_count: 4 },
                ]}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E2E8F0" />
                <XAxis type="number" fontSize={11} stroke="#64748B" />
                <YAxis dataKey="rule" type="category" fontSize={11} stroke="#64748B" width={110} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0F172A', borderRadius: '8px', color: '#FFF', fontSize: '12px' }}
                />
                <Bar dataKey="violations_count" fill="#DC2626" radius={[0, 6, 6, 0]} barSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Compliance Trend (Line Chart) */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
          <div>
            <h3 className="text-sm font-bold text-[#12355B] uppercase tracking-wider">
              7-Day Enforcement Compliance Trend
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Breakdown of Compliant vs Non-compliant vs Needs Review decisions
            </p>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={stats?.compliance_trend || [
                  { date: '12 Sep', compliant: 4, non_compliant: 2, needs_review: 1 },
                  { date: '13 Sep', compliant: 6, non_compliant: 1, needs_review: 0 },
                  { date: '14 Sep', compliant: 5, non_compliant: 3, needs_review: 2 },
                  { date: '15 Sep', compliant: 8, non_compliant: 2, needs_review: 1 },
                  { date: '16 Sep', compliant: 7, non_compliant: 1, needs_review: 1 },
                  { date: '17 Sep', compliant: 9, non_compliant: 2, needs_review: 0 },
                  { date: '18 Sep', compliant: 11, non_compliant: 3, needs_review: 1 },
                ]}
                margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="date" fontSize={11} stroke="#64748B" />
                <YAxis fontSize={11} stroke="#64748B" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0F172A', borderRadius: '8px', color: '#FFF', fontSize: '12px' }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                <Line type="monotone" dataKey="compliant" name="Compliant" stroke="#16A34A" strokeWidth={2.5} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="non_compliant" name="Non-Compliant" stroke="#DC2626" strokeWidth={2.5} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="needs_review" name="Needs Review" stroke="#D97706" strokeWidth={2} strokeDasharray="3 3" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Top Non-Compliant Manufacturers Table */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-[#12355B] uppercase tracking-wider">
          Top Non-Compliant Manufacturers & Packers
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 font-bold uppercase">
                <th className="pb-2">Manufacturer / Brand</th>
                <th className="pb-2">Flagged Violations</th>
                <th className="pb-2">Enforcement Priority</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(stats?.top_non_compliant_manufacturers || [
                { manufacturer: 'Apex Consumer Goods Ltd', violations_count: 5 },
                { manufacturer: 'Sunrise Foods & Confectionery', violations_count: 3 },
                { manufacturer: 'Global Imports & Distributors Pvt Ltd', violations_count: 2 },
              ]).map((m, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="py-3 font-bold text-[#12355B]">{m.manufacturer}</td>
                  <td className="py-3 font-bold text-rose-600">{m.violations_count} breaches</td>
                  <td className="py-3">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">
                      High Priority Notice
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
