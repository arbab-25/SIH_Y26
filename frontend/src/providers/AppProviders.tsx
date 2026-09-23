import React, { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '../i18n';
import { useTranslation } from 'react-i18next';
import { syncPendingScans } from '../utils/offlineSync';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * Registers the PWA service worker and drains the IndexedDB offline scan
 * queue when connectivity returns (Phase 4). Mounted once, above App.
 */
export const AppProviders: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { i18n } = useTranslation();

  // Keep i18next language in sync with the existing cmd_lang localStorage key
  // that App.tsx manages (single source of truth preserved).
  useEffect(() => {
    const apply = () => {
      const stored = localStorage.getItem('cmd_lang');
      if (stored && stored !== i18n.language) {
        void i18n.changeLanguage(stored);
      }
    };
    apply();
    window.addEventListener('storage', apply);
    return () => window.removeEventListener('storage', apply);
  }, [i18n]);

  // PWA service worker registration (vite-plugin-pwa injects the SW assets).
  useEffect(() => {
    if ('serviceWorker' in navigator && import.meta.env.PROD) {
      import('virtual:pwa-register').then(({ registerSW }) => {
        registerSW({ immediate: true });
      });
    }
  }, []);

  // Offline queue drain on reconnect.
  useEffect(() => {
    const onOnline = () => {
      void syncPendingScans();
    };
    window.addEventListener('online', onOnline);
    return () => window.removeEventListener('online', onOnline);
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
