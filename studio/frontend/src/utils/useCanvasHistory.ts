import { ref, Ref } from "vue";
import Block from "@/runtime/utils/block";
import { generateId } from "@/utils/helpers";
import { getBlockString, getBlockInstance } from "@/runtime/utils/serializer"
import { debounceFilter, pausableFilter, watchIgnorable } from "@vueuse/core";

type CanvasState = {
	block: string;
	selectedBlockIds: Set<string>;
};
export type PauseId = string & { __brand: "PauseId" };

const CAPACITY = 500;
const DEBOUNCE_DELAY = 100;
// Each record is a complete copy of the page. For a large page, the history reaches this
// limit before it has CAPACITY records.
const MAX_BYTES = 20 * 1024 * 1024;
const MIN_ENTRIES = 10;

export function useCanvasHistory(source: Ref<Block>, selectedBlockIds: Ref<Set<string>>) {
	const undoStack = ref([]) as Ref<CanvasState[]>;
	const redoStack = ref([]) as Ref<CanvasState[]>;
	const last = ref(createHistoryRecord());
	const pauseIdSet = new Set<PauseId>();

	const {
		eventFilter: blockWatcherFilter,
		pause: pauseBlockWatcher,
		resume: resumeBlockWatcher,
		isActive: isTracking,
	} = pausableFilter(debounceFilter(DEBOUNCE_DELAY));

	const {
		eventFilter: selectionWatherFilter,
		pause: pauseSelectionWatcher,
		resume: resumeSelectionWatcher,
	} = pausableFilter();

	const {
		ignoreUpdates: ignoreBlockUpdates,
		ignorePrevAsyncUpdates: ignorePrevAsyncBlockUpdates,
		stop: stopBlockWatcher,
	} = watchIgnorable(source, commit, {
		deep: true,
		eventFilter: blockWatcherFilter,
	});

	const {
		ignoreUpdates: ignoreSelectedBlockUpdates,
		ignorePrevAsyncUpdates: ignorePrevSelectedBlockUpdates,
		stop: stopSelectedBlockUpdates,
	} = watchIgnorable(selectedBlockIds, updateSelections, {
		deep: true,
		eventFilter: selectionWatherFilter,
	});

	// tracks tree changes since the last markClean() — undoing back to the exact
	// saved state still counts as dirty (conservative, like a text editor)
	const dirty = ref(false);

	function commit() {
		const previousRecord = last.value;
		const nextRecord = createHistoryRecord();
		// Resume and the watcher can both record the same tree state.
		// Skip the duplicate so Undo takes only one step.
		if (nextRecord.block === previousRecord.block) return;
		dirty.value = true;
		undoStack.value.unshift(previousRecord);
		last.value = nextRecord;
		trim(undoStack.value);
		if (redoStack.value.length) {
			redoStack.value.splice(0, redoStack.value.length);
		}
	}

	function trim(stack: CanvasState[]) {
		if (stack.length > CAPACITY) {
			stack.splice(CAPACITY, Number.POSITIVE_INFINITY);
		}
		let bytes = 0;
		for (let i = 0; i < stack.length; i++) {
			bytes += stack[i].block.length;
			if (bytes > MAX_BYTES && i >= MIN_ENTRIES) {
				stack.splice(i + 1, Number.POSITIVE_INFINITY);
				return;
			}
		}
	}

	function updateSelections() {
		last.value.selectedBlockIds = new Set(selectedBlockIds.value);
	}

	function createHistoryRecord() {
		return {
			block: getBlockString(source.value),
			selectedBlockIds: selectedBlockIds.value,
		};
	}

	function setSource(value: CanvasState) {
		ignorePrevAsyncBlockUpdates();
		ignoreBlockUpdates(() => {
			source.value = getBlockInstance(value.block);
		});
		ignorePrevSelectedBlockUpdates();
		ignoreSelectedBlockUpdates(() => {
			selectedBlockIds.value = new Set(value.selectedBlockIds);
		});
		last.value = value;
	}

	function undo() {
		const state = undoStack.value.shift();
		if (state) {
			redoStack.value.unshift(last.value);
			trim(redoStack.value);
			setSource(state);
			dirty.value = true;
		}
	}

	function canUndo() {
		return undoStack.value.length > 0;
	}

	function redo() {
		const state = redoStack.value.shift();
		if (state) {
			undoStack.value.unshift(last.value);
			trim(undoStack.value);
			setSource(state);
			dirty.value = true;
		}
	}

	function canRedo() {
		return redoStack.value.length > 0;
	}

	function stop() {
		stopBlockWatcher();
		stopSelectedBlockUpdates();
	}

	const clear = () => {
		undoStack.value.splice(0, undoStack.value.length);
		redoStack.value.splice(0, redoStack.value.length);
	};

	function dispose() {
		stop();
		clear();
	}

	function pause() {
		pauseBlockWatcher();
		pauseSelectionWatcher();
		const pauseId = generateId() as PauseId;
		pauseIdSet.add(pauseId);
		return pauseId as PauseId;
	}

	function resumeTracking() {
		resumeBlockWatcher();
		resumeSelectionWatcher();
	}

	function resume(pauseId?: PauseId, commitNow?: boolean, force?: boolean) {
		if (pauseId && pauseIdSet.has(pauseId)) {
			pauseIdSet.delete(pauseId);
		} else if (!force) {
			return;
		}
		if (pauseIdSet.size && !force) {
			return;
		}
		pauseIdSet.clear();
		resumeTracking();
		if (commitNow) commit();
	}

	function batch(callback: () => void) {
		const pauseId = pause();
		callback();
		resume(pauseId, true);
	}

	function isDirty() {
		return dirty.value;
	}

	function markClean() {
		dirty.value = false;
	}

	return {
		undo,
		redo,
		pause,
		resume,
		batch,
		canUndo,
		canRedo,
		isDirty,
		markClean,
		dispose,
		undoStack,
		redoStack,
		isTracking,
	};
}
