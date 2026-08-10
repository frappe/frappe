import { parseFilters, serializeFilters } from "../../components/Filter/filters";
import {
  fetchFields,
  parseColumns,
  serializeColumns,
} from "../../components/ColumnSettings/columns";
import { parseOrderBy, serializeOrderBy } from "../../components/SortBy/orderBy";
import type { ListViewSnapshot } from "../../components/ListView/useListView";
import type { FilterField } from "../../components/Filter/types";
import type { WireFilters } from "../../components/Filter/filters";
import type { WireColumn } from "../../components/ColumnSettings/types";
import type { RawMetaField } from "../../components/FormLayout/types";
import type { SavedView } from "./types";

export interface SavedViewState {
  filters?: string;
  order_by?: string;
  columns?: string;
  rows?: string;
}

export function toWire(
  snapshot: Partial<ListViewSnapshot>,
  fields: RawMetaField[]
): SavedViewState {
  const wire: SavedViewState = {};

  if (snapshot.filters)
    wire.filters = JSON.stringify(serializeFilters(snapshot.filters));

  if (snapshot.sort) wire.order_by = serializeOrderBy(snapshot.sort);

  if (snapshot.columns) {
    const columns = serializeColumns(snapshot.columns, fields);
    wire.columns = JSON.stringify(columns);
    wire.rows = JSON.stringify(fetchFields(columns));
  }

  return wire;
}

export function toSnapshot(
  view: SavedView,
  fields: FilterField[]
): Partial<ListViewSnapshot> {
  const snapshot: Partial<ListViewSnapshot> = {};

  const filters = parseJson<WireFilters>(view.filters);
  if (filters) snapshot.filters = parseFilters(fields, filters);

  const columns = parseJson<WireColumn[]>(view.columns);
  if (columns) snapshot.columns = parseColumns(columns);

  if (view.order_by?.trim()) snapshot.sort = parseOrderBy(view.order_by);

  return snapshot;
}

export function viewIdFromPath(path: string): string | null {
  const match = /\/view\/([^/?#]+)/.exec(path);
  return match ? decodeURIComponent(match[1]) : null;
}

function parseJson<T>(value: unknown): T | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") return value as T;
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}
