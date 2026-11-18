import { Fragment, useEffect, useRef, useState } from 'react';
import type { Change, GridSheet } from '../api';

export default function SheetView({ sheets, target, changes, onLocate }: { sheets: GridSheet[]; target?: Change; changes: Change[]; onLocate: (change: Change) => void }) {
  const [selected, setSelected] = useState(sheets[0]?.name);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const container = useRef<HTMLDivElement>(null);
  const current = sheets.find(s => s.name === (target?.sheet ?? selected)) ?? sheets[0];
  // A manual tab change clears the parent target through onLocate.
  useEffect(() => {
    if (!target?.cell || !current) return;
    if (target.source === 'original') setExpanded(old => ({ ...old, [`${current.name}:${target.cell!.replace(/[A-Z]/g, '')}`]: true }));
  }, [target, current]);
  useEffect(() => {
    if (!target?.cell) return;
    const node = container.current?.querySelector<HTMLElement>(`[data-${target.source === 'original' ? 'removed' : 'cell'}="${target.cell}"]`)
      ?? container.current?.querySelector<HTMLElement>(`[data-contains~="${target.cell}"]`);
    node?.scrollIntoView?.({ block: 'center', inline: 'center' }); node?.focus();
  }, [target, current, expanded]);
  if (!current) return <p className="empty">표시할 시트가 없습니다.</p>;
  const index = changes.findIndex(c => c === target || (c.sheet === target?.sheet && c.cell === target?.cell && c.source === target?.source));
  const navigate = (direction: number) => onLocate(changes[(index + direction + changes.length) % changes.length]);
  const removed = (after: number) => current.removed_rows.filter(row => row.after === after).map(row => {
    const key = `${current.name}:${row.index}`;
    return <tr key={`removed-${row.index}`} className="grid-removed"><th scope="row">− {row.index}</th><td colSpan={current.cols.length}>
      <button data-removed={row.cells[0]?.addr} aria-expanded={Boolean(expanded[key])} onClick={() => setExpanded(old => ({ ...old, [key]: !old[key] }))}>원본 {row.index}행 삭제 {expanded[key] ? '접기' : '펼치기'}</button>
      {expanded[key] && <div className="removed-values">{row.cells.map(cell => <span key={cell.addr} data-removed={cell.addr} tabIndex={-1}><strong>{cell.addr}</strong> {cell.value || '빈 셀'}</span>)}</div>}
    </td></tr>;
  });
  return <section className="section" aria-label="엑셀 원래 모양">
    <div className="preview-toolbar"><p>노랑 = 수정 · 초록 = 추가 · 빨강 = 삭제</p><div><button disabled={!changes.length} onClick={() => navigate(-1)}>이전 변경</button><button disabled={!changes.length} onClick={() => navigate(1)}>다음 변경</button></div></div>
    {current.message && <p className="warning-banner">{current.message}</p>}
    {current.status === 'removed' && <p className="warning-banner">삭제된 시트 — 원본을 표시합니다.</p>}
    {target?.sheet === current.name && !target.cell && <p role="status">{target.where}</p>}
    <div id="grid-panel" role="tabpanel" aria-labelledby={`grid-tab-${sheets.indexOf(current)}`}><div className="sheet-viewport" ref={container} role="region" aria-label={`${current.name} 격자`} tabIndex={0}>
      <table className={`sheet-grid${current.status === 'removed' ? ' diff-row-removed' : ''}`}><colgroup><col />{current.cols.map(col => <col key={col.letter} style={{ width: col.width }} />)}</colgroup>
        <thead><tr><th scope="col" aria-label="행 번호" />{current.cols.map(col => <th key={col.letter} scope="col">{col.letter}</th>)}</tr></thead>
        <tbody>{removed(0)}{current.rows.map(row => <Fragment key={row.index}><tr className={row.added ? 'diff-row-added' : undefined} style={{ height: row.height * 4 / 3 }}>
          <th scope="row">{row.index}{row.added && <span className="sr-only"> 추가 행</span>}</th>{row.cells.map(cell => {
            const addresses = cell.change_addrs?.length ? cell.change_addrs : current.changes[cell.addr] ? [cell.addr] : [];
            const change = current.changes[addresses[0]];
            const title = change ? addresses.map(addr => `${addr}: ${current.changes[addr].old || '빈 값'} → ${current.changes[addr].new || '빈 값'}`).join('\n') : `${cell.addr}: ${cell.value}`;
            return <td key={cell.addr} data-cell={cell.addr} data-contains={addresses.join(' ')} tabIndex={change || target?.cell === cell.addr ? 0 : undefined} title={title} aria-label={title}
              rowSpan={cell.span?.rows} colSpan={cell.span?.cols} className={change ? `grid-cell-${change.op}` : undefined}
              style={{ fontWeight: cell.bold ? 700 : undefined, fontStyle: cell.italic ? 'italic' : undefined, backgroundColor: change || row.added ? undefined : cell.fill, color: change || row.added ? undefined : cell.color, textAlign: cell.align }}>
              {change && <span className="sr-only">{change.op === 'added' ? '추가' : change.op === 'removed' ? '삭제' : '수정'} </span>}{cell.value}
            </td>;
          })}</tr>{removed(row.index)}</Fragment>)}</tbody>
      </table>
    </div></div>
    <div className="sheet-tabs" role="tablist" aria-label="시트">{sheets.map((sheet, i) => <button key={sheet.name} role="tab" id={`grid-tab-${i}`} aria-controls="grid-panel" aria-selected={sheet === current} tabIndex={sheet === current ? 0 : -1} onClick={() => { setSelected(sheet.name); onLocate({ op: 'modified', where: `'${sheet.name}' 시트`, sheet: sheet.name, old: '', new: '' }); }} onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? sheets.length - 1 : (i + (event.key === 'ArrowRight' ? 1 : -1) + sheets.length) % sheets.length;
      const button = event.currentTarget.parentElement?.children[next] as HTMLButtonElement; button?.click(); button?.focus();
    }}>{sheet.name}{sheet.status !== 'same' && <span aria-label="변경 있음"> ·</span>}</button>)}</div>
  </section>;
}
