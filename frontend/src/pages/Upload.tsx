import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { rememberedReviewer, rememberReviewer } from '../reviewer';

const slots = [
  { key: 'original', label: '원본 (한국어, 선택)' },
  { key: 'revised', label: '수정본 (한국어, 필수)' },
  { key: 'base_zh_cn', label: '기존 간체본 (선택)' },
  { key: 'base_zh_tw', label: '기존 번체본 (선택)' },
] as const;
type Slot = typeof slots[number]['key'];
const extension = (file: File) => file.name.split('.').at(-1)?.toLowerCase();

export default function Upload() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [files, setFiles] = useState<Partial<Record<Slot, File>>>({});
  const [title, setTitle] = useState('');
  const [by, setBy] = useState(rememberedReviewer);
  const errorBanner = useRef<HTMLDivElement>(null);
  const ext = files.revised && extension(files.revised);
  const fileError = (file?: File) => !file ? '' : !['docx', 'xlsx', 'pptx'].includes(extension(file) ?? '')
    ? 'docx·xlsx·pptx 파일을 선택하세요.' : ext && extension(file) !== ext ? '수정본과 확장자가 다릅니다.' : '';
  const canSubmit = Boolean(files.revised) && Object.values(files).every(file => !fileError(file));
  const mutation = useMutation({
    mutationFn: api.upload,
    onSuccess: job => {
      void client.invalidateQueries({ queryKey: ['jobs'] });
      client.setQueryData(['job', job.id], job);
      navigate(`/jobs/${job.id}`);
    },
    onError: () => requestAnimationFrame(() => errorBanner.current?.focus()),
  });
  return <>
    {mutation.error && <div className="error-banner" role="alert" tabIndex={-1} ref={errorBanner}>{mutation.error.message}</div>}
    <Link to="/" className="back-link">작업 목록으로</Link>
    <div className="page-heading"><div><h1>새 작업</h1><p className="muted">파일을 함께 올린 뒤 변경 내용과 번역 계획을 확인하세요.</p></div></div>
    <form className="upload-form" aria-busy={mutation.isPending} onSubmit={event => {
      event.preventDefault();
      if (!canSubmit || mutation.isPending) return;
      const body = new FormData();
      for (const slot of slots) { const file = files[slot.key]; if (file) body.set(slot.key, file); }
      body.set('title', title.trim());
      body.set('by', by.trim());
      rememberReviewer(by);
      mutation.mutate(body);
    }}>
      <fieldset disabled={mutation.isPending}>
        <legend className="sr-only">업로드할 작업 정보</legend>
        <p id="file-help" className="field-help">Word (.docx), Excel (.xlsx), PowerPoint (.pptx)를 지원합니다. 모든 파일의 형식이 같아야 합니다.</p>
        <div className="upload-slots">{slots.map(slot => {
          const file = files[slot.key], error = fileError(file);
          return <div className="upload-slot" key={slot.key}>
            <label htmlFor={slot.key}>{slot.label}<input id={slot.key} type="file" accept=".docx,.xlsx,.pptx" required={slot.key === 'revised'} aria-invalid={Boolean(error)} aria-describedby={`${slot.key}-help${error ? ` ${slot.key}-error` : ''}`} onChange={event => {
              const next = event.target.files?.[0];
              setFiles(previous => ({ ...previous, [slot.key]: next }));
              if (slot.key === 'revised') setTitle(next?.name ?? '');
              mutation.reset();
            }} /></label>
            <p className="field-help" id={`${slot.key}-help`}>{file?.name ?? '선택한 파일 없음'}</p>
            {error && <p className="error-banner" role="alert" id={`${slot.key}-error`}>{error}</p>}
          </div>;
        })}</div>
        {!files.original && <p className="info-banner">원본이 없으면 신규 문서로 전체 번역합니다. 기존 중국어본을 함께 올려도 재사용하지 않습니다.</p>}
        <label htmlFor="job-title">제목 (선택)<input id="job-title" value={title} maxLength={240} onChange={event => setTitle(event.target.value)} /></label>
        <label htmlFor="uploader">올린 사람 이름 (선택)<input id="uploader" autoComplete="name" maxLength={200} value={by} onChange={event => setBy(event.target.value)} /></label>
        <div className="decision-actions"><button className="primary" type="submit" disabled={!canSubmit || mutation.isPending}>{mutation.isPending ? '올리는 중…' : '올리기'}</button></div>
        {mutation.isPending && <p role="status" className="field-help">파일을 올리고 변경 내용·기존 번역 매칭을 준비하고 있습니다.</p>}
      </fieldset>
    </form>
  </>;
}
