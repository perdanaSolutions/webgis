import { describe, expect, it } from 'vitest'
import { statusTanamSummary } from '../utils/statusTanam'

describe('statusTanamSummary', () => {
  it('tiga label LC, TBM, TM; % AREA TM = TM / (LC+TBM+TM) (data gis_db_v4 Des 2026)', () => {
    const s = statusTanamSummary([
      { status: 'TM', luas_tanam: 84896.36, jumlah_blok: 3617 },
      { status: 'TBM', luas_tanam: 848.81, jumlah_blok: 43 },
      { status: 'LC', luas_tanam: 1395.07, jumlah_blok: 53 },
    ])!
    expect(s.slices.map((x) => x.key)).toEqual(['LC', 'TBM', 'TM'])
    expect(s.total).toBeCloseTo(87140.24, 2)
    expect(s.tmPct).toBeCloseTo(97.42, 2)
    expect(s.slices[0]!.pct).toBeCloseTo(1.6, 2)
  })
  it('angka pivot Bayu (Σ 12 bulan 2026) -> TM 97,29%', () => {
    const s = statusTanamSummary([
      { status: 'LC', luas_tanam: 18203.28 }, { status: 'TBM', luas_tanam: 10185.72 }, { status: 'TM', luas_tanam: 1018771.68 },
    ])!
    expect(s.total).toBeCloseTo(1047160.68, 2)
    expect(s.tmPct).toBeCloseTo(97.29, 2)
  })
  it('status kosong tidak masuk grafik/penyebut, dicatat terpisah; kategori kosong tetap tampil 0', () => {
    const s = statusTanamSummary([
      { status: 'TM', luas_tanam: 90, jumlah_blok: 9 },
      { status: 'TANPA_STATUS', luas_tanam: 10, jumlah_blok: 2 },
    ])!
    expect(s.tmPct).toBe(100)
    expect(s.slices.find((x) => x.key === 'LC')!.ha).toBe(0)
    expect(s.lainnya).toEqual({ blok: 2, ha: 10 })
  })
  it('tanpa data -> null', () => {
    expect(statusTanamSummary([])).toBeNull()
  })
})
