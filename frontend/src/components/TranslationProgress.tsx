import { useEffect, useState } from 'react';
import { languages, languageLabels, type Phase, type Progress } from '../api';
const labels: Record<Phase, string> = { extract: '문서 읽기', reuse: '기존 번역 재사용', llm: 'LLM 번역', write: '파일 만들기', done: '완료' };
const duration = (seconds: number) => `${Math.floor(Math.max(0, seconds) / 60)}분 ${Math.floor(Math.max(0, seconds) % 60)}초`;
export default function TranslationProgress({ progress, running }: { progress: Progress; running: boolean }) {
  const [clock, setClock] = useState(Date.now());
  useEffect(() => { if (running) { const timer = window.setInterval(() => setClock(Date.now()), 1000); return () => clearInterval(timer); } }, [running]);
  const elapsed = ((running ? clock : Date.parse(progress.updated_at)) - Date.parse(progress.started_at)) / 1000;
  return <section className="section translation-progress" aria-labelledby="progress-heading"><h2 id="progress-heading">번역 진행 상황</h2>
    <ol className="progress-phases">{(['extract', 'reuse', 'llm', 'write'] as Phase[]).map(phase => <li key={phase} aria-current={progress.phase === phase ? 'step' : undefined}>{labels[phase]}</li>)}</ol>
    <p role="status">{running ? labels[progress.phase] : progress.phase === 'done' ? '번역 완료' : '번역 중단'} · 경과 {duration(elapsed)} · 남은 예상 {progress.eta_sec === null ? '계산 중' : duration(progress.eta_sec)}</p>
    <div className="language-plans">{languages.map(lang => { const p = progress.langs[lang]; return <div key={lang}><label htmlFor={`progress-${lang}`}>{languageLabels[lang]} · {labels[p.phase]} · 재사용 {p.reused} + 번역 {p.translated}/{Math.max(0, p.total - p.reused)}</label><progress id={`progress-${lang}`} max={Math.max(1, p.total)} value={p.total === 0 && p.phase === 'done' ? 1 : p.done} /></div>; })}</div>
    <details open={!running}><summary>최근 기록 ({progress.log.length}건)</summary><ol className="progress-log">{progress.log.map((entry, i) => <li key={i}><time dateTime={entry.at}>{new Date(entry.at).toLocaleTimeString('ko-KR')}</time> {entry.message}</li>)}</ol></details>
  </section>;
}
