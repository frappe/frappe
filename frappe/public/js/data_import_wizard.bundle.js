import DataImportWizardApp from "./data_import_wizard/DataImportWizardApp.js";

// Vue wizard on the Data Import form view. UI chrome follows ui/CLAUDE.md:
// frappe-ui where the desk bundle ships it; documented fallbacks otherwise.
frappe.provide("frappe.ui");
frappe.ui.DataImportWizard = DataImportWizardApp;

export default DataImportWizardApp;
