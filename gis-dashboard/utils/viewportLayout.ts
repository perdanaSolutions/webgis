/** Batas lebar popup peta / modal mengikuti viewport (termasuk saat browser zoom 110%–150%). */
export function viewportPopupMaxWidth(preferredPx: number, marginPx = 48): number {
  if (typeof window === "undefined") return preferredPx;
  const available = window.innerWidth - marginPx;
  return Math.max(160, Math.min(preferredPx, available));
}
