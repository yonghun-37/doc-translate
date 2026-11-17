export function rememberedReviewer(): string {
  try { return localStorage.getItem('doc-translate.reviewer') ?? ''; } catch { return ''; }
}

export function rememberReviewer(by: string) {
  try { localStorage.setItem('doc-translate.reviewer', by.trim()); } catch { /* Storage may be disabled. */ }
}
