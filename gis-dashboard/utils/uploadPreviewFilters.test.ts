import { describe, expect, it } from "vitest";
import { findGroupColumns } from "./uploadPreviewFilters";

describe("findGroupColumns", () => {
  it("mencocokkan alias tanpa beda huruf besar/kecil dan urut sesuai grup", () => {
    const found = findGroupColumns(["Blok", "Short_Name_PT", "Est_ID", "Afdeling", "luas", "Group", "AREA", "Company_Code"]);
    expect(found.map((f) => [f.key, f.column])).toEqual([
      ["group", "Group"],
      ["perusahaan", "Short_Name_PT"],
      ["perusahaan", "Company_Code"],
      ["area", "AREA"],
      ["estate", "Est_ID"],
      ["afdeling", "Afdeling"],
      ["blok", "Blok"],
    ]);
  });

  it("kosong bila tidak ada kolom pengelompokan", () => {
    expect(findGroupColumns(["luas", "objectid"])).toEqual([]);
  });
});
