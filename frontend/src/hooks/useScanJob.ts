import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

export interface ScanJobStatus {
  scan_id: string;
  scan_status: 'queued' | 'processing' | 'done' | 'failed';
  verdict: string | null;
  compliance_score: number | null;
  processing_time_ms: number | null;
  error_message: string | null;
  job: { job_id: string; status: string } | null;
  done: boolean;
}

/**
 * Phase 4: polls GET /scans/{id}/job via TanStack Query with exponential-ish
 * backoff (1.5s -> 2s -> 3s, capped at 3s) so the free-tier OCR wait no
 * longer fires blind 1.5s requests for two minutes. `enabled` gates polling
 * until a scan id exists. The RQ worker status (job.status) surfaces the
 * Phase-2 queue state (queued/started/finished) when Redis is configured.
 */
export function useScanJobStatus(scanId: string | null, enabled = true) {
  const queryClient = useQueryClient();

  const query = useQuery<ScanJobStatus>({
    queryKey: ['scan-job', scanId],
    enabled: Boolean(scanId) && enabled,
    refetchInterval: (query) => {
      const data = query.state.data as ScanJobStatus | undefined;
      if (!data || data.done) return false; // stop polling at terminal state
      const n = query.state.dataUpdateCount;
      if (n < 4) return 1500; // first ~6s: snappy
      if (n < 10) return 2500; // next ~25s
      return 3000; // long free-tier OCR tail
    },
    refetchIntervalInBackground: false,
    retry: 1,
    staleTime: 0,
  });

  // Terminal results stay in the cache for the session so switching tabs
  // doesn't re-poll finished scans.
  useEffect(() => {
    const data = query.data;
    if (data?.done && scanId) {
      queryClient.invalidateQueries({ queryKey: ['scan', scanId] });
    }
  }, [query.data, scanId, queryClient]);

  return query;
}
