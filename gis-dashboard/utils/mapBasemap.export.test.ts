import { afterEach, describe, expect, it, vi } from "vitest";
import { inlineBlobTiles } from "./mapBasemap";

type FakeImg = { src: string; complete: boolean; naturalWidth: number; naturalHeight: number; _blobUrl?: string;
  onload: null | (() => void); onerror: null | (() => void); removed: boolean; remove: () => void };

function fakeImg(src: string, loaded = true): FakeImg {
  const img: FakeImg = { src: "", complete: loaded, naturalWidth: loaded ? 512 : 0, naturalHeight: loaded ? 512 : 0,
    _blobUrl: src.startsWith("blob:") ? src : undefined, onload: null, onerror: null, removed: false,
    remove() { this.removed = true; } };
  let current = src;
  Object.defineProperty(img, "src", { get: () => current, set: (v: string) => { current = v; queueMicrotask(() => img.onload?.()); } });
  return img;
}

afterEach(() => vi.unstubAllGlobals());

describe("inlineBlobTiles (Unduh Peta + Foto Udara)", () => {
  it("menyematkan ubin blob sebagai data URL, membuang ubin gagal, dan mengabaikan ubin http biasa", async () => {
    const revoke = vi.fn();
    vi.stubGlobal("URL", { revokeObjectURL: revoke });
    vi.stubGlobal("document", { createElement: () => ({ width: 0, height: 0,
      getContext: () => ({ drawImage: vi.fn() }), toDataURL: () => "data:image/jpeg;base64,AAAA" }) });
    const good = fakeImg("blob:http://x/1");
    const broken = fakeImg("blob:http://x/2", false);
    const osm = fakeImg("https://tile.osm.org/1/1/1.png");
    const root = { querySelectorAll: () => [good, broken, osm] } as unknown as HTMLElement;

    const result = await inlineBlobTiles(root);

    expect(result).toEqual({ total: 2, ok: 1, failed: 1 });
    expect(good.src).toBe("data:image/jpeg;base64,AAAA");
    expect(broken.removed).toBe(true);
    expect(osm.src).toBe("https://tile.osm.org/1/1/1.png");
    expect(revoke).toHaveBeenCalledWith("blob:http://x/1");
    expect(revoke).toHaveBeenCalledWith("blob:http://x/2");
  });
});
