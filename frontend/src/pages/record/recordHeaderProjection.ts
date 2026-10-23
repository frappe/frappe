// The record header row as the page draws it: three top-level controls on the right, the rest in `⋯`.
import { projectHeader, type HeaderItem } from "@/recordPage";
import type { ResolvedItem } from "@/recordPage/surface";

const HEADER_BUDGET = 3;
// Save keeps its slot whatever a script adds; it is the only pinned control.
const PINNED_CONTROLS = ["save"];

export function projectRecordHeader(resolved: ResolvedItem<HeaderItem>[]) {
	return projectHeader(resolved, HEADER_BUDGET, PINNED_CONTROLS);
}
