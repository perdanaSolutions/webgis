export interface AreaCandidate {
  code: string;
  name?: string;
}

interface ParsedKey {
  base: string[];
  num: string | null;
}

/** Huruf besar, dipisah per kata; batas huruf-angka juga memisah ("KUTIM1" -> KUTIM, 1). */
function tokenize(text: string): string[] {
  return String(text ?? "")
    .toUpperCase()
    .replace(/([A-Z])(\d)/g, "$1 $2")
    .replace(/(\d)([A-Z])/g, "$1 $2")
    .split(/[^A-Z0-9]+/)
    .filter(Boolean);
}

const isNumber = (token: string | undefined) => !!token && /^\d+$/.test(token);

function parseKey(text: string): ParsedKey | null {
  const tokens = tokenize(text);
  if (!tokens.length) return null;
  const last = tokens[tokens.length - 1];
  if (isNumber(last) && tokens.length > 1) return { base: tokens.slice(0, -1), num: last };
  return { base: tokens, num: null };
}

/** Posisi (indeks token berikutnya) setiap kemunculan urutan `base` di `tokens`. */
function findAfter(tokens: string[], base: string[]): number[] {
  const hits: number[] = [];
  for (let i = 0; i + base.length <= tokens.length; i += 1) {
    if (base.every((part, offset) => tokens[i + offset] === part)) hits.push(i + base.length);
  }
  return hits;
}

/**
 * Menebak area dari nama role. Kata harus utuh (BERAUAN tidak cocok dengan BERAU).
 * - "BERAU" -> BERAU saja (BERAU2 tidak ikut); "BERAU 2" / "BERAU2" -> BERAU2.
 * - "KUTIM" tanpa angka dan tanpa area bernama persis KUTIM -> semua KUTIM1..n.
 */
export function suggestAreasFromRoleName(roleName: string, areas: AreaCandidate[]): string[] {
  const tokens = tokenize(roleName);
  if (!tokens.length) return [];

  const parsed = areas.map((area) => {
    const keys = [area.code, area.name]
      .map((text) => (text ? parseKey(text) : null))
      .filter((key): key is ParsedKey => !!key);
    return { code: area.code, keys };
  });
  const hasPlainBase = (base: string[]) =>
    parsed.some((area) => area.keys.some((key) => key.num === null && key.base.join(" ") === base.join(" ")));

  const matched = new Set<string>();
  for (const area of parsed) {
    for (const key of area.keys) {
      for (const after of findAfter(tokens, key.base)) {
        const next = tokens[after];
        if (key.num !== null) {
          if (next === key.num) matched.add(area.code);
        } else if (!isNumber(next)) {
          matched.add(area.code);
        } else if (!parsed.some((other) => other.keys.some((k) => k.num === next && k.base.join(" ") === key.base.join(" ")))) {
          matched.add(area.code);
        }
      }
      // Nama dasar saja ("KUTIM") untuk area bernomor, bila tidak ada area tanpa nomor dengan nama itu.
      if (key.num !== null && !hasPlainBase(key.base)) {
        for (const after of findAfter(tokens, key.base)) {
          if (!isNumber(tokens[after])) matched.add(area.code);
        }
      }
    }
  }
  return areas.map((area) => area.code).filter((code) => matched.has(code));
}
