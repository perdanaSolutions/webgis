import { describe, expect, it } from "vitest";

import { formatDecimalId, truncateDecimal } from "../utils/numberFormat";
import { formatNumberId } from "../utils/mapBlokPopup";

describe("formatDecimalId (30 Okt 2026)", () => {
  it("memotong ke 2 desimal tanpa membulatkan", () => {
    expect(formatDecimalId(1.456)).toBe("1,45");
    expect(formatDecimalId(1.999)).toBe("1,99");
    expect(formatDecimalId(-1.456)).toBe("-1,45");
    expect(formatDecimalId(-0.004)).toBe("0");
  });
  it("aman floating point", () => {
    expect(formatDecimalId(1.15)).toBe("1,15");
    expect(formatDecimalId(0.1 + 0.2)).toBe("0,30");
    expect(formatDecimalId(4.35)).toBe("4,35");
  });
  it("bilangan bulat tanpa desimal, ribuan titik", () => {
    expect(formatDecimalId(12)).toBe("12");
    expect(formatDecimalId(12345.678)).toBe("12.345,67");
    expect(formatDecimalId(1234567)).toBe("1.234.567");
    expect(formatDecimalId(1.5)).toBe("1,50");
    expect(formatDecimalId(2.001)).toBe("2");
  });
  it("kosong -> fallback", () => {
    expect(formatDecimalId(null)).toBe("-");
    expect(formatDecimalId("abc", "—")).toBe("—");
  });
  it("truncateDecimal & popup", () => {
    expect(truncateDecimal(14.2857)).toBe(14.28);
    expect(truncateDecimal(-14.2857)).toBe(-14.28);
    expect(formatNumberId(0.4706)).toBe("0,47");
  });
});
