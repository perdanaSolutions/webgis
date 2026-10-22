"""
Konteks part upload (FE memecah file jadi beberapa part ≤1.000 feature).

Diset oleh runner selama satu analyze/execute berjalan, dibaca oleh:
- `quarantine.save`: nomor fitur karantina = offset + nomor di part (nomor baris global preview FE);
- query hapus "data lama periode ini" di service execute: baris yang disimpan part LAIN dari grup
  upload yang sama (`protected_batch_ids`) tidak ikut dihapus, sehingga part 2 tidak menghapus
  data blok yang baru saja disimpan part 1.
Memakai ContextVar supaya tanda tangan service lama tidak perlu diubah.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PartContext:
    offset: int = 0
    part_index: int = 1
    part_total: int = 1
    protected_batch_ids: tuple[str, ...] = field(default_factory=tuple)


_current: ContextVar[PartContext] = ContextVar("upload_part_context", default=PartContext())


def current() -> PartContext:
    return _current.get()


@contextmanager
def use(ctx: PartContext):
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)


# Fragmen SQL untuk query DELETE/UPSERT data lama: lewati baris milik part lain grup yang sama.
NOT_PROTECTED = "(upload_batch_id IS NULL OR NOT (upload_batch_id = ANY(CAST(:protected_batches AS uuid[]))))"


def protected_params() -> dict:
    return {"protected_batches": list(current().protected_batch_ids)}
