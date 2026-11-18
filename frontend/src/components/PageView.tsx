import { useEffect } from 'react';
import { previewUrl, type Change, type Preview } from '../api';

export default function PageView({ id, preview, changes, target }: { id: string; preview: Preview; changes: Change[]; target?: Change }) {
  useEffect(() => {
    if (target?.page) { const node = document.getElementById(`page-${target.page}`); node?.scrollIntoView?.({ block: 'start' }); node?.focus(); }
  }, [target]);
  return <section className="section" aria-label="Word 원래 모양"><p>색 밑줄 = 추가 · 취소선 = 삭제</p>
    <div className="page-view"><nav className="page-thumbnails" aria-label="페이지 이동">{preview.pages.map(page => {
      const count = changes.filter(c => c.page === page.page).length;
      return <a key={page.name} href={`#page-${page.page}`} aria-label={`${page.page}페이지${count ? `, 변경 ${count}건` : ''}`}>
        <img src={previewUrl(id, page.name)} alt="" loading="lazy" width={page.width} height={page.height} /><span>{page.page}페이지 {count > 0 && '· 변경'}</span>
      </a>;
    })}</nav><div>{preview.pages.map(page => <section className="preview-page" id={`page-${page.page}`} tabIndex={-1} key={page.name}>
      <h3>{page.page}페이지 — 변경 {changes.filter(c => c.page === page.page).length}건</h3>
      <img src={previewUrl(id, page.name)} alt={`Word 변경 추적 ${page.page}페이지`} loading="lazy" width={page.width} height={page.height} />
    </section>)}</div></div>
  </section>;
}
