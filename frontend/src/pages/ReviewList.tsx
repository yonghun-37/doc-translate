import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api, languages, languageLabels } from '../api';
import StatusBadge from '../components/StatusBadge';

export function formatDate(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ko-KR');
}
export default function ReviewList() {
  const [status, setStatus] = useState('all');
  const [search, setSearch] = useState('');
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ['jobs'], queryFn: api.jobs, refetchInterval: 10000 });
  const jobs = [...(query.data ?? [])].filter(job => (status === 'all' || job.status === status)
    && job.title.toLocaleLowerCase('ko').includes(search.trim().toLocaleLowerCase('ko')))
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  return <>
    {query.error && <div className="error-banner" role="alert">{query.error.message}</div>}
    <div className="page-heading"><div><h1>작업 목록</h1><p className="muted">변경 내용과 기존본 매칭을 확인하고 번역을 실행하세요.</p></div><div className="list-actions"><span className="refresh-note">10초마다 자동 갱신</span><Link to="/new" className="button">새 작업</Link></div></div>
    <div className="list-toolbar"><label htmlFor="status">상태<select id="status" value={status} onChange={event => setStatus(event.target.value)}><option value="all">전체</option><option value="pending">검토 대기</option><option value="translating">번역 중</option><option value="translated">완료</option><option value="rejected">반려</option><option value="failed">실패</option></select></label><label htmlFor="search">제목 검색<input id="search" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="제목으로 검색" /></label><p className="list-count">{jobs.length}개 작업</p></div>
    {query.isPending ? <p role="status" className="empty">작업 목록을 불러오는 중입니다.</p> : <>
      <div className="table-scroll" role="region" aria-label="작업 목록 표" tabIndex={0}><table className="review-list">
        <thead><tr><th scope="col">제목 · 형식</th><th scope="col">상태</th><th scope="col">추가</th><th scope="col">삭제</th><th scope="col">수정</th><th scope="col">기존본 매칭</th><th scope="col">올린 사람</th><th scope="col">생성 시각</th></tr></thead>
        <tbody>{jobs.map(job => {
          const path = `/jobs/${job.id}`;
          return <tr key={job.id} onClick={event => { if (!(event.target as HTMLElement).closest('a')) navigate(path); }} className="review-row">
            <th scope="row"><Link to={path}>{job.title}</Link><span className="file-type">{job.ext}</span></th><td><StatusBadge status={job.status} /></td><td className="numeric">{job.counts.added}</td><td className="numeric">{job.counts.removed}</td><td className="numeric">{job.counts.modified}</td><td>{languages.map(lang => { const match = job.alignment[lang]; return `${languageLabels[lang]} ${match ? `${match.matched}/${match.total}` : '없음'}`; }).join(' · ')}</td><td>{job.uploaded_by ?? '—'}</td><td className="date-cell">{formatDate(job.created_at)}</td>
          </tr>;
        })}</tbody>
      </table></div>
      {jobs.length === 0 && !query.error && <p className="empty">{search || status !== 'all' ? '조건에 맞는 작업이 없습니다.' : '등록된 작업이 없습니다.'}</p>}
    </>}
  </>;
}
