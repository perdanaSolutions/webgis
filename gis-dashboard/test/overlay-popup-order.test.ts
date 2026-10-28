import { describe, expect, it } from "vitest";
import { OVERLAY_STYLES } from "../utils/mapLayers";

const BLOCK = ["kode_est", "kode_afd", "kode_blok"];

describe("urutan popup layer (t121u)", () => {
  for (const code of ["tph", "sawit", "landuse", "slope", "jalan", "jembatan", "drainase"]) {
    it(`${code}: Estate, Afdeling, Blok di 3 baris teratas tanpa duplikat`, () => {
      const keys = OVERLAY_STYLES[code]!.popupFields.map(([key]) => key);
      expect(keys.slice(0, 3)).toEqual(BLOCK);
      expect(keys.slice(3).filter((key) => BLOCK.includes(key))).toEqual([]);
    });
  }
});
