export type Status = 'pending' | 'translating' | 'translated' | 'rejected' | 'failed';
export type Language = 'zh-CN' | 'zh-TW';
export const languages: Language[] = ['zh-CN', 'zh-TW'];
export const languageLabels: Record<Language, string> = { 'zh-CN': '간체', 'zh-TW': '번체' };
export interface AlignmentCounts { total: number; matched: number }
export interface Alignment extends AlignmentCounts {
  lang: Language;
  unmatched_samples: { where: string; text: string }[];
}
export interface Stats { segments: number; reused: number; translated: number }
export interface JobSummary {
  id: string;
  title: string;
  ext: 'docx' | 'xlsx' | 'pptx';
  status: Status;
  counts: { added: number; removed: number; modified: number };
  created_at: string;
  uploaded_by: string | null;
  alignment: Partial<Record<Language, AlignmentCounts>>;
}
export interface Change {
  op: 'added' | 'removed' | 'modified';
  where: string;
  old: string | null;
  new: string | null;
  page?: number;
  slide?: number;
  sheet?: string;
  cell?: string;
  source?: 'original' | 'revised';
}
export interface JobDetail extends JobSummary {
  files: { revised: string; original?: string; 'base_zh-CN'?: string; 'base_zh-TW'?: string };
  decided_at: string | null;
  decided_by: string | null;
  reason: string | null;
  error: string | null;
  changes: Change[];
  alignment: Partial<Record<Language, Alignment>>;
  plan: Record<Language, Stats>;
  artifacts: { redline?: string };
  outputs: { lang: Language; url: string }[];
  stats: Partial<Record<Language, Stats>>;
  preview?: Preview;
  progress?: Progress;
}
export interface PreviewPage { page: number; name: string; width: number; height: number; side: string }
export interface Preview { status: 'pending' | 'ready' | 'unavailable' | 'failed'; message: string; pages: PreviewPage[] }
export type Phase = 'extract' | 'reuse' | 'llm' | 'write' | 'done';
export interface Progress {
  phase: Phase;
  langs: Record<Language, { phase: Phase; total: number; reused: number; translated: number; done: number }>;
  started_at: string; updated_at: string; eta_sec: number | null;
  log: { at: string; message: string }[];
}
export interface GridCell { addr: string; value: string; bold?: boolean; italic?: boolean; fill?: string; color?: string; align?: 'left' | 'center' | 'right'; span?: { rows: number; cols: number }; change_addrs?: string[] }
export interface GridSheet {
  name: string; status: SheetDiff['status']; message: string;
  cols: { letter: string; width: number }[];
  rows: { index: number; height: number; cells: GridCell[]; added?: boolean }[];
  merges: string[];
  changes: Record<string, Pick<Change, 'op' | 'old' | 'new'>>;
  removed_rows: { index: number; after: number; cells: GridCell[] }[];
}
export interface Overlay { slide: number; shape: string; side: 'original' | 'revised'; op: Change['op']; x: number; y: number; width: number; height: number }
export const previewUrl = (id: string, name: string) => `${jobUrl(id)}/files/preview/${encodeURIComponent(name)}`;
export interface SheetDiff {
  sheet: string;
  status: 'added' | 'removed' | 'changed' | 'same';
  header: string[];
  rows: { marker: string; cells: string[] }[];
}
export interface SlideDiff {
  slide: number;
  items: { shape: string; notes: boolean; op: Change['op']; old: string | null; new: string | null }[];
}

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(url, options); }
  catch { throw new Error('서버에 연결할 수 없습니다. 연결 상태를 확인한 뒤 다시 시도하세요.'); }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const error = body as { detail?: unknown } | null;
    throw new ApiError(typeof error?.detail === 'string' ? error.detail : `요청을 처리하지 못했습니다. (${response.status})`, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const jobUrl = (id: string) => `/api/jobs/${encodeURIComponent(id)}`;
export const api = {
  upload: (body: FormData) => request<JobDetail>('/api/jobs', { method: 'POST', body }),
  jobs: () => request<JobSummary[]>('/api/jobs'),
  job: (id: string) => request<JobDetail>(jobUrl(id)),
  sheets: (id: string) => request<SheetDiff[]>(`${jobUrl(id)}/sheets`),
  slides: (id: string) => request<SlideDiff[]>(`${jobUrl(id)}/slides`),
  grid: (id: string, target?: Change) => {
    const params = new URLSearchParams();
    if (target?.sheet) params.set('sheet', target.sheet);
    const match = target?.cell?.match(/^([A-Z]+)(\d+)$/);
    if (match) {
      params.set('row', match[2]);
      params.set('col', String([...match[1]].reduce((sum, c) => sum * 26 + c.charCodeAt(0) - 64, 0)));
    }
    return request<GridSheet[]>(`${jobUrl(id)}/grid?${params}`);
  },
  overlays: (id: string) => request<Overlay[]>(previewUrl(id, 'overlays.json')),
  delete: (id: string) => request<void>(jobUrl(id), { method: 'DELETE' }),
  decide: (id: string, action: 'translate' | 'reject' | 'retry', body?: { by?: string; reason?: string }) =>
    request<JobDetail>(`${jobUrl(id)}/${action}`, {
      method: 'POST', headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    }),
};
