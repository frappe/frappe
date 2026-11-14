// Desk's Vue, shared with prebuilt app bundles that mark `vue` as external
// (e.g. frappe-ui's <frappe-mobile-nav>) so they don't ship their own copy.
// Not in the default bundles: mobile_nav.bundle.js loads it on demand.
//
// Only the names those bundles call, so the rest of Vue is tree-shaken out of
// mobile_nav.bundle.js. A rebuilt element that calls a name missing here fails as it
// loads; add the name here when that happens.
import {
	computed,
	createBlock,
	createCommentVNode,
	createElementBlock,
	createElementVNode,
	defineComponent,
	defineCustomElement,
	getCurrentInstance,
	mergeProps,
	normalizeClass,
	openBlock,
	ref,
	renderSlot,
	resolveDynamicComponent,
	toDisplayString,
	withCtx,
} from "vue";

frappe.Vue = {
	computed,
	createBlock,
	createCommentVNode,
	createElementBlock,
	createElementVNode,
	defineComponent,
	defineCustomElement,
	getCurrentInstance,
	mergeProps,
	normalizeClass,
	openBlock,
	ref,
	renderSlot,
	resolveDynamicComponent,
	toDisplayString,
	withCtx,
};
