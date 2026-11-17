import { Link, Route, Routes } from 'react-router-dom';
import ReviewList from './pages/ReviewList';
import ReviewDetail from './pages/ReviewDetail';
import Upload from './pages/Upload';

export default function App() {
  return <>
    <a href="#main" className="skip-link">본문으로 이동</a>
    <header className="site-header"><div className="header-inner"><Link to="/" className="brand">문서 번역 검토</Link><span>변경 확인 · 번역 계획 · 결과</span></div></header>
    <main id="main" tabIndex={-1}>
      <Routes>
        <Route path="/" element={<ReviewList />} />
        <Route path="/new" element={<Upload />} />
        <Route path="/jobs/:id" element={<ReviewDetail />} />
        <Route path="*" element={<><h1>페이지를 찾을 수 없습니다.</h1><Link to="/">작업 목록으로</Link></>} />
      </Routes>
    </main>
    <footer className="site-footer">원본과 수정본을 비교하고 기존 번역을 재사용하세요.</footer>
  </>;
}
