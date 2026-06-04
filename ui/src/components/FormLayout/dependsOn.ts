/**
 * App-agnostic evaluator for Frappe conditional expressions (`depends_on`,
 * `mandatory_depends_on`, `read_only_depends_on`).
 *
 * Ports the *intent* of CRM's `evaluateDependsOnValue`
 * (`crm/.../utils/expressions.js`) — no CRM import. Expressions originate from
 * **trusted doctype meta**, exactly as Frappe desk evaluates them, so `new
 * Function` is acceptable here; no user input is evaluated.
 *
 * Supported forms (meta only ever gives strings):
 * - empty / undefined → `true` (no condition);
 * - `eval:<js>` → run `<js>` with `{ doc }` in scope, **fail-open** to `true`
 *   on throw (never hide a field because its condition errored);
 * - bare fieldname → truthiness of `doc[fieldname]` (arrays → non-empty).
 */

function _eval(code: string, doc: Record<string, any>): any {
  return new Function('doc', `let out = ${code}; return out`)(doc)
}

export function evaluateDependsOn(
  expression: string | undefined,
  doc: Record<string, any>,
): boolean {
  if (!expression) return true
  if (expression.startsWith('eval:')) {
    try {
      return Boolean(_eval(expression.slice(5), doc))
    } catch {
      return true
    }
  }
  const value = doc?.[expression]
  return Array.isArray(value) ? value.length > 0 : Boolean(value)
}
