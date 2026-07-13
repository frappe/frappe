declare module "frappe-ui";
declare module "frappe-ui/tailwind/tokens.js";

// Build-time flag: true when apps/frappe/ui (@framework/ui) exists on this bench.
// Injected by vite `define`; gates @framework/ui registration and panel visibility.
declare const __FRAMEWORK_UI_AVAILABLE__: boolean;
