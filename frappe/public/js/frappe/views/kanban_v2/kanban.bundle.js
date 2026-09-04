/**
 * Desk bundle entry for the Kanban engine (vanilla JS).
 *
 * esbuild builds this to dist/js/kanban.bundle.<hash>.js and it is loaded
 * on demand via `frappe.require("kanban.bundle.js")`. Exposes the engine on
 * `frappe.kanban_v2`.
 */
import { KanbanVanilla } from "./adapters/vanilla";
import { KanbanCore } from "./core/kanban_core";
import { FrappeDataProvider } from "./providers/frappe_data_provider";
import BulkOperations from "../../list/bulk_operations";

frappe.provide("frappe.kanban_v2");
frappe.kanban_v2.KanbanVanilla = KanbanVanilla;
frappe.kanban_v2.KanbanCore = KanbanCore;
frappe.kanban_v2.FrappeDataProvider = FrappeDataProvider;
frappe.kanban_v2.BulkOperations = BulkOperations;

// Page wrapper and swimlane classes live here so list.bundle.js stays lean.
import "./kanban_page";

export { KanbanVanilla, KanbanCore, FrappeDataProvider };
