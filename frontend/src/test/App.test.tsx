import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';

const changes = [
  { op: 'added', where: '문단 1', old: null, new: '추가 문장' },
  { op: 'removed', where: '문단 2', old: '삭제 문장', new: null },
  { op: 'modified', where: '문단 3', old: '기존 내용', new: '변경 내용' },
];
const detail = {
  id: '20261117-090000-abcdef', title: '운영 지침', ext: 'docx', status: 'pending',
  files: { original: '원본.docx', revised: '수정본.docx' }, uploaded_by: '김등록',
  alignment: { 'zh-CN': { lang: 'zh-CN', total: 10, matched: 8, unmatched_samples: [{ where: '본문 문단 5', text: '매칭 누락 문장' }] } },
  plan: { 'zh-CN': { segments: 10, reused: 4, translated: 6 }, 'zh-TW': { segments: 10, reused: 0, translated: 10 } },
  counts: { added: 1, removed: 1, modified: 1 }, created_at: '2026-11-17T09:00:00+09:00',
  decided_at: null, decided_by: null, reason: null, error: null, changes,
  artifacts: { redline: '/api/jobs/20261117-090000-abcdef/files/redline.docx' }, outputs: [], stats: {},
};
const fetchMock = vi.fn<typeof fetch>();
const clients: QueryClient[] = [];
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
}
function mount(path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
}
const reviewPath = '/jobs/20261117-090000-abcdef';
beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  localStorage.clear();
  fetchMock.mockReset();
  fetchMock.mockImplementation(async () => json(detail));
});
afterEach(() => {
  for (const client of clients.splice(0)) client.clear();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('검토 목록', () => {
  it('최신순 정렬, 상태 필터, 검색과 상세 이동을 지원한다', async () => {
    fetchMock.mockResolvedValue(json([
      { ...detail, id: '20261118-090000-abcdef', title: '완료 문서', status: 'translated', created_at: '2026-11-18T09:00:00+09:00' },
      detail,
      { ...detail, id: '20261116-090000-abcdef', title: '인사 규정', created_at: '2026-11-16T09:00:00+09:00' },
    ]));
    mount();
    await screen.findByRole('link', { name: '운영 지침' });
    const rows = screen.getAllByRole('row');
    expect(within(rows[1]).getByRole('link', { name: '완료 문서' })).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText('상태'), 'translated');
    expect(screen.queryByRole('link', { name: '운영 지침' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '완료 문서' })).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText('상태'), 'all');
    await userEvent.type(screen.getByRole('searchbox', { name: '제목 검색' }), '운영');
    expect(screen.queryByRole('link', { name: '인사 규정' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '운영 지침' })).toHaveAttribute('href', '/jobs/20261117-090000-abcdef');
  });

  it('API 오류 메시지를 상단 배너로 보여 준다', async () => {
    fetchMock.mockResolvedValue(json({ detail: '검토 목록을 읽을 수 없습니다.' }, 500));
    mount();
    expect(await screen.findByRole('alert')).toHaveTextContent('검토 목록을 읽을 수 없습니다.');
  });

  it('10초마다 목록에 도착한 새 검토를 표시한다', async () => {
    vi.useFakeTimers();
    let requests = 0;
    fetchMock.mockImplementation(async () => json(++requests === 1 ? [] : [detail]));
    mount();
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(screen.getByText('등록된 작업이 없습니다.')).toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(10100); });
    expect(screen.getByRole('link', { name: '운영 지침' })).toBeVisible();
  });
});

describe('검토 상세', () => {
  it('변경 종류 필터와 글자별 차이, Word 내려받기를 제공한다', async () => {
    mount(reviewPath);
    const download = await screen.findByRole('link', { name: 'Word 변경 추적 내려받기' });
    expect(download).toHaveAttribute('href', '/api/jobs/20261117-090000-abcdef/files/redline.docx');
    expect(screen.getByText('기존').closest('del')).toBeInTheDocument();
    expect(screen.getByText('변경').closest('ins')).toBeInTheDocument();
    expect(screen.getByText('내용')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '추가 1' }));
    expect(screen.getByText('추가 문장')).toBeVisible();
    expect(screen.queryByText('삭제 문장')).not.toBeInTheDocument();
  });

  it('빈 반려 사유를 막고 사유와 결정자를 전송한다', async () => {
    fetchMock.mockImplementation(async (_url, init) => json(init?.method === 'POST' ? { ...detail, status: 'rejected', reason: '내용 확인 필요', decided_by: '김검토' } : detail));
    mount(reviewPath);
    const reject = await screen.findByRole('button', { name: '반려' });
    expect(reject).toBeDisabled();
    await userEvent.type(screen.getByLabelText('검토자 이름 (선택)'), '김검토');
    await userEvent.type(screen.getByLabelText('반려 사유'), '   ');
    expect(reject).toBeDisabled();
    await userEvent.type(screen.getByLabelText('반려 사유'), '내용 확인 필요');
    await userEvent.click(reject);
    await waitFor(() => expect(screen.queryByRole('button', { name: '반려' })).not.toBeInTheDocument());
    const posted = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(posted?.[0]).toBe('/api/jobs/20261117-090000-abcdef/reject');
    expect(JSON.parse(String(posted?.[1]?.body))).toEqual({ by: '김검토', reason: '내용 확인 필요' });
    expect(localStorage.getItem('doc-translate.reviewer')).toBe('김검토');
  });

  it('번역 확인 후에만 POST하고 409 안내 후 변경 데이터를 다시 읽는다', async () => {
    let changed = false;
    fetchMock.mockImplementation(async (_url, init) => {
      if (init?.method === 'POST') {
        changed = true;
        return json({ detail: '이미 다른 요청이 처리한 작업입니다.',  }, 409);
      }
      return json(changed ? { ...detail, changes: [] } : detail);
    });
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    mount(reviewPath);
    const approve = await screen.findByRole('button', { name: '번역 실행' });
    await userEvent.click(approve);
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
    await userEvent.click(approve);
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 다른 요청이 처리한 작업입니다.');
    expect(await screen.findByText('변경된 내용이 없습니다.')).toBeVisible();
    expect(confirm).toHaveBeenCalledTimes(2);
    confirm.mockRestore();
  });

  it('기억한 검토자 이름으로 번역하고 대기 패널을 닫는다', async () => {
    localStorage.setItem('doc-translate.reviewer', '이승인');
    fetchMock.mockImplementation(async (_url, init) => json(init?.method === 'POST' ? { ...detail, status: 'translating', decided_by: '이승인' } : detail));
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    mount(reviewPath);
    expect(await screen.findByLabelText('검토자 이름 (선택)')).toHaveValue('이승인');
    await userEvent.click(screen.getByRole('button', { name: '번역 실행' }));
    expect(await screen.findByText('번역 중')).toBeVisible();
    expect(screen.queryByRole('button', { name: '번역 실행' })).not.toBeInTheDocument();
    const posted = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(posted?.[0]).toMatch(/\/translate$/);
    expect(JSON.parse(String(posted?.[1]?.body))).toEqual({ by: '이승인' });
    confirm.mockRestore();
  });

  it('xlsx 시트 전환과 행 종류를 표시하고 문자열을 HTML로 해석하지 않는다', async () => {
    fetchMock.mockImplementation(async (url) => json(String(url).endsWith('/sheets') ? [
      { sheet: '매출', status: 'changed', header: ['항목', '값'], rows: [
        { marker: '+++', cells: ['신규', '<img src=x onerror=alert(1)>'] },
        { marker: '---', cells: ['이전', '15'] },
        { marker: '->', cells: ['가격', '10->20'] },
      ] },
      { sheet: '재고', status: 'same', header: ['상품'], rows: [{ marker: '', cells: ['부품'] }] },
    ] : { ...detail, ext: 'xlsx' }));
    mount(reviewPath);
    expect((await screen.findByText('신규')).closest('tr')).toHaveClass('diff-row-added');
    expect(screen.getByRole('cell', { name: '이전' }).closest('tr')).toHaveClass('diff-row-removed');
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
    expect(screen.getByText('10').closest('del')).toBeInTheDocument();
    expect(screen.getByText('20').closest('ins')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: '재고' }));
    expect(screen.getByText('부품')).toBeVisible();
    expect(screen.queryByText('신규')).not.toBeInTheDocument();
  });

  it('pptx 변경을 슬라이드별로 묶고 노트를 구분한다', async () => {
    fetchMock.mockImplementation(async (url) => json(String(url).endsWith('/slides') ? [
      { slide: 2, items: [{ shape: '제목', notes: false, op: 'added', old: null, new: '제품 소개' }] },
      { slide: 5, items: [{ shape: '발표자', notes: true, op: 'removed', old: '발표 메모', new: null }] },
    ] : { ...detail, ext: 'pptx' }));
    mount(reviewPath);
    expect(await screen.findByRole('heading', { name: '슬라이드 2' })).toBeVisible();
    expect(screen.getByRole('heading', { name: '슬라이드 5' })).toBeVisible();
    expect(screen.getByText('노트: 발표자')).toBeVisible();
  });

  it.each(['-->', '--->'])('daff 구분자 %s로 셀의 원래 화살표를 보존한다', async (marker) => {
    fetchMock.mockImplementation(async (url) => json(String(url).endsWith('/sheets') ? [
      { sheet: '경로', status: 'changed', header: ['값'], rows: [{ marker, cells: [`a->b${marker}a->c`] }] },
    ] : { ...detail, ext: 'xlsx' }));
    mount(reviewPath);
    const panel = await screen.findByRole('tabpanel');
    expect(within(panel).getByText('a->b').closest('del')).toBeInTheDocument();
    expect(within(panel).getByText('a->c').closest('ins')).toBeInTheDocument();
    expect(within(panel).getByRole('rowheader', { name: '수정' })).toBeVisible();
  });

  it('번역 상태를 2초마다 조회해 완료 파일과 통계를 표시한다', async () => {
    vi.useFakeTimers();
    let gets = 0;
    fetchMock.mockImplementation(async () => json(++gets === 1 ? { ...detail, status: 'translating' } : {
      ...detail, status: 'translated', outputs: [{ lang: 'zh-CN', url: '/api/files/output/cn.docx' }, { lang: 'zh-TW', url: '/api/files/output/tw.docx' }],
      stats: { 'zh-CN': { segments: 10, reused: 7, translated: 3 }, 'zh-TW': { segments: 10, reused: 0, translated: 10 } },
    }));
    mount(reviewPath);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText('번역 중')).toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(screen.getByRole('link', { name: /zh-CN/ })).toHaveAttribute('href', '/api/files/output/cn.docx');
    expect(screen.getByRole('link', { name: /zh-TW/ })).toHaveAttribute('href', '/api/files/output/tw.docx');
    expect(screen.getAllByText('전체 세그먼트')[0].nextElementSibling).toHaveTextContent('10');
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(gets).toBe(2);
  });

  it('실패 오류와 재시도를 제공한다', async () => {
    fetchMock.mockImplementation(async (_url, init) => json(init?.method === 'POST' ? { ...detail, status: 'translating' } : { ...detail, status: 'failed', error: '번역 서버 연결 실패' }));
    mount(reviewPath);
    expect(await screen.findByRole('alert')).toHaveTextContent('번역 서버 연결 실패');
    await userEvent.click(screen.getByRole('button', { name: '재시도' }));
    expect(await screen.findByText('번역 중')).toBeVisible();
    expect(fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')?.[0]).toMatch(/\/retry$/);
  });

  it('매칭 계획, 낮은 매칭률 경고와 미매칭 문장을 보여 준다', async () => {
    fetchMock.mockResolvedValue(json({ ...detail, alignment: { 'zh-CN': { ...detail.alignment['zh-CN'], matched: 4 } } }));
    mount(reviewPath);
    expect(await screen.findByRole('heading', { name: '번역 계획' })).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('50% 미만');
    expect(screen.getByText('기존 중국어본 없음 — 전체 번역')).toBeVisible();
    const plan = screen.getByRole('region', { name: '간체 번역 계획' });
    expect(plan).toHaveTextContent('기존 번역 재사용 예정 4개 / 새로 번역 6개');
    await userEvent.click(screen.getByText('매칭 안 된 원본 문장 (1개 표시)'));
    expect(screen.getByText('매칭 누락 문장')).toBeVisible();
  });

  it('확인 후 삭제하고 작업 목록으로 이동한다', async () => {
    fetchMock.mockImplementation(async (url, init) => init?.method === 'DELETE' ? new Response(null, { status: 204 }) : json(url === '/api/jobs' ? [] : detail));
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    mount(reviewPath);
    const button = await screen.findByRole('button', { name: '작업 삭제' });
    await userEvent.click(button);
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false);
    await userEvent.click(button);
    expect(await screen.findByRole('heading', { name: '작업 목록' })).toBeVisible();
    expect(fetchMock.mock.calls.find(([, init]) => init?.method === 'DELETE')?.[0]).toBe('/api/jobs/20261117-090000-abcdef');
    confirm.mockRestore();
  });

  it('번역 중에는 삭제할 수 없다', async () => {
    fetchMock.mockResolvedValue(json({ ...detail, status: 'translating' }));
    mount(reviewPath);
    expect(await screen.findByRole('button', { name: '작업 삭제' })).toBeDisabled();
  });

  it('신규 문서는 전체 번역 안내를 표시하고 형식별 비교를 요청하지 않는다', async () => {
    fetchMock.mockResolvedValue(json({ ...detail, files: { revised: '신규.xlsx' }, ext: 'xlsx', changes: [], alignment: {}, artifacts: {} }));
    mount(reviewPath);
    expect(await screen.findByText('신규 문서 — 전체 번역')).toBeVisible();
    expect(screen.queryByRole('heading', { name: '변경 내용' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/sheets'))).toBe(false);
    expect(screen.getByRole('button', { name: '번역 실행' })).toBeEnabled();
  });
});
