import { useEffect, useState } from 'react';
import { previewUrl, type Change, type Overlay, type Preview, type SlideDiff } from '../api';
import InlineDiff from './InlineDiff';

export default function SlideCompare({ id, preview, overlays, slides, target }: { id: string; preview: Preview; overlays: Overlay[]; slides: SlideDiff[]; target?: Change }) {
  const [changedOnly, setChangedOnly] = useState(false);
  useEffect(() => {
    if (target?.slide) { setChangedOnly(false); }
  }, [target]);
  useEffect(() => {
    if (target?.slide) { const node = document.getElementById(`slide-${target.slide}`); node?.scrollIntoView?.({ block: 'start' }); node?.focus(); }
  }, [target, changedOnly]);
  const numbers = [...new Set(preview.pages.map(p => p.page))].sort((a, b) => a - b);
  return <section className="section" aria-label="슬라이드 원래 모양">
    <div className="preview-toolbar"><p>초록 테두리 = 추가 · 주황 = 수정 · 빨강 = 삭제</p><label className="checkbox-field"><input type="checkbox" checked={changedOnly} onChange={e => setChangedOnly(e.target.checked)} />바뀐 슬라이드만 보기</label></div>
    {numbers.filter(n => !changedOnly || slides.some(s => s.slide === n)).map(n => <section key={n} id={`slide-${n}`} className="slide-preview" tabIndex={-1}>
      <h3>슬라이드 {n}</h3><div className="slide-pair">{(['original', 'revised'] as const).map(side => {
        const page = preview.pages.find(p => p.page === n && p.side === side);
        return <figure key={side}><figcaption>{side === 'original' ? '원본' : '수정본'}</figcaption>{page ? <div className="slide-image">
          <img src={previewUrl(id, page.name)} alt={`슬라이드 ${n} ${side === 'original' ? '원본' : '수정본'}`} loading="lazy" width={page.width} height={page.height} />
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="slide-overlays" aria-label="변경 도형 위치" role="img">{overlays.filter(o => o.slide === n && o.side === side).map((o, i) => <rect key={i} className={`overlay-${o.op}`} x={o.x * 100} y={o.y * 100} width={o.width * 100} height={o.height * 100}><title>{o.shape}: {o.op === 'added' ? '추가' : o.op === 'removed' ? '삭제' : '수정'}</title></rect>)}</svg>
        </div> : <p className="empty">슬라이드 없음 또는 표시 범위 초과</p>}</figure>;
      })}</div>{slides.find(s => s.slide === n)?.items.filter(item => item.notes).map((item, i) => <div className="notes-change" key={i}><strong>발표자 노트</strong><p><InlineDiff oldText={item.old ?? ''} newText={item.new ?? ''} /></p></div>)}
    </section>)}
  </section>;
}
