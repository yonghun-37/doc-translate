import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import SheetView from '../components/SheetView';
import PageView from '../components/PageView';
import SlideCompare from '../components/SlideCompare';
import TranslationProgress from '../components/TranslationProgress';
import { type Change, type GridSheet, type JobDetail, type Progress } from '../api';

const changes: Change[] = [
  { op: 'modified', where: "'단가' 시트 · B3", sheet: '단가', cell: 'B3', old: '20', new: '21' },
  { op: 'added', where: "'재고' 시트 · A1", sheet: '재고', cell: 'A1', old: '', new: '부품' },
];
const sheets: GridSheet[] = [
  { name: '단가', status: 'changed', message: '', cols: [{ letter: 'A', width: 100 }, { letter: 'B', width: 100 }], rows: [{ index: 3, height: 20, added: true, cells: [{ addr: 'A3', value: '<img src=x onerror=bad>' }, { addr: 'B3', value: '21' }] }], merges: [], changes: { B3: changes[0] }, removed_rows: [{ index: 2, after: 3, cells: [{ addr: 'A2', value: '삭제한 원본' }] }] },
  { name: '재고', status: 'added', message: '', cols: [{ letter: 'A', width: 100 }], rows: [{ index: 1, height: 20, cells: [{ addr: 'A1', value: '부품' }] }], merges: [], changes: { A1: changes[1] }, removed_rows: [] },
];
const job: JobDetail = {
  id: '20261118-000000-abcdef', title: '레이아웃 검토', ext: 'docx', status: 'pending', counts: { added: 0, modified: 1, removed: 0 }, created_at: '2026-11-18T00:00:00Z', uploaded_by: null,
  files: { original: 'old.docx', revised: 'new.docx' }, decided_at: null, decided_by: null, reason: null, error: null, changes: [{ op: 'modified', where: '2페이지 · 1번째 문단', page: 2, old: 'before', new: 'after' }], alignment: {}, plan: { 'zh-CN': { segments: 10, reused: 0, translated: 10 }, 'zh-TW': { segments: 10, reused: 0, translated: 10 } }, artifacts: {}, outputs: [], stats: {},
  preview: { status: 'ready', message: '', pages: [{ page: 1, name: 'redline-001.png', width: 100, height: 150, side: 'redline' }, { page: 2, name: 'redline-002.png', width: 100, height: 150, side: 'redline' }] },
};
const clients: QueryClient[] = [];
const fetchMock = vi.fn<typeof fetch>();
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/jobs/${job.id}`]}><App /></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { vi.stubGlobal('fetch', fetchMock); fetchMock.mockReset(); fetchMock.mockImplementation(async () => json(job)); });
afterEach(() => { for (const client of clients.splice(0)) client.clear(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it('격자의 변경 강조·툴팁·삭제 펼치기·시트 전환·다음 위치 이동', async () => {
  const onLocate = vi.fn();
  const { rerender } = render(<SheetView sheets={sheets} changes={changes} onLocate={onLocate} />);
  const changed = screen.getByRole('cell', { name: 'B3: 20 → 21' });
  expect(changed).toHaveClass('grid-cell-modified'); expect(changed).toHaveAttribute('title', 'B3: 20 → 21');
  expect(changed.closest('tr')).toHaveClass('diff-row-added');
  expect(screen.getByText('<img src=x onerror=bad>')).toBeVisible(); expect(document.querySelector('img')).toBeNull();
  await userEvent.click(screen.getByRole('button', { name: '원본 2행 삭제 펼치기' })); expect(screen.getByText('삭제한 원본')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '다음 변경' })); expect(onLocate).toHaveBeenLastCalledWith(changes[0]);
  rerender(<SheetView sheets={sheets} changes={changes} target={changes[0]} onLocate={onLocate} />);
  expect(changed).toHaveFocus();
  await userEvent.click(screen.getByRole('button', { name: '다음 변경' })); expect(onLocate).toHaveBeenLastCalledWith(changes[1]);
  await userEvent.click(screen.getByRole('tab', { name: /재고/ }));
  const tabChange = onLocate.mock.calls.at(-1)![0];
  rerender(<SheetView sheets={sheets} changes={changes} target={tabChange} onLocate={onLocate} />);
  expect(screen.getByText('부품')).toBeVisible(); expect(screen.getByRole('tab', { name: /재고/ })).toHaveAttribute('aria-selected', 'true');
  await userEvent.click(screen.getByRole('button', { name: '이전 변경' })); expect(onLocate).toHaveBeenLastCalledWith(changes[0]);
});

it('Word 페이지 썸네일·변경 수·지연 로딩', () => {
  render(<PageView id={job.id} preview={job.preview!} changes={job.changes} target={job.changes[0]} />);
  expect(screen.getByRole('heading', { name: '2페이지 — 변경 1건' })).toBeVisible();
  expect(screen.getByRole('link', { name: '2페이지, 변경 1건' })).toHaveAttribute('href', '#page-2');
  expect(screen.getByRole('img', { name: 'Word 변경 추적 2페이지' })).toHaveAttribute('loading', 'lazy');
  expect(document.getElementById('page-2')).toHaveFocus();
});

it('PPT 원본 삭제 테두리·수정본 추가 테두리·노트·변경 필터', async () => {
  const pages = [1, 2].flatMap(page => ['original', 'revised'].map(side => ({ page, name: `${side}-00${page}.png`, width: 1600, height: 900, side })));
  render(<SlideCompare id={job.id} preview={{ status: 'ready', message: '', pages }} slides={[{ slide: 1, items: [{ shape: '노트', notes: true, op: 'modified', old: 'old', new: 'new' }] }]} overlays={[
    { slide: 1, side: 'original', shape: '삭제 도형', op: 'removed', x: .1, y: .2, width: .3, height: .4 },
    { slide: 1, side: 'revised', shape: '추가 도형', op: 'added', x: .2, y: .2, width: .3, height: .4 },
  ]} />);
  expect(document.querySelector('.overlay-removed')).toHaveAttribute('x', '10');
  expect(document.querySelector('.overlay-added')).toHaveAttribute('width', '30');
  expect(screen.getByText('발표자 노트')).toBeVisible();
  await userEvent.click(screen.getByRole('checkbox', { name: '바뀐 슬라이드만 보기' }));
  expect(screen.queryByRole('heading', { name: '슬라이드 2' })).not.toBeInTheDocument();
});

it('변경 목록의 위치를 누르면 원래 모양의 해당 페이지로 이동', async () => {
  mount(); await screen.findByRole('tab', { name: '원래 모양' });
  expect(screen.getByRole('tab', { name: '원래 모양' })).toHaveAttribute('aria-selected', 'true');
  await userEvent.click(screen.getByRole('tab', { name: '변경 목록' }));
  await userEvent.click(screen.getByRole('button', { name: '2페이지 · 1번째 문단' }));
  expect(screen.getByRole('tab', { name: '원래 모양' })).toHaveAttribute('aria-selected', 'true');
  expect(document.getElementById('page-2')).toHaveFocus();
});

it('미리보기 준비는 3초 폴링 후 완료되면 중지', async () => {
  vi.useFakeTimers(); let requests = 0;
  fetchMock.mockImplementation(async () => json(++requests === 1 ? { ...job, preview: { status: 'pending', message: '', pages: [] } } : job));
  mount(); await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(screen.getByRole('status')).toHaveTextContent('미리보기 만드는 중');
  await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
  expect(screen.getByRole('heading', { name: '2페이지 — 변경 1건' })).toBeVisible();
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); }); expect(requests).toBe(2);
});

it.each(['unavailable', 'failed'])('미리보기 %s는 안내 후 변경 목록과 번역 실행 유지', async status => {
  fetchMock.mockImplementation(async () => json({ ...job, preview: { status, message: '서버에 LibreOffice가 없어 원래 모양 보기를 할 수 없습니다', pages: [] } }));
  mount(); await screen.findByRole('tab', { name: '변경 목록' });
  expect(screen.getByRole('tab', { name: '변경 목록' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByText('서버에 LibreOffice가 없어 원래 모양 보기를 할 수 없습니다')).toBeVisible();
  expect(screen.getByRole('button', { name: '번역 실행' })).toBeEnabled();
});

it('번역 진행 단계·언어별 막대·계산 중/ETA·실패 마지막 기록', () => {
  const progress: Progress = { phase: 'llm', langs: { 'zh-CN': { phase: 'llm', total: 49, reused: 9, translated: 20, done: 29 }, 'zh-TW': { phase: 'extract', total: 40, reused: 0, translated: 0, done: 0 } }, started_at: '2026-11-18T00:00:00Z', updated_at: '2026-11-18T00:01:00Z', eta_sec: null, log: [{ at: '2026-11-18T00:01:00Z', message: '간체 LLM 묶음 1/2 완료 (20문장, 2.0초)' }] };
  const { rerender } = render(<TranslationProgress progress={progress} running={false} />);
  expect(screen.getByRole('progressbar', { name: /간체/ })).toHaveAttribute('value', '29');
  expect(screen.getByRole('status')).toHaveTextContent('번역 중단 · 경과 1분 0초 · 남은 예상 계산 중');
  expect(screen.getByText(/간체 LLM 묶음 1\/2 완료/)).toBeVisible();
  rerender(<TranslationProgress progress={{ ...progress, eta_sec: 10 }} running={false} />);
  expect(screen.getByRole('status')).toHaveTextContent('남은 예상 0분 10초');
  expect(within(screen.getByRole('region', { name: '번역 진행 상황' })).getAllByRole('progressbar')).toHaveLength(2);
});

it('삭제 행의 두 번째 셀과 병합 셀 안의 변경에도 위치를 맞춘다', async () => {
  const sheet: GridSheet = { ...sheets[0], removed_rows: [{ index: 2, after: 3, cells: [{ addr: 'A2', value: '원본' }, { addr: 'B2', value: '삭제 값' }] }], rows: [{ index: 3, height: 20, cells: [{ addr: 'A3', value: '병합 값', span: { rows: 1, cols: 2 }, change_addrs: ['B3'] }] }] };
  const deleted: Change = { op: 'removed', where: '원본 B2', sheet: '단가', cell: 'B2', source: 'original', old: '삭제 값', new: '' };
  const onLocate = vi.fn();
  const { rerender } = render(<SheetView sheets={[sheet]} changes={[deleted, ...changes]} target={deleted} onLocate={onLocate} />);
  expect(await screen.findByText('삭제 값')).toHaveFocus();
  rerender(<SheetView sheets={[sheet]} changes={changes} target={changes[0]} onLocate={onLocate} />);
  const merged = screen.getByRole('cell', { name: 'B3: 20 → 21' });
  expect(merged).toHaveFocus(); expect(merged).toHaveAttribute('colspan', '2');
});
