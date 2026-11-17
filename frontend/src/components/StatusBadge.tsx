import type { Status } from '../api';

export const statusLabels: Record<Status, string> = {
  pending: '검토 대기', translating: '번역 중',
  translated: '완료', rejected: '반려', failed: '실패',
};
export default function StatusBadge({ status }: { status: Status }) {
  return <span className={`status-badge status-${status}`}>{statusLabels[status]}</span>;
}
