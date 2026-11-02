/**
 * Best-effort cabut jti di backend (Redis deny list).
 * Aman di belakang HAProxy tanpa sticky session: revoke disimpan di Redis bersama.
 * Error jaringan/503 diabaikan — pemanggil tetap wajib membersihkan token lokal.
 */

export type RevokeAuthSessionParams = {
  baseUrl: string;
  token: string;
  tokenType?: string | null;
  timeoutMs?: number;
};

export type RevokeFetch = (
  url: string,
  options: {
    method: "POST";
    timeout: number;
    headers: Record<string, string>;
  },
) => Promise<unknown>;

export function revokeAuthSessionUrl(baseUrl: string): string {
  return `${String(baseUrl || "").replace(/\/+$/, "")}/v1/auth/logout`;
}

export async function revokeAuthSession(
  params: RevokeAuthSessionParams,
  fetchImpl?: RevokeFetch,
): Promise<boolean> {
  if (!String(params.baseUrl || "").trim() || !params.token) return false;

  const run = fetchImpl ?? (($fetch as unknown) as RevokeFetch);
  try {
    await run(revokeAuthSessionUrl(params.baseUrl), {
      method: "POST",
      timeout: params.timeoutMs ?? 5000,
      headers: {
        Authorization: `${params.tokenType ?? "bearer"} ${params.token}`,
        accept: "application/json",
      },
    });
    return true;
  } catch {
    return false;
  }
}
