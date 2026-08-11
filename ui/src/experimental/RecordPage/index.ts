export { registerRecordPage, registrationsFor, resetRegistry, ALL_DOCTYPES } from "./registry";
export { createRecordPage } from "./createRecordPage";
export type { RecordPageController, RecordPageHost } from "./createRecordPage";
export { Surface, BUILTIN } from "./surface";
export type { ResolvedItem } from "./surface";
export { loadFrontendExtensions } from "./loader";
export { withRegisteringSource, HOST_SOURCE } from "./context";
export type {
	Handler,
	HeaderAction,
	PanelSectionItem,
	Position,
	QuickAction,
	RecordPageApi,
	RecordPageHandlers,
	SurfaceItem,
	SurfaceVerbs,
	TabCreateAction,
	TabItem,
} from "./types";
