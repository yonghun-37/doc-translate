import { useState } from 'react';
import type { Change } from '../api';
import InlineDiff from './InlineDiff';

export const changeLabels = { added: '추가', removed: '삭제', modified: '수정' };
export default function ChangeTable({ changes }: { changes: Change[] }) {
  const [filter, setFilter] = useState<'all' | Change['op']>('all');
  const shown = changes.filter(change => filter === 'all' || change.op === filter);
  return <section className="section" aria-labelledby="changes-heading">
    <div className="section-heading"><h2 id="changes-heading">변경 내용</h2><span className="muted">{changes.length}건</span></div>
    {changes.length === 0 ? <p className="empty">변경된 내용이 없습니다.</p> : <>
      <div className="filter-buttons" role="group" aria-label="변경 종류">
        {(['all', 'added', 'removed', 'modified'] as const).map(op => <button key={op} aria-pressed={filter === op} onClick={() => setFilter(op)}>{op === 'all' ? '전체' : changeLabels[op]} <span>{op === 'all' ? changes.length : changes.filter(c => c.op === op).length}</span></button>)}
      </div>
      <div className="table-scroll" role="region" aria-label="변경 내용 표" tabIndex={0}><table className="change-table">
        <thead><tr><th scope="col">위치</th><th scope="col">종류</th><th scope="col">이전</th><th scope="col">새 텍스트</th></tr></thead>
        <tbody>{shown.map((change, i) => <tr key={`${change.where}-${i}`}>
          <th scope="row">{change.where}</th><td><span className={`change-kind kind-${change.op}`}>{changeLabels[change.op]}</span></td>
          <td className="document-text">{change.old ?? <span className="muted">없음</span>}</td>
          <td className="document-text">{change.op === 'modified' ? <InlineDiff oldText={change.old ?? ''} newText={change.new ?? ''} /> : change.new ?? <span className="muted">없음</span>}</td>
        </tr>)}</tbody>
      </table></div>
      {shown.length === 0 && <p className="empty">선택한 종류의 변경이 없습니다.</p>}
      <p className="table-note">수정된 텍스트에서 <del>삭제</del>와 <ins>추가</ins> 부분을 강조합니다.</p>
    </>}
  </section>;
}
