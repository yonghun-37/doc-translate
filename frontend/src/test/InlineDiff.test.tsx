import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import InlineDiff from '../components/InlineDiff';

describe('글자별 비교', () => {
  it('여러 변경 사이의 공통 글자와 유니코드 문자를 보존한다', () => {
    const { container } = render(<InlineDiff oldText="앞가중간나뒤😀" newText="앞다중간라뒤😀" />);
    expect([...container.querySelectorAll('del')].map(el => el.textContent)).toEqual(['가', '나']);
    expect([...container.querySelectorAll('ins')].map(el => el.textContent)).toEqual(['다', '라']);
    expect(container).toHaveTextContent('중간');
    expect(container.textContent).toContain('뒤😀');
  });

  it('빈 문자열로 바뀌면 전체를 삭제로 표시한다', () => {
    const { container } = render(<InlineDiff oldText="전체 삭제" newText="" />);
    expect(container.querySelector('del')).toHaveTextContent('전체 삭제');
    expect(container.querySelector('ins')).toBeNull();
  });
});
