import { describe, expect, it } from "vitest";
import { basemapCapabilitiesUrl, basemapServiceUrl } from "./mapBasemap";
import { BASEMAPS } from "./mapLayers";

const fotoUdata = BASEMAPS.find((item) => item.key === "tpa-sga");
const tile = fotoUdata?.tiles[0];

describe("basemap Foto Udata", () => {
  it("menampilkan judul Foto Udata dan endpoint WMS publik", () => {
    expect(fotoUdata?.label).toBe("Foto Udata");
    expect(tile?.url).toBe("https://digilink.teladanprima.com/fu/wms");
    expect(tile?.version).toBe("1.1.0");
    expect(tile?.tokenParam).toBe("token");
  });

  it("menempelkan token dari pemanggil, bukan dari kode sumber", () => {
    expect(tile).toBeTruthy();
    const url = new URL(basemapServiceUrl(tile!, "secret-token"));
    expect(`${url.origin}${url.pathname}`).toBe("https://digilink.teladanprima.com/fu/wms");
    expect(url.searchParams.get("token")).toBe("secret-token");
    expect(basemapServiceUrl(tile!, "")).toBe(tile!.url);
  });

  it("GetCapabilities memakai versi 1.1.0 dan tetap membawa token", () => {
    const url = new URL(basemapCapabilitiesUrl(tile!, "secret-token"));
    expect(url.searchParams.get("service")).toBe("WMS");
    expect(url.searchParams.get("version")).toBe("1.1.0");
    expect(url.searchParams.get("request")).toBe("GetCapabilities");
    expect(url.searchParams.get("token")).toBe("secret-token");
  });
});
