import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { translations } from './translations';

// react-i18next (Phase 4) wraps the existing translation dictionaries:
// all keys from src/i18n/translations.ts become t('key') resources, so the
// existing bilingual strings are reused verbatim — no duplicated content.
const en = Object.fromEntries(
  Object.entries(translations.en).filter(([, v]) => typeof v === 'string')
);
const hi = Object.fromEntries(
  Object.entries(translations.hi).filter(([, v]) => typeof v === 'string')
);

const storedLang = (localStorage.getItem('cmd_lang') as 'en' | 'hi') || 'en';

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
  },
  lng: storedLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false }, // React escapes already
  returnNull: false,
});

export default i18n;
