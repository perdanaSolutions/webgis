/**
 * ID grup upload multi-part (UUID v4) yang diterima backend (`upload_group_id: UUID`).
 * `crypto.randomUUID` hanya ada di secure context (HTTPS/localhost); dashboard dibuka lewat
 * http://IP:port sehingga perlu fallback lewat `crypto.getRandomValues` (tersedia di HTTP) atau Math.random.
 */
export function newUploadGroupId(): string {
  const c = typeof globalThis !== "undefined" ? (globalThis.crypto as Crypto | undefined) : undefined;
  if (c && typeof c.randomUUID === "function") {
    try {
      return c.randomUUID();
    } catch {
      // non-secure context di sebagian browser melempar error: pakai fallback
    }
  }
  const bytes = new Uint8Array(16);
  if (c && typeof c.getRandomValues === "function") c.getRandomValues(bytes);
  else for (let i = 0; i < 16; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
