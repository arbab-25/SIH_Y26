import axios from 'axios';

// Resolve API Base URL from environment. Production fallback points at the live
// Render backend so a fresh build without VITE_API_BASE_URL still works.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD
    ? 'https://codemaze-api-m6f0.onrender.com/api/v1'
    : 'http://localhost:8000/api/v1');

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Accept': 'application/json',
  }
});

// Interceptor to inject Bearer Token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cmd_auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Global handler for expired/missing sessions: the app listens for this event
// and shows the sign-in modal (guest mode has been removed — every scan,
// report and history view requires a signed-in inspector account).
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      window.dispatchEvent(new CustomEvent('cmd_trigger_login'));
    }
    return Promise.reject(error);
  }
);
