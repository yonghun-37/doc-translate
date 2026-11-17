import { useState } from 'react';
import { rememberedReviewer, rememberReviewer } from '../reviewer';

export default function DecisionPanel({ busy, newDocument = false, onDecision }: { busy: boolean; newDocument?: boolean; onDecision: (action: 'translate' | 'reject', body: { by?: string; reason?: string }) => void }) {
  const [by, setBy] = useState(rememberedReviewer);
  const [reason, setReason] = useState('');
  function decide(action: 'translate' | 'reject') {
    if (busy || (action === 'reject' && !reason.trim())) return;
    if (action === 'translate' && !window.confirm(newDocument ? '신규 문서 전체를 중국어 간체와 번체로 번역할까요?' : '번역 계획을 확인했습니다. 중국어 간체와 번체 번역을 시작할까요?')) return;
    rememberReviewer(by);
    onDecision(action, { ...(by.trim() ? { by: by.trim() } : {}), ...(action === 'reject' ? { reason: reason.trim() } : {}) });
  }
  return <section className="section decision-panel" aria-labelledby="decision-heading">
    <h2 id="decision-heading">검토 결정</h2>
    <p className="muted">번역 실행을 누르면 중국어 간체와 번체 번역을 시작합니다.</p>
    <div className="decision-fields">
      <label htmlFor="reviewer">검토자 이름 (선택)<input id="reviewer" maxLength={200} value={by} disabled={busy} autoComplete="name" onChange={event => setBy(event.target.value)} /></label>
      <div className="reason-field"><label htmlFor="reason">반려 사유<textarea id="reason" maxLength={10000} value={reason} disabled={busy} rows={3} onChange={event => setReason(event.target.value)} aria-describedby="reason-help" /></label><span id="reason-help" className="field-help">반려하려면 사유를 입력하세요.</span></div>
    </div>
    <div className="decision-actions"><button className="primary" disabled={busy} onClick={() => decide('translate')}>{busy ? '처리 중…' : '번역 실행'}</button><button className="reject-button" disabled={busy || !reason.trim()} onClick={() => decide('reject')}>반려</button></div>
  </section>;
}
