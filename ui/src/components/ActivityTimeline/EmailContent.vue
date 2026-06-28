<template>
	<iframe
		ref="iframeRef"
		:srcdoc="htmlContent"
		sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
		referrerpolicy="no-referrer"
		class="prose-f block h-10 max-h-[500px] w-full"
		:class="{ 'email-clipped-fade': isClipped }"
	/>
</template>
<!-- sandboxed iframe to prevent scripts from running and external resources from loading -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { applyCssToIframe, stripEmailColors, useDataTheme } from "./utils";

const props = defineProps<{
	content: string;
}>();

// keep in sync with the `max-h-[500px]` on the iframe — past this the body is
// clipped, and we fade the cut edge instead of hard-slicing a line
const MAX_CONTENT_HEIGHT = 500;

const iframeRef = ref<HTMLIFrameElement | null>(null);
const isClipped = ref(false);
const _content = ref(stripEmailColors(props.content));
const dataTheme = useDataTheme();

const parser = new DOMParser();
const doc = parser.parseFromString(_content.value, "text/html");

const gmailReplyToContent = doc.querySelectorAll("div.gmail_quote");
const outlookReplyToContent = doc.querySelectorAll("div#appendonsend");
const replyToContent = doc.querySelectorAll("p.reply-to-content");

if (gmailReplyToContent.length) {
	_content.value = parseReplyToContent(doc, "div.gmail_quote", true);
} else if (outlookReplyToContent.length) {
	_content.value = parseReplyToContent(doc, "div#appendonsend");
} else if (replyToContent.length) {
	_content.value = parseReplyToContent(doc, "p.reply-to-content");
}

function parseReplyToContent(doc: Document, selector: string, forGmail = false) {
	function handleAllInstances(doc: Document) {
		const replyToContentElements = doc.querySelectorAll(selector);
		if (replyToContentElements.length === 0) return;
		const replyToContentElement = replyToContentElements[0];
		replaceReplyToContent(replyToContentElement, forGmail);
		handleAllInstances(doc);
	}

	handleAllInstances(doc);
	return doc.body.innerHTML;
}

function replaceReplyToContent(replyToContentElement: Element, forGmail: boolean) {
	if (!replyToContentElement) return;
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
		const prevSibling = replyToContentElement.previousElementSibling;
		if (prevSibling && prevSibling.tagName === "BR") {
			prevSibling.remove();
		}
		const cloned = replyToContentElement.cloneNode(true) as Element;
		cloned.classList.remove("gmail_quote");
		wrapper.appendChild(cloned);
	} else {
		const allSiblings = Array.from(replyToContentElement.parentElement?.children || []);
		const replyToContentIndex = allSiblings.indexOf(replyToContentElement);
		const followingSiblings = allSiblings.slice(replyToContentIndex + 1);

		if (followingSiblings.length === 0) return;

		const clonedFollowingSiblings = followingSiblings.map((sibling) =>
			sibling.cloneNode(true)
		);

		const div = doc.createElement("div");
		div.append(...clonedFollowingSiblings);
		wrapper.append(div);

		for (let i = replyToContentIndex + 1; i < allSiblings.length; i++) {
			replyToContentElement.parentElement?.removeChild(allSiblings[i]);
		}
	}

	replyToContentElement.parentElement?.replaceChild(wrapper, replyToContentElement);
}

// <meta /> tag added to prevent scripts from running inside the iframe, and to prevent the iframe from loading any external resources (images, fonts, etc.) that could be used for tracking. The iframe is sandboxed to further restrict its capabilities.
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
        /* contain child margins so the first line isn't clipped at the iframe's
           top edge (margin-collapse escaping the top) and the measured height
           stays accurate */
        display: flow-root;
        /* breathing room between the card border and the first line — kept
           *inside* the scroll viewport so it scrolls away with the content and
           scrolled email clips flush at the border, not 12px below it */
        padding-top: 12px;
      }
      /* drop the leading/trailing margins so the body sits flush against this
         element's padding — the iframe-internal padding-top / card pb-2 provide
         the breathing room */
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
    <div class="email-content prose-f">${_content.value}</div>
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

			// measure content → set iframe height, and flag when it overflows the
			// cap so the template fades the clipped bottom edge
			const syncHeight = () => {
				const full = parent.offsetHeight + 1;
				iframe.style.height = full + "px";
				isClipped.value = full > MAX_CONTENT_HEIGHT;
			};

			// Inherit the host app's compiled styles (frappe-ui prose-f, color
			// tokens, fonts) into the isolated iframe; external sheets load async,
			// so re-measure the iframe height once they apply.
			applyCssToIframe(iframe, syncHeight);

			// note: helpdesk added a per-content font class here (getFontFamily,
			// Arabic → system-ui); dropped for now, re-add on emailContent if needed

			syncHeight();

			// Clicks inside the iframe don't bubble to the parent document, so popovers
			// and dropdowns that close on outside-click never fire without this.
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
/* Very subtle fade on the clipped bottom edge — softens only the last sliver
 * (~18px) so a long email never hard-slices a line. Transparency-based, so it
 * works on any card background and in both themes. */
.email-clipped-fade {
	-webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 18px), transparent);
	mask-image: linear-gradient(to bottom, #000 calc(100% - 18px), transparent);
}
</style>
