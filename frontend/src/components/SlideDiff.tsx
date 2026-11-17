import type { SlideDiff as Slide } from '../api';
import InlineDiff from './InlineDiff';
import { changeLabels } from './ChangeTable';

export default function SlideDiff({ slides }: { slides: Slide[] }) {
  return <section className="section" aria-labelledby="slides-heading"><h2 id="slides-heading">슬라이드 비교</h2>
    {slides.length === 0 && <p className="empty">변경된 슬라이드가 없습니다.</p>}
    {[...slides].sort((a, b) => a.slide - b.slide).map(slide => <section key={slide.slide} className="slide-group">
      <h3>슬라이드 {slide.slide}</h3>
      <ul className="slide-items">{slide.items.map((item, i) => <li key={i}>
        <div className="slide-item-label"><strong>{item.notes ? '노트' : '도형'}: {item.shape}</strong><span className={`change-kind kind-${item.op}`}>{changeLabels[item.op]}</span></div>
        <p className="document-text">{item.op === 'modified' ? <InlineDiff oldText={item.old ?? ''} newText={item.new ?? ''} /> : item.op === 'removed' ? <del>{item.old}</del> : <ins>{item.new}</ins>}</p>
      </li>)}</ul>
    </section>)}
  </section>;
}
