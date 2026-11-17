type Part = { kind: 'same' | 'added' | 'removed'; text: string };

function diff(oldText: string, newText: string): Part[] {
  const oldChars = Array.from(oldText), newChars = Array.from(newText);
  let start = 0, end = 0;
  while (start < oldChars.length && start < newChars.length && oldChars[start] === newChars[start]) start++;
  while (end < oldChars.length - start && end < newChars.length - start && oldChars[oldChars.length - end - 1] === newChars[newChars.length - end - 1]) end++;
  const left = oldChars.slice(start, oldChars.length - end), right = newChars.slice(start, newChars.length - end);
  const parts: Part[] = [];
  const append = (kind: Part['kind'], text: string) => {
    if (!text) return;
    if (parts.at(-1)?.kind === kind) parts[parts.length - 1].text += text;
    else parts.push({ kind, text });
  };
  append('same', oldChars.slice(0, start).join(''));
  // Bound memory for unusually long paragraphs; keep shared edges in that case.
  if (left.length * right.length > 1_000_000) {
    append('removed', left.join(''));
    append('added', right.join(''));
  } else {
    const width = right.length + 1;
    const lengths = new Uint32Array((left.length + 1) * width);
    for (let i = left.length - 1; i >= 0; i--) {
      for (let j = right.length - 1; j >= 0; j--) {
        lengths[i * width + j] = left[i] === right[j] ? 1 + lengths[(i + 1) * width + j + 1] : Math.max(lengths[(i + 1) * width + j], lengths[i * width + j + 1]);
      }
    }
    let i = 0, j = 0;
    while (i < left.length || j < right.length) {
      if (i < left.length && j < right.length && left[i] === right[j]) { append('same', left[i++]); j++; }
      else if (i < left.length && (j === right.length || lengths[(i + 1) * width + j] >= lengths[i * width + j + 1])) append('removed', left[i++]);
      else append('added', right[j++]);
    }
  }
  append('same', oldChars.slice(oldChars.length - end).join(''));
  return parts;
}

export default function InlineDiff({ oldText, newText }: { oldText: string; newText: string }) {
  return <span className="inline-diff">{diff(oldText, newText).map((part, i) => part.kind === 'removed' ? <del key={i}>{part.text}</del> : part.kind === 'added' ? <ins key={i}>{part.text}</ins> : <span key={i}>{part.text}</span>)}</span>;
}
