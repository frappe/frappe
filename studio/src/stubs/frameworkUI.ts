// Stub for @framework/ui on frappe branches that don't ship the `ui` package.
//
// globals.ts imports @framework/ui components inside `if (__FRAMEWORK_UI_AVAILABLE__)`
// (false on such branches). Production builds DCE that dead branch away, but the Vite
// dev server does NOT tree-shake before import-analysis — it still tries to resolve
// every `import("@framework/ui/...")` specifier and errors when the package is absent.
//
// When unavailable, vite.config aliases `@framework/ui/*` here so those specifiers
// resolve. This is never executed at runtime (the branch is dead), so the export only
// needs to exist — it's never mounted.
export default {}
