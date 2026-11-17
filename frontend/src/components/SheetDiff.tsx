import { useState } from 'react';
import type { SheetDiff as Sheet } from '../api';

const statuses = { added: '추가', removed: '삭제', changed: '변경', same: '변경 없음' };
const markers: Record<string, string> = { '+++': '추가', '---': '삭제', '->': '수정', '@@': '머리글', '': '' };
export default function SheetDiff({ sheets }: { sheets: Sheet[] }) {
  const [selected, setSelected] = useState(0);
  const current = sheets[selected] ?? sheets[0];
  if (!current) return <p className="empty">표시할 시트가 없습니다.</p>;
  return <section className="section" aria-labelledby="sheets-heading">
    <h2 id="sheets-heading">시트 비교</h2>
    <div role="tablist" aria-label="시트" className="sheet-tabs">{sheets.map((sheet, i) => <button key={sheet.sheet} role="tab" id={`sheet-tab-${i}`} aria-controls="sheet-panel" aria-selected={sheet === current} tabIndex={sheet === current ? 0 : -1} onClick={() => setSelected(i)} onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? sheets.length - 1 : (i + (event.key === 'ArrowRight' ? 1 : -1) + sheets.length) % sheets.length;
      setSelected(next);
      document.getElementById(`sheet-tab-${next}`)?.focus();
    }}>{sheet.sheet}</button>)}</div>
    <div id="sheet-panel" role="tabpanel" aria-labelledby={`sheet-tab-${sheets.indexOf(current)}`}>
      <p className="muted">{statuses[current.status]}</p>
      <div className="table-scroll" role="region" aria-label={`${current.sheet} 비교 표`} tabIndex={0}><table>
        <thead><tr><th scope="col">변경</th>{current.header.map((cell, i) => <th scope="col" key={i}>{cell || `열 ${i + 1}`}</th>)}</tr></thead>
        <tbody>{current.rows.map((row, i) => <tr key={i} className={row.marker === '+++' ? 'diff-row-added' : row.marker === '---' ? 'diff-row-removed' : undefined}>
          <th scope="row">{/^-+>$/.test(row.marker) ? '수정' : markers[row.marker] ?? row.marker}</th>{row.cells.map((cell, j) => {
            const arrow = /^-+>$/.test(row.marker) ? cell.indexOf(row.marker) : -1;
            return <td key={j} className="document-text">{arrow >= 0 ? <><del>{cell.slice(0, arrow)}</del><span aria-hidden="true"> → </span><ins>{cell.slice(arrow + row.marker.length)}</ins></> : cell}</td>;
          })}
        </tr>)}</tbody>
      </table></div>
    </div>
  </section>;
}
