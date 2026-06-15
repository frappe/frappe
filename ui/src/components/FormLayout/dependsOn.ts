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
 * - `eval:<js>` → run `<js>` with `{ doc, parent }` in scope, **fail-open** to
 *   `true` on throw (never hide a field because its condition errored);
 * - bare fieldname → truthiness of `doc[fieldname]` (arrays → non-empty).
 *
 * `doc` is the **local** record; `parent` is the enclosing doc, so a child-table
 * row's expression can reach a parent field via `parent.x` — exactly as Frappe
 * desk scopes it (`frappe.utils.eval(expr, { doc, parent })` in
 * `grid_row.js` / `layout.js`, where `doc = this.doc` and
 * `parent = this.frm.doc`). The two are **separate names**, never merged:
 * `doc.x` always means the row, `parent.x` always the parent. At the top level
 * desk sets `parent === doc`, so `parent` defaults to `doc` here too. The bare
 * fieldname form reads `doc` only, matching desk's `doc[expression]`.
 */

function _eval(
  code: string,
  doc: Record<string, any>,
  parent: Record<string, any>
): any {
  return new Function("doc", "parent", `let out = ${code}; return out`)(
    doc,
    parent
  );
}

export function evaluateDependsOn(
  expression: string | undefined,
  doc: Record<string, any>,
  parent: Record<string, any> = doc
): boolean {
  if (!expression) return true;
  if (expression.startsWith("eval:")) {
    try {
      return Boolean(_eval(expression.slice(5), doc, parent));
    } catch {
      return true;
    }
  }
  const value = doc?.[expression];
  return Array.isArray(value) ? value.length > 0 : Boolean(value);
}
