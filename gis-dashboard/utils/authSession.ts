/** Cookie sesi bertahan 1 hari. */
export const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24

export const AUTH_USER_STORAGE_KEY = "auth_user"

export function accessTokenExpiryMs(token: string | null | undefined): number | null {
  if (!token) return null
  const part = token.split(".")[1]
  if (!part) return null
  try {
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/")
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4)
    const payload = JSON.parse(atob(padded))
    return typeof payload.exp === "number" ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

export function isAccessTokenExpired(token: string | null | undefined): boolean {
  const expiresAt = accessTokenExpiryMs(token)
  if (!expiresAt) return true
  return Date.now() >= expiresAt
}
