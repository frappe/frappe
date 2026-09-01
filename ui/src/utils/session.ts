/**
 * The signed-in user's id, read from the `user_id` cookie the Frappe backend
 * sets. `null` for guests.
 */
export function sessionUser(): string | null {
  let cookies = new URLSearchParams(document.cookie.split("; ").join("&"));
  let _sessionUser = cookies.get("user_id");
  if (_sessionUser === "Guest") {
    return null;
  }
  return _sessionUser;
}
