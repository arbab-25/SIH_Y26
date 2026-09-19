import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { MobileTabBar } from './components/MobileTabBar';
import { LoginModal } from './components/LoginModal';
import { HelpDrawer } from './components/HelpDrawer';
import { GuidedTour } from './components/GuidedTour';
import { ScanUpload } from './pages/ScanUpload';
import { ScanSummary } from './pages/ScanSummary';
import { DetailedAnalysis } from './pages/DetailedAnalysis';
import { RuleBook } from './pages/RuleBook';
import { ReportHistory } from './pages/ReportHistory';
import { ScanHistory } from './pages/ScanHistory';
import { Dashboard } from './pages/Dashboard';
import { ScanResult, User } from './types';
import { api } from './utils/api';
import { getPendingScansCount } from './utils/offlineQueue';

export function App() {
  const [activeTab, setActiveTab] = useState<string>('scan');
  const [lang, setLang] = useState<'en' | 'hi'>(() => {
    return (localStorage.getItem('cmd_lang') as 'en' | 'hi') || 'en';
  });

  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loginModalOpen, setLoginModalOpen] = useState<boolean>(false);
  const [helpDrawerOpen, setHelpDrawerOpen] = useState<boolean>(false);
  const [guidedTourOpen, setGuidedTourOpen] = useState<boolean>(false);
  const [pendingSyncCount, setPendingSyncCount] = useState<number>(0);

  // Latest Scan Data
  const [currentScan, setCurrentScan] = useState<ScanResult | null>(null);
  const [ruleDeepLink, setRuleDeepLink] = useState<string | null>(null);

  // Check initial user authentication
  useEffect(() => {
    const token = localStorage.getItem('cmd_auth_token');
    if (token) {
      api.get('/auth/me')
        .then((res) => setCurrentUser(res.data))
        .catch(() => {
          localStorage.removeItem('cmd_auth_token');
          setCurrentUser(null);
        });
    }

    // Check offline sync queue
    getPendingScansCount().then(setPendingSyncCount);

    // Listen for guest free scan limit trigger per §6
    const handleTriggerLogin = () => {
      setLoginModalOpen(true);
    };
    window.addEventListener('cmd_trigger_login', handleTriggerLogin);
    return () => window.removeEventListener('cmd_trigger_login', handleTriggerLogin);
  }, []);

  const handleToggleLang = () => {
    const next = lang === 'en' ? 'hi' : 'en';
    setLang(next);
    localStorage.setItem('cmd_lang', next);
  };

  const handleLogout = () => {
    localStorage.removeItem('cmd_auth_token');
    setCurrentUser(null);
  };

  const handleScanCompleted = (result: ScanResult) => {
    setCurrentScan(result);
    setActiveTab('analysis'); // Go directly to Detailed Analysis per user request
  };

  const handleNavigateToRule = (ruleRef: string) => {
    setRuleDeepLink(ruleRef);
    setActiveTab('rulebook');
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#172033] flex flex-col font-sans">
      {/* Top Header per §4 */}
      <Header
        lang={lang}
        onToggleLang={handleToggleLang}
        currentUser={currentUser}
        onOpenLogin={() => setLoginModalOpen(true)}
        onLogout={handleLogout}
        onOpenHelp={() => setHelpDrawerOpen(true)}
        pendingSyncCount={pendingSyncCount}
      />

      {/* Main Layout: Fixed Navy Sidebar + Content Area */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} lang={lang} />

        {/* Scrollable Content Viewport */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto pb-20 md:pb-8">
          {activeTab === 'scan' && (
            <ScanUpload
              onScanComplete={handleScanCompleted}
              lang={lang}
              onOfflineQueued={() => getPendingScansCount().then(setPendingSyncCount)}
            />
          )}

          {activeTab === 'summary' && (
            currentScan ? (
              <ScanSummary
                scan={currentScan}
                onViewDetailedAnalysis={() => setActiveTab('analysis')}
                lang={lang}
              />
            ) : (
              <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 max-w-xl mx-auto">
                <h3 className="text-base font-bold text-[#12355B] mb-2">No Active Label Scan</h3>
                <p className="text-xs text-slate-500 mb-6">
                  Please capture or upload a product packaging label to view compliance summary.
                </p>
                <button
                  onClick={() => setActiveTab('scan')}
                  className="px-5 py-2.5 bg-[#12355B] text-white rounded-xl text-xs font-bold shadow"
                >
                  Go to Scan / Upload
                </button>
              </div>
            )
          )}

          {activeTab === 'analysis' && (
            currentScan ? (
              <DetailedAnalysis
                scan={currentScan}
                onScanUpdated={(updated) => setCurrentScan(updated)}
                onNavigateToRule={handleNavigateToRule}
                lang={lang}
              />
            ) : (
              <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 max-w-xl mx-auto">
                <h3 className="text-base font-bold text-[#12355B] mb-2">No Active Label Scan</h3>
                <p className="text-xs text-slate-500 mb-6">
                  Run a scan to view detailed per-field statutory evaluations.
                </p>
                <button
                  onClick={() => setActiveTab('scan')}
                  className="px-5 py-2.5 bg-[#12355B] text-white rounded-xl text-xs font-bold shadow"
                >
                  Go to Scan / Upload
                </button>
              </div>
            )
          )}

          {activeTab === 'rulebook' && (
            <RuleBook initialRule={ruleDeepLink} lang={lang} />
          )}

          {activeTab === 'reports' && (
            <ReportHistory
              onViewReport={(_repNum) => {
                // Navigate to view report
                setActiveTab('summary');
              }}
              lang={lang}
            />
          )}

          {activeTab === 'history' && (
            <ScanHistory
              onSelectScan={(s) => {
                setCurrentScan(s);
                setActiveTab('summary');
              }}
              lang={lang}
            />
          )}

          {activeTab === 'dashboard' && <Dashboard lang={lang} />}
        </main>
      </div>

      {/* Mobile Bottom Tab Bar for viewport <768px per §4 */}
      <MobileTabBar activeTab={activeTab} setActiveTab={setActiveTab} lang={lang} />

      {/* Global Modals & Drawers */}
      <LoginModal
        isOpen={loginModalOpen}
        onClose={() => setLoginModalOpen(false)}
        onLoginSuccess={(user) => setCurrentUser(user)}
        lang={lang}
      />

      <HelpDrawer
        isOpen={helpDrawerOpen}
        onClose={() => setHelpDrawerOpen(false)}
        onStartTour={() => {
          setHelpDrawerOpen(false);
          setGuidedTourOpen(true);
        }}
        lang={lang}
      />

      <GuidedTour
        isOpen={guidedTourOpen}
        onClose={() => setGuidedTourOpen(false)}
        lang={lang}
      />
    </div>
  );
}

export default App;
