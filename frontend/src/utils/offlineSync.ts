import { getAllPendingScans, removePendingScan } from './offlineQueue';
import { api } from './api';

/**
 * Phase 4: drains the IndexedDB offline queue when connectivity returns.
 * Called by the QueryProvider component on the `online` window event.
 * Each queued scan is uploaded once; successes are removed, failures stay
 * queued for the next sync (never silently dropped).
 */
export async function syncPendingScans(): Promise<{ synced: number; remaining: number }> {
  const pending = await getAllPendingScans();
  let synced = 0;

  for (const scan of pending) {
    try {
      const formData = new FormData();
      scan.files.forEach((file) => formData.append('images', file));
      formData.append('category', scan.category);
      formData.append('package_type', scan.packageType);

      const res = await api.post('/scans', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.status === 202 || res.status === 200) {
        await removePendingScan(scan.id);
        synced += 1;
      }
    } catch (err: any) {
      // 401 => session expired; keep queued, the user re-authenticates and
      // the next sync retries. Network errors likewise stay queued.
      console.warn('Offline scan sync deferred:', scan.id, err?.response?.status || err);
    }
  }

  const remaining = pending.length - synced;
  return { synced, remaining };
}
