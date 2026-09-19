import { openDB } from 'idb';

const DB_NAME = 'codemaze_offline_db';
const STORE_NAME = 'pending_scans';

export interface PendingScan {
  id: string;
  files: File[];
  category: string;
  packageType: string;
  timestamp: number;
}

export const getDb = async () => {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
    },
  });
};

export const queueOfflineScan = async (scan: PendingScan): Promise<void> => {
  const db = await getDb();
  await db.put(STORE_NAME, scan);
};

export const getPendingScansCount = async (): Promise<number> => {
  try {
    const db = await getDb();
    return await db.count(STORE_NAME);
  } catch {
    return 0;
  }
};

export const getAllPendingScans = async (): Promise<PendingScan[]> => {
  const db = await getDb();
  return await db.getAll(STORE_NAME);
};

export const removePendingScan = async (id: string): Promise<void> => {
  const db = await getDb();
  await db.delete(STORE_NAME, id);
};
