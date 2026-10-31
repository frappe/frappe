// The Record page customization API: what a script's handlers receive and the
// item schemas the four surfaces accept.
import type { Component } from "vue";
import type { BaseActivity, VisibleTypes } from "@framework/ui/ActivityTimeline";
import type { FieldAccess } from "@framework/ui/useDocPermissions";
import type { ActFields } from "@/acts/dispatcher";
import { ACT_KEYS } from "@/pageEngine/types";
import type {
  HeaderItem as PageHeaderItem,
  PageApi,
  SurfaceItem,
  SurfaceVerbs,
} from "@/pageEngine/types";

export {
  ACT_KEYS,
  BODY_ITEM_KEYS,
  FRAME_ITEM_KEYS,
  HEADER_ITEM_KEYS,
} from "@/pageEngine/types";
export type {
  BodyItem,
  FrameItem,
  HeaderZone,
  PageDialog,
  PageDialogAction,
  PageDialogActionContext,
  PageDialogColumn,
  PageDialogConfirmAction,
  PageDialogConfirmOptions,
  PageDialogControl,
  PageDialogDangerOptions,
  PageDialogField,
  PageDialogFormOptions,
  PageDialogOpenOptions,
  PageDialogSection,
  PageDialogTab,
  PageToast,
  Position,
  SurfaceItem,
  SurfaceVerbs,
} from "@/pageEngine/types";

/** One item of the header row; its `run` receives the record's `page`. */
export type HeaderItem = PageHeaderItem<RecordPageApi>;

/** The fields an item that has `run` carries as an act; `run` receives the argument's value. */
export type PageActFields = ActFields<RecordPageApi>;

export interface QuickAction extends SurfaceItem, PageActFields {
  label: string;
  description?: string;
  run?: (page: RecordPageApi, value?: any) => any;
}

// Each item type's keys as a list beside it: a key outside the list is dropped with a dev
// warning, so a key a component starts reading is added here, or scripts never see it.
export const QUICK_ACTION_KEYS: readonly string[] = [
  "name",
  "label",
  "icon",
  "description",
  "run",
  ...ACT_KEYS,
];

/** A tab's entry in the composer's `+` menu; its act is `tabs.<name>`. */
export interface TabCreateAction extends PageActFields {
  name: string;
  label: string;
  icon: string;
  run: (page: RecordPageApi, value?: any) => any;
}

export interface TabItem extends SurfaceItem {
  label: string;
  component?: Component;
  props?: Record<string, any>;
  /** Joins the composer's `+` menu while this tab is on the strip. */
  create?: TabCreateAction;
  /** Draws the composer band at the foot of this tab, as Activity and Emails do. */
  composer?: boolean;
}

export const TAB_ITEM_KEYS: readonly string[] = [
  "name",
  "label",
  "icon",
  "component",
  "props",
  "create",
  "composer",
];

/** One item of the panel's single list; a `label` gives it a header, a layout name renders its fields. */
export interface PanelSectionItem extends SurfaceItem {
  component?: Component;
  props?: Record<string, any>;
  /** Whether a section with a header starts open; meaningless without one. */
  opened?: boolean;
}

export const PANEL_SECTION_KEYS: readonly string[] = [
  "name",
  "label",
  "icon",
  "component",
  "props",
  "opened",
];

/** One item of the Details form: a section the layout stores, or a part a script adds. */
export interface FormItem extends SurfaceItem {
  /** Draws the part; absent on a section, whose fields the layout draws. */
  component?: Component;
  props?: Record<string, any>;
}

export const FORM_ITEM_KEYS: readonly string[] = ["name", "label", "component", "props"];

/** A script's own row in the feed or the files list; its timestamp places it among the server's rows. */
export interface FeedItem extends SurfaceItem {
  /** `YYYY-MM-DD HH:mm:ss`, as the server writes one. */
  timestamp: string;
  component: Component;
  props?: Record<string, any>;
}

export const FEED_ITEM_KEYS: readonly string[] = ["name", "timestamp", "component", "props"];

/** One row the Activity tab has loaded, as the activity store holds it. */
export type ActivityRow = BaseActivity<string, unknown>;

/** A server row as `page.activity.items` hands it: the row's `key` is its `name`. */
export interface ActivityItem {
  name: string;
  type: string;
  timestamp?: string;
  author?: ActivityRow["author"];
  data: unknown;
  /** Posted, and not yet answered by the server. */
  pending?: boolean;
}

/** One row of the record read's `attachments` part; `name` is the File's name. */
export interface FileRow {
  name: string;
  file_name: string;
  file_url: string;
  file_type?: string;
  file_size?: number;
  is_private: 0 | 1;
  attached_to_field?: string | null;
  folder?: string;
  creation: string;
  owner: string;
}

/** A list time orders: the server's rows read-only, a script's own rows added between them. */
export interface PageFeedList<Row> {
  /** Oldest first, a script's rows included; read-only. */
  readonly items: ReadonlyArray<Row | FeedItem>;
  add(item: FeedItem | FeedItem[]): void;
  /** Takes out a script's own row; a server row stays. */
  remove(name: string): void;
  /** True for a loaded server row and for a script's own row. */
  has(name: string): boolean;
  /** Reads the server's rows again; a script's rows stay. */
  reload(): Promise<void>;
}

/** The Activity tab's list. */
export interface PageActivity extends PageFeedList<ActivityItem> {
  /** Opens the Activity tab and scrolls to the row, loading older rows until it is found. */
  scrollTo(key: string): void;
  /** The types the Activity tab shows, as `ActivityTimeline` names them; unset shows every type. */
  types(list: VisibleTypes): void;
}

export type PageFiles = PageFeedList<FileRow>;

/** One writer of the composer: the built-in `comment`, or a script's own. */
export interface WriterItem extends SurfaceItem {
  label: string;
  icon?: string;
  /** Draws the writer's body; it receives `{ ...props, page, close }` and posts on its own. */
  component?: Component;
  props?: Record<string, any>;
}

export const WRITER_ITEM_KEYS: readonly string[] = ["name", "label", "icon", "component", "props"];

/** Where the open writer's card sits: in the band at the foot of the tab, or floating over the page. */
export type ComposerWindow = "docked" | "floating";

export interface ComposerOpenOptions {
  /** Seeds the writer's draft; a draft already in memory wins. */
  draft?: Record<string, unknown>;
  /** Places the card for this open only; unset, the reader's own choice does. */
  window?: ComposerWindow;
}

/** The writers the band at the foot of a composer tab offers, and the one open in it. */
export interface PageComposer extends SurfaceVerbs<WriterItem> {
  /** Moves the reader to a tab that draws the band, then opens the writer; held in a replay. */
  open(name: string, options?: ComposerOpenOptions): void;
  close(): void;
  /** The open writer's name, or `''`. */
  readonly active: string;
  /** The open card's place, else the reader's own choice; setting it moves an open card only. */
  window: ComposerWindow;
}

/** The panel surface also opens and shuts a section for the reader. */
export interface PanelSectionsApi extends SurfaceVerbs<PanelSectionItem> {
  /**
   * Opens a section that has a header, on `TabsApi.activate`'s terms: resolved at the
   * call, delivered when the replay commits. In-page state, never an address.
   */
  open(name: string): void;
  close(name: string): void;
}

/** The tabs surface also tells a handler which tab the reader is on. */
export interface TabsApi extends SurfaceVerbs<TabItem> {
  readonly active: string;
  /**
   * Moves the reader to a tab on this strip. Resolved at the call, never queued;
   * `active` reads the new tab at once, or after the commit when called in a replay.
   */
  activate(name: string): void;
}

/**
 * What a script may override on one of the record's fields, spelled as a
 * DocField spells it. Closed: a key not named here is dropped with a dev warning.
 */
export interface PageFieldPatch {
  // `0 | 1` alongside the boolean: a DocField spells these as ints.
  hidden?: boolean | 0 | 1;
  read_only?: boolean | 0 | 1;
  reqd?: boolean | 0 | 1;
  label?: string;
  placeholder?: string;
  description?: string;
  /** Link target, or a `Select`'s newline-separated choices. */
  options?: string;
  /** Search filters for a `Link` field. v1 spells it this way; so do we. */
  link_filters?: Record<string, unknown>;
  /** Decimal places for a numeric field. */
  precision?: number | string;
  /** A Table field's grid offers no way to add a row. */
  cannot_add_rows?: boolean | 0 | 1;
  /** A Table field's grid offers no way to delete a row. */
  cannot_delete_rows?: boolean | 0 | 1;
  /** Renders this component in the field's slot instead of the default one. */
  component?: Component;
  /** Props bound onto whichever component renders the field. */
  props?: Record<string, any>;
}

/** What `get` hands back: the keys `update` writes, resolved, plus the two that identify the field. */
export interface PageField extends PageFieldPatch {
  fieldname: string;
  fieldtype: string;
  // Resolved, so these are answered as booleans however they were written.
  hidden?: boolean;
  read_only?: boolean;
  reqd?: boolean;
  cannot_add_rows?: boolean;
  cannot_delete_rows?: boolean;
}

/**
 * The fields surface: a render-time overlay on fields authored elsewhere, cleared
 * before every replay. No `add`, `move` or `order`; ordering is the Form Layout's job.
 */
/** A field is named by its fieldname, a table's column by `<table>.<column>`. */
export interface PageFields {
  hide(fieldname: string): void;
  show(fieldname: string): void;
  update(fieldname: string, patch: PageFieldPatch): void;
  /** Whether the doctype has this field at all. */
  has(fieldname: string): boolean;
  /** The field as it currently resolves — post-override, post-`depends_on`. */
  get(fieldname: string): PageField | null;
  /** Moves the reader to the field: tab, scroll, cursor; read-only gets no cursor, unknown or hidden warns. */
  focus(fieldname: string): void;
  /** Marks the field until it is edited, a save starts or a replay runs; `throw` the Error it returns to veto a save. */
  setError(fieldname: string, message: string): Error;
  clearError(fieldname: string): void;
}

/** What a script may override on one of the Form Layout's tabs. */
export interface PageFormTabPatch {
  label?: string;
}

/** What `page.form.tabs.get()` hands back: the tab as the strip resolves it. */
export interface PageFormTab {
  /** What the author wrote, if anything; the address is `identity`. */
  name?: string;
  identity: string;
  label: string;
  /** Resolved: `depends_on` and this surface's own ops both folded in. */
  hidden: boolean;
}

/**
 * The Form Layout's own tab strip, inside the Details form. A tab is addressed
 * by its identity (`name`, else the slugified label, else its position), never by label.
 */
export interface PageFormTabs {
  hide(identity: string): void;
  show(identity: string): void;
  update(identity: string, patch: PageFormTabPatch): void;
  /** Whether the layout carries this tab at all, on screen or not. */
  has(identity: string): boolean;
  /** The tab as it currently resolves — post-override, post-`depends_on`. */
  get(identity: string): PageFormTab | null;
  /** The identity of the tab the reader is on, or `''` outside the form; not a name. */
  readonly active: string;
  /** Moves the reader to a tab of the form, on `TabsApi.activate`'s terms except `active`, which updates once the form has moved. */
  activate(identity: string): void;
  /** Hides every tab present at the call; a later `show(identity)` brings one back. */
  clear(): void;
}

/** The Details form as one list: its sections and a script's parts, with the strip inside it. */
export interface PageForm extends SurfaceVerbs<FormItem> {
  tabs: PageFormTabs;
}

/**
 * A child row as a script addresses it: re-finds its row on every access, with
 * fields read and written bare. Access to a removed row throws.
 */
export interface PageRow {
  /** Fires this row's handler for one child field: `row.trigger('rate')` dispatches `'products.rate'`. */
  trigger(fieldname: string): Promise<void>;
  /** Marks one of this row's cells, on `page.fields.setError`'s terms. */
  setError(fieldname: string, message: string): Error;
  clearError(fieldname: string): void;
  [fieldname: string]: any;
}

/** The curated object every handler mutates — a script's whole capability surface. */
export interface RecordPageApi extends PageApi {
  /** The app the reader is in, such as `crm` on `/apps/crm`; read-only. */
  readonly app: string;
  docname: string;
  doc: Record<string, any>;
  /** The document as the server last showed it; read-only, `page.doc` is the draft. */
  saved: Record<string, any>;
  /** What this user may do with a field, by permlevel; an unknown one is `none`. */
  fieldAccess(fieldname: string): FieldAccess;
  isDirty: boolean;
  /** True until the first save; the record has no name and `page.save()` inserts it. */
  isNew: boolean;
  quickActions: SurfaceVerbs<QuickAction>;
  header: SurfaceVerbs<HeaderItem>;
  tabs: TabsApi;
  panelSections: PanelSectionsApi;
  fields: PageFields;
  /** The Details form: the layout's sections and a script's parts as one list, and its tab strip. */
  form: PageForm;
  /** The Activity tab's rows, oldest first. */
  activity: PageActivity;
  /** The record's attachments, oldest first. */
  files: PageFiles;
  /** The writers of the band at the foot of the Activity and Emails tabs. */
  composer: PageComposer;
  /** The child table's rows as handles, in array order; a non-table fieldname answers empty. */
  rows(parentfield: string): PageRow[];
  save(): Promise<void>;
  /** Saves a dirty draft, renames the record and opens it at its new name; `null` when refused or not on a saved record. */
  rename(name: string, options?: { merge?: boolean }): Promise<string | null>;
  reload(): Promise<void>;
  /** Opens Create for a doctype; the saved record, or `null` when nothing was saved in the dialog. */
  create(
    doctype: string,
    options?: { values?: Record<string, any> },
  ): Promise<Record<string, any> | null>;
  /** Opens the settings dialog at `#settings/<prefix>/<pane>/<block>`; each segment is optional. */
  openSettings(prefix?: string, pane?: string, block?: string): void;
  /** Runs an act by its full name, `<surface>.<item>`, in a hold; rejects with `ActDenied` or the act's error. */
  run(name: string, value?: unknown): Promise<unknown>;
}

export type { FieldAccess, VisibleTypes };

/** What `onPost` receives: the key of the row the built-in writer posted. */
export interface PostedRow {
  name: string;
}

/**
 * A top-level key receives `(page)`, and `onPost` `(page, { name })`; one nested under a
 * child table receives `(page, row)`, except `onRemove`, whose row is gone.
 */
export type Handler = HandlerMethod["handle"];

// A method's parameters check both ways, so a handler may type the argument its event passes.
interface HandlerMethod {
  handle(page: RecordPageApi, row?: PageRow | PostedRow): any;
}

/** What an author writes: event handlers, plus a block nested under a child table's fieldname. */
export type AuthoredHandlers = Record<
  string,
  Handler | Record<string, Handler>
>;

/** What the engine dispatches against: nested blocks flattened onto dotted keys. */
export type RecordPageHandlers = Record<string, Handler>;
