import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type Change, type JobDetail, type SheetDiff as Sheet, type SlideDiff as Slide } from '../api';
import ChangeTable from './ChangeTable';
import SheetView from './SheetView';
import SheetDiff from './SheetDiff';
import PageView from './PageView';
import SlideCompare from './SlideCompare';
import SlideDiff from './SlideDiff';

export default function LayoutView({ job, sheets, slides }: { job: JobDetail; sheets?: Sheet[]; slides?: Slide[] }) {
  const [tab, setTab] = useState<'layout' | 'list'>('layout');
  const [target, setTarget] = useState<Change>();
  const preview = job.preview!;
  const fallback = preview.status === 'unavailable' || preview.status === 'failed';
  const active = fallback ? 'list' : tab;
  const ready = preview.status === 'ready';
  const grid = useQuery({ queryKey: ['job', job.id, 'grid', target?.sheet, target?.cell], queryFn: () => api.grid(job.id, target), enabled: ready && job.ext === 'xlsx' && active === 'layout' });
  const overlays = useQuery({ queryKey: ['job', job.id, 'overlays'], queryFn: () => api.overlays(job.id), enabled: ready && job.ext === 'pptx' && active === 'layout' });
  function locate(change: Change) {
    if (!(change.page || change.slide || change.sheet)) return;
    setTarget(change); setTab('layout');
  }
  return <section className="section" aria-label="문서 변경 검토">
    <div className="sheet-tabs" role="tablist" aria-label="변경 보기">{(['layout', 'list'] as const).map(value => <button key={value} role="tab" id={`view-${value}`} aria-controls="layout-panel" aria-selected={active === value} tabIndex={active === value ? 0 : -1} disabled={value === 'layout' && fallback} onClick={() => setTab(value)} onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || fallback) return;
      event.preventDefault(); const next = event.key === 'Home' ? 'layout' : event.key === 'End' ? 'list' : value === 'layout' ? 'list' : 'layout'; setTab(next); document.getElementById(`view-${next}`)?.focus();
    }}>{value === 'layout' ? '원래 모양' : '변경 목록'}</button>)}</div>
    {preview.message && <p className={fallback ? 'info-banner' : 'warning-banner'}>{preview.message}</p>}
    <div id="layout-panel" role="tabpanel" aria-labelledby={`view-${active}`}>
      {active === 'list' ? <><ChangeTable changes={job.changes} onLocate={fallback ? undefined : locate} />{job.ext === 'xlsx' && sheets && <SheetDiff sheets={sheets} />}{job.ext === 'pptx' && slides && <SlideDiff slides={slides} />}</> : <>
        {preview.status === 'pending' && <p role="status" className="info-banner">미리보기 만드는 중</p>}
        {ready && job.ext === 'docx' && <PageView id={job.id} preview={preview} changes={job.changes} target={target} />}
        {ready && job.ext === 'xlsx' && (grid.isPending ? <p role="status">격자를 불러오는 중입니다.</p> : grid.data && <SheetView sheets={grid.data} target={target} changes={job.changes} onLocate={locate} />)}
        {ready && job.ext === 'pptx' && (overlays.isPending ? <p role="status">변경 도형을 불러오는 중입니다.</p> : overlays.data && <SlideCompare id={job.id} preview={preview} overlays={overlays.data} slides={slides ?? []} target={target} />)}
        {(grid.error || overlays.error) && <p role="alert" className="error-banner">{grid.error?.message || overlays.error?.message} 변경 목록에서 내용을 확인할 수 있습니다.</p>}
      </>}
    </div>
  </section>;
}
