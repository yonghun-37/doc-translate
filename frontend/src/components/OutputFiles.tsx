import { languages, languageLabels, type JobDetail } from '../api';

export default function OutputFiles({ outputs, stats }: Pick<JobDetail, 'outputs' | 'stats'>) {
  return <section className="section output-section" aria-labelledby="output-heading"><h2 id="output-heading">번역 결과</h2>
    <div className="file-actions">{outputs.map(file => <a className="button" href={file.url} download key={file.lang}>중국어 {languageLabels[file.lang]} ({file.lang}) 내려받기</a>)}</div>
    {outputs.length === 0 && <p className="muted">내려받을 결과 파일이 없습니다.</p>}
    {languages.map(lang => { const counts = stats[lang]; return counts && <div key={lang} className="language-result"><h3>{languageLabels[lang]} 통계</h3><dl className="translation-stats"><div><dt>전체 세그먼트</dt><dd>{counts.segments}</dd></div><div><dt>재사용</dt><dd>{counts.reused}</dd></div><div><dt>새 번역</dt><dd>{counts.translated}</dd></div></dl></div>; })}
  </section>;
}
