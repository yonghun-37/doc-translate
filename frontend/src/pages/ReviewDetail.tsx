import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api';
import StatusBadge from '../components/StatusBadge';
import ChangeTable from '../components/ChangeTable';
import SheetDiff from '../components/SheetDiff';
import SlideDiff from '../components/SlideDiff';
import DecisionPanel from '../components/DecisionPanel';
import OutputFiles from '../components/OutputFiles';
import TranslationPlan from '../components/TranslationPlan';
import { formatDate } from './ReviewList';

export default function ReviewDetail() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [notice, setNotice] = useState('');
  const key = ['job', id];
  const query = useQuery({ queryKey: key, queryFn: () => api.job(id), refetchInterval: query => query.state.data?.status === 'translating' ? 2000 : false });
  const job = query.data;
  const hasOriginal = Boolean(job?.files.original);
  const sheets = useQuery({ queryKey: [...key, 'sheets'], queryFn: () => api.sheets(id), enabled: job?.ext === 'xlsx' && hasOriginal });
  const slides = useQuery({ queryKey: [...key, 'slides'], queryFn: () => api.slides(id), enabled: job?.ext === 'pptx' && hasOriginal });
  const onError = async (error: Error) => {
    setNotice(error.message);
    if (error instanceof ApiError && error.status === 409) await client.invalidateQueries({ queryKey: key });
  };
  const mutation = useMutation({
    mutationFn: ({ action, body }: { action: 'translate' | 'reject' | 'retry'; body?: { by?: string; reason?: string } }) => api.decide(id, action, body),
    onMutate: () => setNotice(''),
    onSuccess: result => {
      client.setQueryData(key, result);
      void client.invalidateQueries({ queryKey: ['jobs'] });
    }, onError,
  });
  const deletion = useMutation({
    mutationFn: () => api.delete(id),
    onMutate: () => setNotice(''),
    onSuccess: () => {
      client.removeQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: ['jobs'] });
      navigate('/');
    }, onError,
  });
  const busy = mutation.isPending || deletion.isPending;
  const errors = [notice, query.error?.message, sheets.error?.message, slides.error?.message, job?.status === 'failed' ? job.error : null].filter((value): value is string => Boolean(value));
  return <>
    {errors.length > 0 && <div className="error-banner" role="alert">{[...new Set(errors)].map(error => <p key={error}>{error}</p>)}</div>}
    <Link to="/" className="back-link">작업 목록으로</Link>
    {query.isPending && <p className="empty" role="status">작업 내용을 불러오는 중입니다.</p>}
    {job && <>
      <div className="page-heading detail-heading"><div><h1>{job.title}</h1><p className="muted">{job.ext} · {job.id}</p></div><div aria-live="polite" aria-atomic="true"><StatusBadge status={job.status} /></div></div>
      <dl className="review-meta"><div><dt>생성 시각</dt><dd>{formatDate(job.created_at)}</dd></div><div><dt>올린 사람</dt><dd>{job.uploaded_by ?? '—'}</dd></div><div><dt>결정 시각</dt><dd>{formatDate(job.decided_at)}</dd></div><div><dt>결정자</dt><dd>{job.decided_by ?? '—'}</dd></div>
        <div><dt>원본</dt><dd>{job.files.original ?? '없음'}</dd></div><div><dt>수정본</dt><dd>{job.files.revised}</dd></div><div><dt>기존 간체본</dt><dd>{job.files['base_zh-CN'] ?? '없음'}</dd></div><div><dt>기존 번체본</dt><dd>{job.files['base_zh-TW'] ?? '없음'}</dd></div>
        {job.reason && <div className="reason-meta"><dt>반려 사유</dt><dd>{job.reason}</dd></div>}</dl>
      {job.status === 'translating' && <p className="info-banner" role="status">번역을 진행하고 있습니다. 완료되면 결과를 자동으로 표시합니다.</p>}
      {job.status === 'failed' && <button className="primary" disabled={busy} onClick={() => mutation.mutate({ action: 'retry' })}>{busy ? '처리 중…' : '재시도'}</button>}
      {job.status === 'translated' && <OutputFiles outputs={job.outputs} stats={job.stats} />}
      {job.ext === 'docx' && job.artifacts.redline && <div className="redline-download"><a className="button" href={job.artifacts.redline} download>Word 변경 추적 내려받기</a><p className="muted">Word에서 열면 변경 추적으로 보입니다.</p></div>}
      {hasOriginal ? <ChangeTable changes={job.changes} /> : <p className="info-banner">신규 문서 — 전체 번역</p>}
      {hasOriginal && job.ext === 'xlsx' && (sheets.isPending ? <p role="status">시트 비교를 불러오는 중입니다.</p> : sheets.data && <SheetDiff sheets={sheets.data} />)}
      {hasOriginal && job.ext === 'pptx' && (slides.isPending ? <p role="status">슬라이드 비교를 불러오는 중입니다.</p> : slides.data && <SlideDiff slides={slides.data} />)}
      <TranslationPlan job={job} />
      {job.status === 'pending' && <DecisionPanel newDocument={!hasOriginal} busy={busy} onDecision={(action, body) => mutation.mutate({ action, body })} />}
      <div className="section"><button className="reject-button" disabled={busy || job.status === 'translating'} onClick={() => {
        if (!busy && window.confirm('이 작업의 입력 파일, 검토 내용과 번역 결과를 모두 삭제할까요?')) deletion.mutate();
      }}>{deletion.isPending ? '삭제 중…' : '작업 삭제'}</button></div>
    </>}
  </>;
}
