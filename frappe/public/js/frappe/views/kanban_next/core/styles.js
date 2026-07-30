/**
 * Minimal injected styles for Kanban states and behaviors.
 * Layout/spacing/color mostly come from utility classes in kanban_core.js.
 * Keep height/overflow here — flex children need min-height:0 or the column
 * body grows with cards and never scrolls.
 */
const STYLE_ID = "kn-base-styles";

const CSS = `
.kn-board {
	--kn-accent: var(--blue-500, #2490ef);
	height: 100%;
	overflow-y: hidden;
}
.kn-column {
	/* Fixed column width — cards fill it. 320px fits label+value stacks
	   without feeling sparse; content truncates inside, never grows the card. */
	flex: 0 0 320px;
	max-height: 100%;
	min-height: 0;
}
/* The column body is the board's only scrolling surface, and its scrollbar is
   painted over the body's inline padding (macOS reserves no gutter). Two things
   have to be tamed:
   1. scrollbar.scss gives every scrollbar a filled track, which shows up here as
      a grey rail down the whole column as soon as the browser reveals the bar —
      so this track is blank and only the thumb shows.
   2. The thumb must stay clear of the cards, which the body's 16px end padding
      takes care of.
   Chrome ignores ::-webkit-scrollbar-* once scrollbar-color is set (and the desk
   sets it on *), so the standard properties come first and the pseudo-elements
   are the fallback for Safari and older Chrome. */
.kn-column-body {
	min-height: 0;
	overflow-y: auto;
	overflow-x: hidden;
	scrollbar-width: thin;
	scrollbar-color: var(--scrollbar-thumb-color) transparent;
}
.kn-column-body::-webkit-scrollbar {
	width: 10px !important;
	background: transparent;
}
.kn-column-body::-webkit-scrollbar-track,
.kn-column-body::-webkit-scrollbar-track-piece,
.kn-column-body::-webkit-scrollbar-corner {
	background: transparent;
}
.kn-column-body::-webkit-scrollbar-thumb {
	background: var(--scrollbar-thumb-color);
	background-clip: content-box;
	border: 2px solid transparent;
	border-radius: var(--radius-full);
}
/* Dark mode: the column fill matches the card fill, so outline the panel
   instead of filling it (utilities have no dark variant). */
[data-theme="dark"] .kn-column {
	background: transparent;
	border: 1px solid var(--outline-gray-1, #333);
}
.kn-spacer { width: 100%; flex: 0 0 auto; pointer-events: none; }
/* Cards sit flat on the column and lift only on hover. */
.kn-card { cursor: grab; transition: box-shadow 0.1s ease, border-color 0.1s ease; }
.kn-card:active { cursor: grabbing; }
/* The card wears the .border utility, which is !important — every state that
   repaints the border has to shout back. Selected cards keep their own colour. */
.kn-card:not(.kn-selected):hover { border-color: var(--outline-gray-3, #cbd0d6) !important; box-shadow: var(--elevation-sm); }
.kn-card:focus-visible { outline: 2px solid var(--kn-accent); outline-offset: 1px; }
/* While lifted, the card reads as the empty slot it left behind. */
.kn-card.kn-dragging {
	opacity: 0.5;
	border-style: dashed !important;
	background: var(--surface-gray-2);
	box-shadow: none;
}
.kn-card.kn-selected { outline: 2px solid var(--kn-accent); outline-offset: -1px; background: var(--bg-blue); }
.kn-card.kn-drop-before { box-shadow: inset 0 3px 0 0 var(--kn-accent); }
.kn-card.kn-drop-after { box-shadow: inset 0 -3px 0 0 var(--kn-accent); }
.kn-empty { min-height: 24px; }
.kn-add-card-input { box-sizing: border-box; border-color: var(--kn-accent) !important; font: inherit; resize: none; outline: none; }
.kn-board.kn-loading { opacity: 0.6; pointer-events: none; }
.kn-column-header { cursor: grab; user-select: none; }
.kn-column-header.kn-col-dragging { opacity: 0.65; cursor: grabbing; }
.kn-column-header.kn-col-drop-before { box-shadow: inset 3px 0 0 0 var(--kn-accent); }
.kn-column-header.kn-col-drop-after { box-shadow: inset -3px 0 0 0 var(--kn-accent); }
/* Drop the default indicator margin — flex gap on the header meta owns spacing. */
.kn-column-dot.indicator::before { margin: 0; border-radius: 50%; }
`;

let injected = false;

export function injectBaseStyles() {
	if (typeof document === "undefined") return;
	const existing = document.getElementById(STYLE_ID);
	if (existing) {
		// Keep CSS in sync across HMR / soft reloads of this module.
		existing.textContent = CSS;
		injected = true;
		return;
	}
	if (injected) return;
	const style = document.createElement("style");
	style.id = STYLE_ID;
	style.textContent = CSS;
	document.head.appendChild(style);
	injected = true;
}
