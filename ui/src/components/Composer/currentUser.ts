/**
 * Default avatar/label for the collapsed trigger bar, read from
 * `frappe.boot.user_info` for the signed-in user — no network call, no host store.
 * Read per call, not cached at import: `frappe.boot` may not be populated yet when
 * this module first loads (same caveat as FileUpload/useFileUpload.ts's chunkSize).
 */
export function currentUserInfo(): { image?: string; fullname?: string } {
  const frappeGlobal = (globalThis as any).frappe;
  const userId = frappeGlobal?.session?.user;
  return (userId && frappeGlobal?.boot?.user_info?.[userId]) || {};
}
