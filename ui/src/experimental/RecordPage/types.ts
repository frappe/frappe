// The Record page customization API: what a script's handlers receive and the
// item schemas the four surfaces accept.
import type { Component } from "vue";
import type { Router } from "vue-router";

/** Where an added or moved item lands; absent or unknown anchors append. */
export type Position = { before?: string; after?: string };

export interface SurfaceItem {
	name: string;
	label?: string;
	icon?: string;
	[key: string]: any;
}

export interface QuickAction extends SurfaceItem {
	label: string;
	description?: string;
	run?: (page: RecordPageApi) => any;
}

export interface HeaderAction extends SurfaceItem {
	label: string;
	/** The menu band this action joins; omitted means `actions`. */
	group?: string;
	run?: (page: RecordPageApi) => any;
}

export interface TabCreateAction {
	label: string;
	icon: string;
	run: (page: RecordPageApi) => any;
}

export interface TabItem extends SurfaceItem {
	label: string;
	component?: Component;
	props?: Record<string, any>;
	/** Joins the composer's `+` menu while this tab is on the strip. */
	create?: TabCreateAction;
}

export interface PanelSectionItem extends SurfaceItem {
	component?: Component;
	props?: Record<string, any>;
	opened?: boolean;
}

export interface SurfaceVerbs<Item extends SurfaceItem = SurfaceItem> {
	add(item: Item, position?: Position): void;
	hide(name: string): void;
	show(name: string): void;
	update(name: string, patch: Partial<Item>): void;
	move(name: string, position: Position): void;
	has(name: string): boolean;
	order(names: string[]): void;
}

export interface PageToast {
	success(message: string): void;
	error(message: string): void;
}

/** The curated object every handler mutates — a script's whole capability surface. */
export interface RecordPageApi {
	doctype: string;
	docname: string;
	doc: Record<string, any>;
	meta: Record<string, any> | null;
	perms: Record<string, any>;
	isDirty: boolean;
	quickActions: SurfaceVerbs<QuickAction>;
	headerActions: SurfaceVerbs<HeaderAction>;
	tabs: SurfaceVerbs<TabItem>;
	panelSections: SurfaceVerbs<PanelSectionItem>;
	save(): Promise<void>;
	reload(): Promise<void>;
	refresh(): Promise<void>;
	toast: PageToast;
	call(method: string, params?: Record<string, any>): Promise<any>;
	router: Router;
}

export type Handler = (page: RecordPageApi) => any;

/** What a script evaluates to: named event handlers, each receiving `page`. */
export type RecordPageHandlers = Record<string, Handler>;
