/**
 * Desk bundle entry for the Kanban engine (vanilla JS).
 *
 * esbuild builds this to dist/js/kanban_next.bundle.<hash>.js and it is loaded
 * on demand via `frappe.require("kanban_next.bundle.js")`. Exposes the engine on
 * `frappe.kanban_next`.
 */
import { KanbanVanilla } from "./adapters/vanilla";
import { KanbanCore } from "./core/kanban_core";
import { FrappeDataProvider } from "./providers/frappe_data_provider";
import BulkOperations from "../../list/bulk_operations";

frappe.provide("frappe.kanban_next");
frappe.kanban_next.KanbanVanilla = KanbanVanilla;
frappe.kanban_next.KanbanCore = KanbanCore;
frappe.kanban_next.FrappeDataProvider = FrappeDataProvider;
frappe.kanban_next.BulkOperations = BulkOperations;

export { KanbanVanilla, KanbanCore, FrappeDataProvider };
