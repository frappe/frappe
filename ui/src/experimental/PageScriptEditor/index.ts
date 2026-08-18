// The dialog is the only way in: ticket 30 ruled the standalone admin surface out
// of scope, and the pane and its state were public solely so that surface could
// embed them. Both stay split from the dialog — that seam is where the tests bite.
export { default as PageScriptEditorDialog } from "./PageScriptEditorDialog.vue";
export type { PageScriptDoc } from "./pageScriptApi";
export { SHARED_DEPS, unresolvableImports } from "./importLint";
