import { ref, Ref } from "vue";
import Block from "@/utils/block";
import { generateId, getBlockInstance, getBlockString } from "@/utils/helpers";
import { debounceFilter, pausableFilter, watchIgnorable } from "@vueuse/core";

type CanvasState = {
	block: string;
	selectedBlockIds: Set<string>;
};
type PauseId = string & { __brand: "PauseId" };

const CAPACITY = 500;
const DEBOUNCE_DELAY = 100;

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

	function commit() {
		undoStack.value.unshift(last.value);
		last.value = createHistoryRecord();
		if (undoStack.value.length > CAPACITY) {
			undoStack.value.splice(CAPACITY, Number.POSITIVE_INFINITY);
		}
		if (redoStack.value.length) {
			redoStack.value.splice(0, redoStack.value.length);
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
			setSource(state);
		}
	}

	function canUndo() {
		return undoStack.value.length > 0;
	}

	function redo() {
		const state = redoStack.value.shift();
		if (state) {
			undoStack.value.unshift(last.value);
			setSource(state);
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

	return {
		undo,
		redo,
		pause,
		resume,
		batch,
		canUndo,
		canRedo,
		dispose,
		undoStack,
		redoStack,
		isTracking,
	};
}
