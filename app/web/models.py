from typing import Literal

from pydantic import BaseModel, Field

Status = Literal['pending', 'translating', 'translated', 'rejected', 'failed']
Operation = Literal['added', 'removed', 'modified']


class Counts(BaseModel):
    added: int = 0
    removed: int = 0
    modified: int = 0


class AlignmentCounts(BaseModel):
    total: int
    matched: int


class JobSummary(BaseModel):
    id: str
    title: str
    ext: Literal['docx', 'xlsx', 'pptx']
    status: Status
    counts: Counts
    created_at: str
    uploaded_by: str | None
    alignment: dict[Literal['zh-CN', 'zh-TW'], AlignmentCounts]


class Change(BaseModel):
    op: Operation
    where: str
    old: str | None
    new: str | None


class Artifacts(BaseModel):
    redline: str | None = None


class OutputFile(BaseModel):
    lang: Literal['zh-CN', 'zh-TW']
    url: str


class Stats(BaseModel):
    segments: int
    reused: int
    translated: int


class UnmatchedSample(BaseModel):
    where: str
    text: str


class Alignment(AlignmentCounts):
    lang: Literal['zh-CN', 'zh-TW']
    unmatched_samples: list[UnmatchedSample]


class JobDetail(JobSummary):
    files: dict[Literal['original', 'revised', 'base_zh-CN', 'base_zh-TW'], str]
    decided_at: str | None
    decided_by: str | None
    reason: str | None
    error: str | None
    changes: list[Change]
    alignment: dict[Literal['zh-CN', 'zh-TW'], Alignment]
    plan: dict[Literal['zh-CN', 'zh-TW'], Stats]
    artifacts: Artifacts
    outputs: list[OutputFile]
    stats: dict[Literal['zh-CN', 'zh-TW'], Stats]


class SheetRow(BaseModel):
    marker: str
    cells: list[str]


class SheetDiff(BaseModel):
    sheet: str
    status: Literal['added', 'removed', 'changed', 'same']
    header: list[str]
    rows: list[SheetRow]


class SlideItem(BaseModel):
    shape: str
    notes: bool
    op: Operation
    old: str | None
    new: str | None


class SlideDiff(BaseModel):
    slide: int
    items: list[SlideItem]


class Decision(BaseModel):
    by: str | None = Field(default=None, max_length=200)


class Rejection(Decision):
    reason: str = Field(default='', max_length=10000)
