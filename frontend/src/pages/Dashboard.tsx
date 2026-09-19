import React, { useState, useEffect, useCallback } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import { BarChart2, TrendingUp, FileCheck, Layers, RefreshCw, DatabaseZap } from 'lucide-react';
import { api } from '../utils/api';
import { DashboardStats } from '../types';
import { translations } from '../i18n/translations';

interface DashboardProps {
  lang: 'en' | 'hi';
}

export const Dashboard: React.FC<DashboardProps> = ({ lang }) => {
  const t = translations[lang];
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await api.get('/dashboard/stats');
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load dashboard stats:', err);
      setLoadError('Inspection analytics could not be loaded. Check the service connection and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchStats();
  }, [fetchStats]);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Title */}
      <div className="cm-card p-6 sm:p-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold tracking-[0.16em] uppercase text-[#0E7490] mb-2">Operational intelligence</p>
          <h1 className="text-2xl font-extrabold text-[#12355B]">{t.navDashboard}</h1>
          <p className="text-sm text-slate-600 mt-2">Inspection volumes, OCR quality, and rule trends from recorded scans.</p>
        </div>
        <button onClick={() => void fetchStats()} disabled={loading} className="btn-secondary shrink-0">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh data
        </button>
      </div>

      {loadError && <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">{loadError}</div>}

      {/* 4 Stat Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Scans Today</span>
            <FileCheck size={18} className="text-[#0E7490]" />
          </div>
          <div className="text-2xl font-black text-[#12355B]">{loading ? '—' : (stats?.scans_today ?? 0)}</div>
          <p className="text-[11px] text-slate-400 mt-1">Recorded field checks</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Past 7 Days</span>
            <TrendingUp size={18} className="text-[#16A34A]" />
          </div>
          <div className="text-2xl font-black text-[#12355B]">{loading ? '—' : (stats?.scans_this_week ?? 0)}</div>
          <p className="text-[11px] text-slate-400 mt-1">Recorded in the last seven days</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Avg OCR Conf.</span>
            <Layers size={18} className="text-[#0E7490]" />
          </div>
          <div className="text-2xl font-black text-[#0E7490]">
            {loading ? '—' : (typeof stats?.average_ocr_confidence === 'number' ? `${stats.average_ocr_confidence.toFixed(1)}%` : '—')}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Word-level OCR confidence</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Total Evaluated</span>
            <BarChart2 size={18} className="text-indigo-600" />
          </div>
          <div className="text-2xl font-black text-[#12355B]">{loading ? '—' : (stats?.total_scans ?? 0)}</div>
          <p className="text-[11px] text-slate-400 mt-1">Stored inspection records</p>
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

          {stats?.top_violated_rules?.length ? <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={stats.top_violated_rules}
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
          </div> : <EmptyAnalytics label="No recorded rule violations yet." />}
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

          {stats?.compliance_trend?.length ? <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={stats.compliance_trend}
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
          </div> : <EmptyAnalytics label="Trend data will appear after completed scans are recorded." />}
        </div>
      </div>

      {/* Top Non-Compliant Manufacturers Table */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-[#12355B] uppercase tracking-wider">
          Top Non-Compliant Manufacturers & Packers
        </h3>
        {stats?.top_non_compliant_manufacturers?.length ? <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 font-bold uppercase">
                <th className="pb-2">Manufacturer / Brand</th>
                <th className="pb-2">Flagged Violations</th>
                <th className="pb-2">Enforcement Priority</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {stats.top_non_compliant_manufacturers.map((m, i) => (
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
        </div> : <EmptyAnalytics label="No manufacturer trends are available yet." />}
      </div>
    </div>
  );
};

const EmptyAnalytics: React.FC<{ label: string }> = ({ label }) => (
  <div className="h-64 rounded-xl border border-dashed border-slate-200 bg-slate-50 flex flex-col items-center justify-center text-center px-6">
    <DatabaseZap size={24} className="text-slate-400 mb-3" />
    <p className="text-sm font-semibold text-slate-600">{label}</p>
    <p className="text-xs text-slate-400 mt-1">Only real inspection records are shown in this workspace.</p>
  </div>
);
