import { describe, expect, it } from "vitest";
import { suggestAreasFromRoleName } from "./roleAreaSuggest";

const AREAS = ["BERAU", "BERAU2", "KUKAR", "KUTIM1", "KUTIM2", "KUTIM3", "KUTIM4", "PASER"].map((code) => ({
  code,
  name: code,
}));

const suggest = (name: string) => suggestAreasFromRoleName(name, AREAS);

describe("suggestAreasFromRoleName", () => {
  it("cocok persis: BERAU tidak ikut BERAU2", () => {
    expect(suggest("BERAU")).toEqual(["BERAU"]);
    expect(suggest("ASISTEN BERAU")).toEqual(["BERAU"]);
  });

  it("angka mengikuti nama dasar, dengan atau tanpa spasi", () => {
    expect(suggest("BERAU 2")).toEqual(["BERAU2"]);
    expect(suggest("berau2")).toEqual(["BERAU2"]);
    expect(suggest("KUTIM 1")).toEqual(["KUTIM1"]);
    expect(suggest("MANAGER KUTIM-3")).toEqual(["KUTIM3"]);
  });

  it("nama dasar tanpa angka mencakup semua area bernomor", () => {
    expect(suggest("KUTIM")).toEqual(["KUTIM1", "KUTIM2", "KUTIM3", "KUTIM4"]);
    expect(suggest("MANAGER KUTIM")).toEqual(["KUTIM1", "KUTIM2", "KUTIM3", "KUTIM4"]);
  });

  it("beberapa area dalam satu nama", () => {
    expect(suggest("BERAU KUKAR")).toEqual(["BERAU", "KUKAR"]);
    expect(suggest("KUTIM 1 & PASER")).toEqual(["KUTIM1", "PASER"]);
  });

  it("harus kata utuh dan tidak menebak yang tidak ada", () => {
    expect(suggest("ADMIN")).toEqual([]);
    expect(suggest("BERAUAN")).toEqual([]);
    expect(suggest("KUTIM 9")).toEqual([]);
    expect(suggest("")).toEqual([]);
    expect(suggest("   ")).toEqual([]);
  });

  it("memakai nama area bila kode berbeda", () => {
    expect(suggestAreasFromRoleName("PASER UTARA", [{ code: "A9", name: "PASER" }])).toEqual(["A9"]);
  });
});
