import React, { useState, useEffect, useCallback } from 'react';
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
import { ErrorBoundary } from './components/ErrorBoundary';
import { ScanResult, User } from './types';
import { api } from './utils/api';
import { getPendingScansCount } from './utils/offlineQueue';
import { translations } from './i18n/translations';

export function App() {
  const [activeTab, setActiveTab] = useState<string>('scan');
  const [lang, setLang] = useState<'en' | 'hi'>(() => {
    return (localStorage.getItem('cmd_lang') as 'en' | 'hi') || 'en';
  });

  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loginModalOpen, setLoginModalOpen] = useState<boolean>(false);
  const [loginNotice, setLoginNotice] = useState<string | null>(null);
  const [helpDrawerOpen, setHelpDrawerOpen] = useState<boolean>(false);
  const [guidedTourOpen, setGuidedTourOpen] = useState<boolean>(false);
  const [pendingSyncCount, setPendingSyncCount] = useState<number>(0);

  // Latest Scan Data
  const [currentScan, setCurrentScan] = useState<ScanResult | null>(null);
  const [ruleDeepLink, setRuleDeepLink] = useState<string | null>(null);

  const t = translations[lang];

  const openLogin = useCallback((notice?: string) => {
    setLoginNotice(notice || null);
    setLoginModalOpen(true);
  }, []);

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

    // 401 from any API call (expired/missing session) opens the sign-in modal.
    // Guest mode removed: scanning, reports and history all require sign-in.
    const handleTriggerLogin = () => {
      openLogin(
        lang === 'hi'
          ? 'स्कैन करने के लिए कृपया साइन इन करें।'
          : 'Please sign in to scan labels and manage reports.'
      );
    };
    window.addEventListener('cmd_trigger_login', handleTriggerLogin);
    return () => window.removeEventListener('cmd_trigger_login', handleTriggerLogin);
  }, [getPendingScansCount, openLogin, lang]);

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
    // Compact summary now appears directly below the Scan / Upload page after each scan
    setActiveTab('scan');
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
        onOpenLogin={() => openLogin()}
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
            <div className="space-y-6">
              <ScanUpload
                onScanComplete={handleScanCompleted}
                lang={lang}
                currentUser={currentUser}
                onRequireLogin={(notice) => openLogin(notice)}
                onOfflineQueued={() => getPendingScansCount().then(setPendingSyncCount)}
              />

              {/* Compact summary rendered below the scan workspace after every scan */}
              {currentScan && (
                <ScanSummary
                  scan={currentScan}
                  compact
                  onViewDetailedAnalysis={() => setActiveTab('analysis')}
                  currentUser={currentUser}
                  onRequireLogin={() =>
                    openLogin(
                      lang === 'hi'
                        ? 'रिपोर्ट भेजने के लिए कृपया साइन इन करें।'
                        : 'Please sign in to send a compliance report.'
                    )
                  }
                  lang={lang}
                />
              )}
            </div>
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
                setActiveTab('analysis');
              }}
              lang={lang}
            />
          )}

          {activeTab === 'history' && (
            <ScanHistory
              onSelectScan={(s) => {
                setCurrentScan(s);
                setActiveTab('analysis');
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
        onClose={() => {
          setLoginModalOpen(false);
          setLoginNotice(null);
        }}
        onLoginSuccess={(user) => setCurrentUser(user)}
        notice={loginNotice}
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

export default function AppWithErrorBoundary() {
  return (
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  );
}
