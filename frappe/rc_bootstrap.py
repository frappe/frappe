# frappe/rc_bootstrap.py
import frappe

# === AJUSTA ESTAS LISTAS A TU GUSTO ===
MY_ROLES = ["Administrador de Empresa", "Vendedor", "Gerente de Ventas", "Gerente de CRM", "Contador"]
SAFE_GUARD_ROLES = {"Administrator", "All", "Guest", "System Manager"}
HIDE_WORKSPACES = ["Build", "Modules", "Users", "Website", "Settings", "Email", "Integrations"]
# ======================================

def run():
    ensure_my_roles()
    disable_every_other_role()
    unassign_disabled_roles_from_users()
    hide_unwanted_workspaces()
    frappe.logger().info("RC bootstrap applied")
    frappe.clear_cache()

def after_install_and_bootstrap():
    """Llama el after_install original del framework y luego aplica tus defaults."""
    from frappe.utils.install import after_install as core_after_install
    core_after_install()   # lo de siempre en Frappe
    run()                  # tus defaults

def ensure_my_roles():
    for role in MY_ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Role", role, "desk_access", 1)

def disable_every_other_role():
    keep = set(MY_ROLES) | SAFE_GUARD_ROLES
    for r in frappe.get_all("Role", pluck="name"):
        if r not in keep:
            frappe.db.set_value("Role", r, {"disabled": 1, "desk_access": 0})

def unassign_disabled_roles_from_users():
    disabled = frappe.get_all("Role", filters={"disabled": 1}, pluck="name")
    if not disabled:
        return
    rows = frappe.get_all("Has Role", filters={"role": ["in", disabled]}, fields=["name"])
    if rows:
        frappe.db.delete("Has Role", {"name": ["in", [r.name for r in rows]]})

def hide_unwanted_workspaces():
    for ws in HIDE_WORKSPACES:
        if frappe.db.exists("Workspace", ws):
            try:
                frappe.db.set_value("Workspace", ws, "is_hidden", 1)
            except Exception:
                try:
                    doc = frappe.get_doc("Workspace", ws)
                    if hasattr(doc, "restrict_to_roles"):
                        doc.set("restrict_to_roles", [])
                        for r in MY_ROLES:
                            doc.append("restrict_to_roles", {"role": r})
                        doc.save(ignore_permissions=True)
                except Exception:
                    pass

