/**
 * Kartu laporan "Status Tanam": tiga kategori tetap LC, TBM, TM (urutan ini), data = Σ luas tanam per status
 * pada snapshot periode terakhir dari GET /v1/dashboard/laporan (status_tanam.per_status, sudah di-scope role).
 * Status kosong/lain tidak masuk grafik maupun penyebut persen; hanya dilaporkan sebagai catatan.
 */
export const STATUS_TANAM_KEYS = ['LC', 'TBM', 'TM'] as const
export type StatusTanamKey = (typeof STATUS_TANAM_KEYS)[number]

export const STATUS_TANAM_LABEL: Record<StatusTanamKey, string> = {
  LC: 'Pembukaan Lahan',
  TBM: 'Tanaman Belum Menghasilkan',
  TM: 'Tanaman Menghasilkan',
}

export type StatusTanamSlice = { key: StatusTanamKey; label: string; ha: number; blok: number; pct: number }
export type StatusTanamSummary = {
  slices: StatusTanamSlice[]
  total: number
  tmPct: number
  lainnya: { blok: number; ha: number }
}

export function statusTanamSummary(perStatus: Array<Record<string, any>> | null | undefined): StatusTanamSummary | null {
  const sums = new Map<StatusTanamKey, { ha: number; blok: number }>()
  const lainnya = { blok: 0, ha: 0 }
  for (const row of perStatus ?? []) {
    const key = String(row.status ?? '').trim().toUpperCase()
    const ha = Number(row.luas_tanam ?? 0)
    const blok = Number(row.jumlah_blok ?? 0)
    if ((STATUS_TANAM_KEYS as readonly string[]).includes(key)) {
      const cur = sums.get(key as StatusTanamKey) ?? { ha: 0, blok: 0 }
      sums.set(key as StatusTanamKey, { ha: cur.ha + (Number.isFinite(ha) ? ha : 0), blok: cur.blok + blok })
    } else {
      lainnya.blok += blok
      lainnya.ha += Number.isFinite(ha) ? ha : 0
    }
  }
  const total = [...sums.values()].reduce((sum, item) => sum + item.ha, 0)
  if (!(total > 0)) return null
  const slices = STATUS_TANAM_KEYS.map((key) => {
    const item = sums.get(key) ?? { ha: 0, blok: 0 }
    return { key, label: STATUS_TANAM_LABEL[key], ha: item.ha, blok: item.blok, pct: (item.ha / total) * 100 }
  })
  return { slices, total, tmPct: slices[2]!.pct, lainnya }
}
