import { describe, expect, it } from "vitest";
import { humanizeColumn, paginate, toTableRows } from "./tablePagination";

describe("paginate", () => {
  const rows = Array.from({ length: 23 }, (_, i) => i + 1);
  it("membagi halaman dan menjepit nomor halaman", () => {
    expect(paginate(rows, 1, 10)).toMatchObject({ items: rows.slice(0, 10), totalPages: 3, total: 23, start: 1, end: 10 });
    expect(paginate(rows, 3, 10)).toMatchObject({ items: [21, 22, 23], start: 21, end: 23 });
    expect(paginate(rows, 99, 10).page).toBe(3);
    expect(paginate(rows, 0, 25)).toMatchObject({ page: 1, totalPages: 1, end: 23 });
    expect(paginate([], 1, 10)).toMatchObject({ totalPages: 1, total: 0, start: 0, end: 0 });
  });
});

describe("toTableRows & humanizeColumn", () => {
  it("array string jadi satu kolom", () => {
    expect(toTableRows(["E1/A/1", "E1/A/2"], "blok")).toEqual({
      columns: ["blok"], rows: [{ blok: "E1/A/1" }, { blok: "E1/A/2" }],
    });
    expect(toTableRows([{ a: 1 }, { b: 2 }]).columns).toEqual(["a", "b"]);
    expect(humanizeColumn("no_preview")).toBe("No Preview");
  });
});
