<template>
	<iframe
		ref="iframeRef"
		:srcdoc="htmlContent"
		class="prose-f block h-10 max-h-[500px] w-full"
	/>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { applyCssToIframe, stripEmailColors, useDataTheme } from "./utils";

const props = defineProps<{
	content: string;
}>();

const iframeRef = ref<HTMLIFrameElement | null>(null);
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

const htmlContent = computed(
	() => `
  <!DOCTYPE html>
  <html>
  <head>
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
      .email-content {
        word-break: break-word;
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

			// Inherit the host app's compiled styles (frappe-ui prose-f, color
			// tokens, fonts) into the isolated iframe; external sheets load async,
			// so re-measure the iframe height once they apply.
			applyCssToIframe(iframe, () => {
				iframe.style.height = parent.offsetHeight + 1 + "px";
			});

			// note: helpdesk added a per-content font class here (getFontFamily,
			// Arabic → system-ui); dropped for now, re-add on emailContent if needed

			iframe.style.height = parent.offsetHeight + 1 + "px";

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
					replyCollapser.addEventListener("change", () => {
						iframe.style.height = parent.offsetHeight + 1 + "px";
					});
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
