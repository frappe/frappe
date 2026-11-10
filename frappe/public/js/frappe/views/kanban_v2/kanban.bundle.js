// Loaded on demand with frappe.require("kanban.bundle.js"); exposes the engine on frappe.kanban_v2.
import { KanbanVanilla } from "./adapters/vanilla";
import { KanbanCore } from "./core/kanban_core";
import { FrappeDataProvider } from "./providers/frappe_data_provider";
import BulkOperations from "../../list/bulk_operations";

frappe.provide("frappe.kanban_v2");
frappe.kanban_v2.KanbanVanilla = KanbanVanilla;
frappe.kanban_v2.KanbanCore = KanbanCore;
frappe.kanban_v2.FrappeDataProvider = FrappeDataProvider;
frappe.kanban_v2.BulkOperations = BulkOperations;

// page and swimlane classes live here so list.bundle.js stays lean
import "./kanban_page";

export { KanbanVanilla, KanbanCore, FrappeDataProvider };
