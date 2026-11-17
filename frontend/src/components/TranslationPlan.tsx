import { languages, languageLabels, type JobDetail } from '../api';

export default function TranslationPlan({ job }: { job: JobDetail }) {
  return <section className="section" aria-labelledby="plan-heading">
    <h2 id="plan-heading">번역 계획</h2>
    <div className="language-plans">{languages.map(lang => {
      const match = job.alignment[lang], plan = job.plan[lang];
      const low = match && match.total > 0 && match.matched / match.total < 0.5;
      return <section className="language-plan" key={lang} aria-label={`${languageLabels[lang]} 번역 계획`}>
        <h3>중국어 {languageLabels[lang]} ({lang})</h3>
        <p className="plan-counts">기존 번역 재사용 예정 <strong>{plan.reused}개</strong> / 새로 번역 <strong>{plan.translated}개</strong></p>
        <p className="muted">{match ? `원본 매칭 ${match.matched}/${match.total}` : '기존 중국어본 없음 — 전체 번역'}</p>
        {match && !job.files.original && <p className="info-banner">한국어 원본이 없어 기존본을 재사용할 수 없습니다.</p>}
        {low && <p className="warning-banner" role="alert">기존 {languageLabels[lang]}본 매칭률이 50% 미만입니다. 파일이 올바른지 확인하세요.</p>}
        {match && match.unmatched_samples.length > 0 && <details><summary>매칭 안 된 원본 문장 ({match.unmatched_samples.length}개 표시)</summary><ul className="unmatched-samples">{match.unmatched_samples.map((sample, i) => <li key={i}><strong>{sample.where}</strong><p className="document-text">{sample.text}</p></li>)}</ul></details>}
      </section>;
    })}</div>
    <p className="table-note">재사용은 수정본의 완전 일치 문장 수, 새 번역은 중복을 제외한 문장 수입니다. 숫자·단위만 있는 텍스트는 번역하지 않습니다.</p>
  </section>;
}
