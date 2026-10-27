import { describe, expect, it } from "vitest"
import * as XLSX from "xlsx"

import { readExcelPreview, buildExcelTemplate } from "./trxExcelFile"
import {
  TRX_KINDS,
  fileModeFromName,
  isTrxExcelFile,
  missingHeaderGroups,
  normalizeCell,
} from "./trxUpload"

describe("katalog upload transaksi", () => {
  it("menyediakan 25 kolom areal statement dan 13 kolom rotasi", () => {
    const areal = TRX_KINDS[0]
    const rotasi = TRX_KINDS[1]
    expect(areal.columns).toHaveLength(25)
    expect(areal.columns).toContain("StatusTanam")
    expect(areal.columns).toContain("Curam")
    expect(rotasi.columns).toEqual([
      "Periode", "Area", "PT", "Estate", "Afdeling", "Blok", "Luas", "Pokok",
      "Rotasi", "Pusingan", "Status Pusingan", "Bulan", "Tanggal",
    ])
    expect(Object.keys(areal.example)).toEqual(areal.columns)
    expect(Object.keys(rotasi.example)).toEqual(rotasi.columns)
  })

  it("menganggap penanda kosong Excel sebagai sel kosong", () => {
    expect(normalizeCell("(Blanks)")).toBe("")
    expect(normalizeCell(" n/a ")).toBe("")
    expect(normalizeCell("TM")).toBe("TM")
  })

  it("menandai periode kurang bila Year ada tanpa Month dan tanpa Tanggal", () => {
    const areal = TRX_KINDS[0]
    const missing = missingHeaderGroups(["Year", "AreaCode", "StatusTanam", "KodeBlok", "DivisionCode", "UnitCode"], areal)
    expect(missing.map((item) => item.label)).toContain("Periode (Year + Month, atau Tanggal)")
  })

  it("menerima periode dari kolom Tanggal", () => {
    const rotasi = TRX_KINDS[1]
    const missing = missingHeaderGroups(
      ["Periode", "Tanggal", "Estate", "Afdeling", "Blok"],
      rotasi,
    )
    expect(missing.map((item) => item.label)).not.toContain("Periode (Year + Month, atau Tanggal)")
  })

  it("hanya menerima file Excel (.xlsx/.xls), .json ditolak", () => {
    expect(isTrxExcelFile("data.xlsx")).toBe(true)
    expect(isTrxExcelFile("DATA.XLS")).toBe(true)
    expect(isTrxExcelFile(" laporan.Xlsx ")).toBe(true)
    for (const name of ["data.json", "data.geojson", "data.csv", "data.xlsx.json", "xlsx", "", null, undefined]) {
      expect(isTrxExcelFile(name)).toBe(false)
    }
    expect(fileModeFromName("a.xlsx")).toBe("excel")
    expect(fileModeFromName("a.json")).toBeNull()
  })

  it("katalog tidak punya endpoint/contoh JSON lagi", () => {
    for (const kind of TRX_KINDS) {
      expect(Object.keys(kind.endpoints).sort()).toEqual(["analyze", "excel"])
      expect("jsonFilename" in kind).toBe(false)
    }
  })
})

describe("template excel", () => {
  it("sheet Data hanya berisi header, contoh ada di sheet lain", async () => {
    for (const spec of TRX_KINDS) {
      const workbook = await buildExcelTemplate(spec)
      expect(workbook.SheetNames).toEqual(["Data", "Contoh", "Petunjuk"])
      const data = XLSX.utils.sheet_to_json<(string | number)[]>(workbook.Sheets.Data, { header: 1 })
      const contoh = XLSX.utils.sheet_to_json<(string | number)[]>(workbook.Sheets.Contoh, { header: 1 })
      expect(data).toEqual([spec.columns])
      expect(contoh[0]).toEqual(spec.columns)
      expect(contoh).toHaveLength(2)
      expect(missingHeaderGroups(spec.columns, spec)).toEqual([])
    }
  })

  it("membaca header sheet pertama dan mengosongkan penanda blank", async () => {
    const sheet = XLSX.utils.aoa_to_sheet([
      ["Year", "Month", "StatusTanam"],
      [2026, 1, "(Blanks)"],
    ])
    const book = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(book, sheet, "Data")
    const bytes = XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer
    const file = new File([bytes], "areal.xlsx")

    const preview = await readExcelPreview(file)
    expect(preview.sheetName).toBe("Data")
    expect(preview.headers).toEqual(["Year", "Month", "StatusTanam"])
    expect(preview.rows).toEqual([{ Year: "2026", Month: "1", StatusTanam: "" }])
  })
})
