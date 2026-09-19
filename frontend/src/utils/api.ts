import axios from 'axios';

// Resolve API Base URL from environment. Production fallback points at the live
// Render backend so a fresh build without VITE_API_BASE_URL still works.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD
    ? 'https://codemaze-api-m6f0.onrender.com/api/v1'
    : 'http://localhost:8000/api/v1');

// Generate or retrieve persistent anonymous device ID for guest scan tracking per §6
export const getDeviceId = (): string => {
  let devId = localStorage.getItem('cmd_device_id');
  if (!devId) {
    devId = 'cmd-' + Math.random().toString(36).substring(2, 11) + '-' + Date.now();
    localStorage.setItem('cmd_device_id', devId);
  }
  return devId;
};

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Accept': 'application/json',
  }
});

// Interceptor to inject Bearer Token and Guest Device ID
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cmd_auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  config.headers['X-Guest-Device-Id'] = getDeviceId();
  return config;
});

// Interceptor to capture guest free scan limits (403)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 403) {
      // Trigger login prompt event for guest users
      window.dispatchEvent(new CustomEvent('cmd_trigger_login'));
    }
    return Promise.reject(error);
  }
);
