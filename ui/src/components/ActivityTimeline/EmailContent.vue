<template>
	<iframe
		ref="iframeRef"
		:srcdoc="htmlContent"
		sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
		referrerpolicy="no-referrer"
		class="prose-f block h-10 w-full"
		:class="{ 'email-clipped-fade': isClipped }"
		:style="{ maxHeight: `${MAX_CONTENT_HEIGHT}px` }"
	/>
</template>
<!-- sandboxed + CSP: scripts and external resources can't load -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { applyCssToIframe, stripEmailColors, useDataTheme } from "./utils";

const props = defineProps<{
	content: string;
}>();

const MAX_CONTENT_HEIGHT = 500; // in px; if the email content exceeds this, the bottom edge fades to indicate more content is clipped.

const iframeRef = ref<HTMLIFrameElement | null>(null);
const isClipped = ref(false);
const dataTheme = useDataTheme(); // needed for the iframe to inherit the host's theme (dark/light) so the email content matches the rest of the app.

// reactive to content: strip inline colors + fold reply quotes into a CSS-only collapse
const processedContent = computed(() => collapseReplyQuotes(stripEmailColors(props.content)));

// gmail → outlook → generic; only the first kind present is collapsed.
const REPLY_QUOTE_SELECTORS = [
	{ selector: "div.gmail_quote", forGmail: true },
	{ selector: "div#appendonsend", forGmail: false },
	{ selector: "p.reply-to-content", forGmail: false },
];

function collapseReplyQuotes(html: string): string {
	const doc = new DOMParser().parseFromString(html, "text/html");
	for (const { selector, forGmail } of REPLY_QUOTE_SELECTORS) {
		if (!doc.querySelector(selector)) continue;
		doc.querySelectorAll(selector).forEach((el) => collapseQuote(doc, el, forGmail));
		break;
	}
	return doc.body.innerHTML;
}

// wrap the quote in .replied-content: a label + checkbox reveal it via pure CSS, no JS
function collapseQuote(doc: Document, quote: Element, forGmail: boolean) {
	const parent = quote.parentElement;
	if (!parent) return;

	const randomId = Math.random().toString(36).substring(2, 7);

	const wrapper = doc.createElement("div");
	wrapper.classList.add("replied-content");

	const collapseLabel = doc.createElement("label");
	collapseLabel.classList.add("collapse");
	collapseLabel.setAttribute("for", randomId);
	collapseLabel.innerHTML = "...";
	wrapper.appendChild(collapseLabel);

	const collapseInput = doc.createElement("input");
	collapseInput.setAttribute("id", randomId);
	collapseInput.setAttribute("class", "replyCollapser");
	collapseInput.setAttribute("type", "checkbox");
	wrapper.appendChild(collapseInput);

	if (forGmail) {
		// drop Gmail's leading <br>; keep the quote minus gmail_quote so it isn't re-detected
		const prevSibling = quote.previousElementSibling;
		if (prevSibling && prevSibling.tagName === "BR") prevSibling.remove();
		const cloned = quote.cloneNode(true) as Element;
		cloned.classList.remove("gmail_quote");
		wrapper.appendChild(cloned);
	} else {
		// move everything after the marker into the hidden block; nothing after ⇒ leave as-is
		const siblings = Array.from(parent.children);
		const following = siblings.slice(siblings.indexOf(quote) + 1);
		if (following.length === 0) return;

		const hidden = doc.createElement("div");
		hidden.append(...following.map((node) => node.cloneNode(true)));
		wrapper.append(hidden);
		following.forEach((node) => node.remove());
	}

	parent.replaceChild(wrapper, quote);
}

// CSP meta: block scripts + external resource loads
const htmlContent = computed(
	() => `
  <!DOCTYPE html>
  <html>
  <head>
    <meta http-equiv="Content-Security-Policy" content="script-src 'none'; object-src 'none';" />
    <base target="_blank" />
    <style>
      :root {
        --bg-surface-gray-3: #ededed;
        --bg-surface-gray-4: #e2e2e2;
      }
      [data-theme='dark'] {
        --bg-surface-gray-3: #343434;
        --bg-surface-gray-4: #424242;
      }
      .replied-content .collapse {
        margin: 10px 0 10px 0;
        visibility: visible;
        cursor: pointer;
        display: flex;
        font-size: larger;
        font-weight: 700;
        height: 12px;
        line-height: 0.1;
        background: #e8eaed;
        width: 23px;
        justify-content: center;
        border-radius: 5px;
      }
      .replied-content .collapse:hover {
        background: #dadce0;
      }
      .replied-content .collapse + input {
        display: none;
      }
      .replied-content .collapse + input + div {
        display: none;
      }
      .replied-content .collapse + input:checked + div {
        display: block;
      }
      body {
        margin: 0;
      }
      .email-content {
        word-break: break-word;
        /* flow-root contains child margins; padding-top adds breathing room that scrolls away */
        display: flow-root;
        padding-top: 12px;
      }
      /* drop leading/trailing margins so the body sits flush to the padding */
      .email-content > :first-child {
        margin-top: 0;
      }
      .email-content > :last-child {
        margin-bottom: 0;
      }

      .email-content :is(:where(img):not(:where([class~='not-prose'], [class~='not-prose'] *))) {
        border-width: 0;
      }
      .email-content :where(img):not(:where([class~='not-prose'], [class~='not-prose'] *)) {
        margin: 0;
      }
      .email-content :where(blockquote p:first-of-type):not(:where([class~='not-prose'], [class~='not-prose'] *))::before {
        content: none;
      }
      .email-content :where(blockquote p:last-of-type):not(:where([class~='not-prose'], [class~='not-prose'] *))::after {
        content: none;
      }
    </style>
  </head>
  <body>
    <div class="email-content prose-f">${processedContent.value}</div>
  </body>
  </html>
  `
);

watch(iframeRef, (iframe) => {
	if (iframe) {
		iframe.onload = () => {
			const emailContent = iframe.contentWindow?.document.querySelector(".email-content");
			if (!emailContent) return;

			const parent = emailContent.closest("html");
			if (!parent) return;
			parent.setAttribute("data-theme", dataTheme.value);

			// measure content → set iframe height; flag overflow so the edge fades
			const syncHeight = () => {
				const full = parent.offsetHeight + 1;
				iframe.style.height = full + "px";
				isClipped.value = full > MAX_CONTENT_HEIGHT;
			};

			// inherit host styles into the iframe; external sheets load async, so re-measure after
			applyCssToIframe(iframe, syncHeight);

			// note: helpdesk's per-content font class (Arabic → system-ui) dropped; re-add if needed

			syncHeight();

			// re-dispatch pointerdown so outside-click popovers fire (iframe clicks don't bubble)
			iframe.contentDocument?.addEventListener("pointerdown", () => {
				document.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
			});

			// Re-dispatch keystrokes so app keyboard shortcuts work while the iframe has focus
			iframe.contentDocument?.addEventListener("keydown", (e) => {
				document.dispatchEvent(
					new KeyboardEvent("keydown", {
						key: e.key,
						code: e.code,
						ctrlKey: e.ctrlKey,
						metaKey: e.metaKey,
						shiftKey: e.shiftKey,
						altKey: e.altKey,
						bubbles: true,
					})
				);
			});

			const replyCollapsers = emailContent.querySelectorAll(".replyCollapser");
			if (replyCollapsers.length) {
				replyCollapsers.forEach((replyCollapser) => {
					replyCollapser.addEventListener("change", syncHeight);
				});
			}
		};
	}
});

watch(dataTheme, (theme) => {
	const html = iframeRef.value?.contentDocument?.documentElement;
	if (html) html.setAttribute("data-theme", theme);
});
</script>

<style scoped>
/* fade the clipped bottom edge (~18px) so a long email never hard-slices a line */
.email-clipped-fade {
	-webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 18px), transparent);
	mask-image: linear-gradient(to bottom, #000 calc(100% - 18px), transparent);
}
</style>
