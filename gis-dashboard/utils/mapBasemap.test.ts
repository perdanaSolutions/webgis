import { describe, expect, it } from "vitest";
import { basemapAccessMessage, basemapCapabilitiesUrl, basemapHost, basemapServiceUrl, fotoUdaraProblem, setBasemapDiagnostics } from "./mapBasemap";
import { BASEMAPS } from "./mapLayers";

const fotoUdara = BASEMAPS.find((item) => item.key === "tpa-sga")!;
const tile = fotoUdara.tiles[0]!;

describe("basemap Foto Udara", () => {
  it("judul Foto Udara (bukan 'Udata') dan lewat proxy backend dengan layer group tpgis:tpgis_fu", () => {
    expect(fotoUdara.label).toBe("Foto Udara");
    expect(tile.proxy).toBe(true);
    expect(tile.url).toBe("/v1/basemap/foto-udara/wms");
    expect(tile.layers).toBe("tpgis:tpgis_fu");
    expect(tile.tokenParam).toBeUndefined();
    expect(basemapHost(fotoUdara)).toBe("digilink.teladanprima.com");
  });

  it("token tidak pernah ditempel ke URL browser untuk tile proxy", () => {
    expect(basemapServiceUrl(tile, "secret-token")).toBe(tile.url);
  });

  it("utilitas token lama tetap bekerja untuk WMS langsung", () => {
    const direct = { url: "https://example.org/wms", attribution: "", service: "wms" as const, tokenParam: "token", version: "1.1.0" };
    const url = new URL(basemapCapabilitiesUrl(direct, "t"));
    expect(url.searchParams.get("token")).toBe("t");
    expect(url.searchParams.get("request")).toBe("GetCapabilities");
  });

  it("pesan dialog sesuai penyebab sebenarnya", () => {
    expect(fotoUdaraProblem(null, { reason: "unauthorized", message: "" }, "x")).toMatch(/401/);
    expect(fotoUdaraProblem({ ok: false, reason: "layer_not_found", message: "Layer tpgis:TPA-SGA tidak ada di GeoServer." }, null, "tpgis:TPA-SGA"))
      .toMatch(/TPA-SGA tidak ada/);
    expect(fotoUdaraProblem({ ok: false, reason: "not_configured" }, null, "x")).toMatch(/FOTO_UDARA_WMS_TOKEN/);
    expect(fotoUdaraProblem({ ok: true, bbox: [116, -2, 118, 1] }, null, "x")).toBeNull();
  });

  it("tanpa alasan khusus: arahkan ke area cakupan", () => {
    setBasemapDiagnostics({ ok: true, bbox: [116.38, -2.35, 118.58, 1.66] }, null);
    const msg = basemapAccessMessage("unavailable", fotoUdara);
    expect(msg.body).toMatch(/cakupan/);
    expect(msg.body).not.toMatch(/Udata/);
    setBasemapDiagnostics({ ok: false, reason: "unauthorized" }, null);
    expect(basemapAccessMessage("unavailable", fotoUdara).body).toMatch(/401/);
  });
});
