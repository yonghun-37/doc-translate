import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';

const job = {
  id: '20261117-090000-abcdef', title: '초안_rev123.XLSX', ext: 'xlsx', status: 'pending',
  files: { revised: '초안_rev123.XLSX' },
  counts: { added: 0, removed: 0, modified: 0 }, created_at: '2026-11-17T09:00:00+09:00',
  decided_at: null, decided_by: null, reason: null, error: null, changes: [], alignment: {},
  plan: { 'zh-CN': { segments: 5, reused: 0, translated: 5 }, 'zh-TW': { segments: 5, reused: 0, translated: 5 } },
  artifacts: {}, outputs: [], stats: {}, uploaded_by: '김등록',
};
const fetchMock = vi.fn<typeof fetch>();
const clients: QueryClient[] = [];
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
}
function mount(path = '/new') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
}
function file(name = '초안_rev123.XLSX') { return new File(['test document'], name); }
async function submit() {
  const button = screen.getByRole('button', { name: '올리기' }) as HTMLButtonElement;
  // jsdom's native required-file check cannot see user-event's mocked FileList.
  button.form!.noValidate = true;
  await userEvent.click(button);
}
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url, init) => json(url === '/api/jobs' && !init?.method ? [] : job));
});
afterEach(() => {
  for (const client of clients.splice(0)) client.clear();
  vi.restoreAllMocks(); vi.unstubAllGlobals();
});

describe('작업 업로드', () => {
  it('목록에서 네 파일 칸이 있는 새 작업으로 이동한다', async () => {
    mount('/');
    await userEvent.click(screen.getByRole('link', { name: '새 작업' }));
    expect(screen.getByRole('heading', { name: '새 작업' })).toBeVisible();
    for (const label of ['원본 (한국어, 선택)', '수정본 (한국어, 필수)', '기존 간체본 (선택)', '기존 번체본 (선택)']) {
      expect(screen.getByLabelText(label)).toHaveAttribute('accept', '.docx,.xlsx,.pptx');
    }
    expect(screen.getByLabelText('수정본 (한국어, 필수)')).toBeRequired();
    expect(screen.getByLabelText('원본 (한국어, 선택)')).not.toBeRequired();
    expect(screen.getByRole('button', { name: '올리기' })).toBeDisabled();
  });

  it('수정본 파일명으로 제목을 채우고 네 파일·이름을 전송해 상세로 이동한다', async () => {
    localStorage.setItem('doc-translate.reviewer', '김등록');
    mount();
    const source = file();
    await userEvent.upload(screen.getByLabelText('수정본 (한국어, 필수)'), source);
    expect(screen.getByLabelText('제목 (선택)')).toHaveValue('초안_rev123.XLSX');
    expect(screen.getByText('초안_rev123.XLSX')).toBeVisible();
    const original = file('원본.xlsx'), cn = file('중국.xlsx'), tw = file('대만.xlsx');
    await userEvent.upload(screen.getByLabelText('원본 (한국어, 선택)'), original);
    await userEvent.upload(screen.getByLabelText('기존 간체본 (선택)'), cn);
    await userEvent.upload(screen.getByLabelText('기존 번체본 (선택)'), tw);
    expect(screen.getByLabelText('올린 사람 이름 (선택)')).toHaveValue('김등록');
    await submit();
    expect(await screen.findByRole('button', { name: '번역 실행' })).toBeVisible();
    const request = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')?.[1];
    const form = request?.body as FormData;
    expect(form.get('revised')).toBe(source); expect(form.get('original')).toBe(original);
    expect(form.get('base_zh_cn')).toBe(cn); expect(form.get('base_zh_tw')).toBe(tw);
    expect(form.get('title')).toBe('초안_rev123.XLSX'); expect(form.get('by')).toBe('김등록');
    expect(request?.headers).toBeUndefined();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  });

  it('필수 수정본과 형식 일치를 검사한다', async () => {
    mount();
    await userEvent.upload(screen.getByLabelText('기존 간체본 (선택)'), file('base.docx'));
    expect(screen.getByRole('button', { name: '올리기' })).toBeDisabled();
    await userEvent.upload(screen.getByLabelText('수정본 (한국어, 필수)'), file());
    expect(screen.getByRole('alert')).toHaveTextContent('수정본과 확장자가 다릅니다.');
    expect(screen.getByLabelText('기존 간체본 (선택)')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('button', { name: '올리기' })).toBeDisabled();
    await userEvent.upload(screen.getByLabelText('기존 간체본 (선택)'), file('base.xlsx'));
    expect(screen.getByRole('button', { name: '올리기' })).toBeEnabled();
  });

  it('서버 오류를 표시하고 파일·입력값을 유지한다', async () => {
    fetchMock.mockResolvedValue(json({ detail: '원본과 수정본이 동일합니다.' }, 400));
    mount();
    await userEvent.upload(screen.getByLabelText('수정본 (한국어, 필수)'), file());
    await userEvent.type(screen.getByLabelText('올린 사람 이름 (선택)'), '이등록');
    await submit();
    expect(await screen.findByRole('alert')).toHaveTextContent('원본과 수정본이 동일합니다.');
    expect(screen.getByLabelText('제목 (선택)')).toHaveValue('초안_rev123.XLSX');
    expect((screen.getByLabelText('수정본 (한국어, 필수)') as HTMLInputElement).files).toHaveLength(1);
    expect(localStorage.getItem('doc-translate.reviewer')).toBe('이등록');
    expect(screen.getByRole('button', { name: '올리기' })).toBeEnabled();
  });

  it('전송 중 전체 폼과 중복 제출을 잠그고 진행 상태를 표시한다', async () => {
    let finish!: (response: Response) => void;
    fetchMock.mockImplementation(async (_url, init) => init?.method === 'POST' ? new Promise(resolve => { finish = resolve; }) : json(job));
    mount();
    await userEvent.upload(screen.getByLabelText('수정본 (한국어, 필수)'), file());
    await submit();
    expect(await screen.findByRole('button', { name: '올리는 중…' })).toBeDisabled();
    expect(screen.getByLabelText('수정본 (한국어, 필수)')).toBeDisabled();
    expect(screen.getByLabelText('원본 (한국어, 선택)')).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('매칭을 준비');
    finish(json(job, 201));
    expect(await screen.findByRole('button', { name: '번역 실행' })).toBeVisible();
  });

  it('수정본만으로 신규 전체 번역을 등록하고 사용자 제목을 보낸다', async () => {
    mount();
    await userEvent.upload(screen.getByLabelText('수정본 (한국어, 필수)'), file());
    await userEvent.clear(screen.getByLabelText('제목 (선택)'));
    await userEvent.type(screen.getByLabelText('제목 (선택)'), ' 새 제목 ');
    await submit();
    await waitFor(() => expect(screen.getByText('신규 문서 — 전체 번역')).toBeVisible());
    const form = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')?.[1]?.body as FormData;
    expect(form.get('title')).toBe('새 제목');
    expect(form.has('original')).toBe(false); expect(form.has('base_zh_tw')).toBe(false);
  });
});
