"""Numeric-only progress snapshots; intermediate disk writes at most once a second."""
import time

from app.storage import now

LABELS = {'zh-CN': '간체', 'zh-TW': '번체'}
PHASES = {'extract': '문서 읽기', 'reuse': '기존 번역 재사용', 'llm': 'LLM 번역',
          'write': '파일 만들기', 'done': '완료'}


class Progress:
    def __init__(self, plans, save, *, clock=time.monotonic):
        self.save, self.clock = save, clock
        self.last_saved = float('-inf')
        self.seconds = self.completed = 0
        self.plans = plans
        self.value = {'phase': 'extract', 'langs': {
            lang: {'phase': 'extract', 'total': plan['reused'] + plan['translated'],
                   'reused': 0, 'translated': 0, 'done': 0} for lang, plan in plans.items()},
            'started_at': now(), 'updated_at': now(), 'eta_sec': None, 'log': []}

    def record(self, lang, phase, stats=None):
        stats = stats or {}
        current = self.value['langs'][lang]
        current['phase'] = 'llm' if phase == 'batch' else phase
        self.value['phase'] = current['phase']
        for key in ('reused', 'translated'):
            if key in stats:
                current[key] = stats[key]
        current['done'] = current['reused'] + current['translated']
        if phase == 'batch':
            self.seconds += stats['elapsed']
            self.completed += stats['count']
            message = (f"{LABELS[lang]} LLM 묶음 {stats['batch']}/{stats['batches']} 완료 "
                       f"({stats['count']}문장, {stats['elapsed']:.1f}초)")
        elif phase == 'reuse':
            message = f"{LABELS[lang]} 기존 번역 재사용 {current['reused']}문장"
        else:
            message = f'{LABELS[lang]} {PHASES[phase]}'
        self.value['log'] = [*self.value['log'], {'at': now(), 'message': message}][-50:]
        remaining = sum(max(0, plan['translated'] - self.value['langs'][key]['translated'])
                        for key, plan in self.plans.items())
        if self.completed:
            self.value['eta_sec'] = round(self.seconds / self.completed * remaining, 1)
        self.value['updated_at'] = now()
        self.flush()

    def flush(self):
        instant = self.clock()
        if instant - self.last_saved >= 1:
            self.save(self.value)
            self.last_saved = instant
