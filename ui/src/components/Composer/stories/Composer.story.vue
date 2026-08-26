<template>
	<div class="mx-auto max-w-4xl p-6">
		<h3 class="mb-1 text-xl-semibold text-ink-gray-9">Composers</h3>
		<p class="mb-8 text-p-sm text-ink-gray-6">
			Two standalone, inline message composers. <code>EmailComposer</code> stacks email
			header rows (From/Subject/To/Cc/Bcc, per the <code>show*</code> props) plus an optional
			quoted reply above the editor; <code>CommentComposer</code> is the editor alone, with
			@-mentions, for internal notes. Both are transport-agnostic: <code>submit</code> hands
			back a payload and the host performs the send, then calls the exposed
			<code>reset()</code>. Each scene below is a real host pattern, built from a few lines
			around the inline composer.
		</p>

		<section class="mb-10">
			<div class="text-base font-medium text-ink-gray-8">Ticket reply</div>
			<p class="mb-3 mt-1 text-p-sm text-ink-gray-6">
				A support thread with an Email/Comment switcher. The quoted customer message rides
				<code>v-model:quoted</code> and is appended on send; both drafts survive tab
				switches because the composers stay mounted (<code>v-show</code>, not
				<code>v-if</code>). The whole reply section lives in frappe-ui's
				<code>FloatingWindow</code>: docked it renders in-flow, and its title bar pops it
				out to a draggable window; the same instance moves, so no draft is lost.
			</p>
			<TicketReply />
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ ticketSnippet }}</code></pre>
		</section>

		<section class="mb-10">
			<div class="text-base font-medium text-ink-gray-8">Docked compose window</div>
			<p class="mb-3 mt-1 text-p-sm text-ink-gray-6">
				A Gmail-style compose window: frappe-ui's <code>FloatingWindow</code> around the
				inline composer (FP1: the composer stays out of the window business). Pop it out
				and drag it, or minimize it to the tray; <code>show-from</code> and
				<code>show-subject</code> turn on the full header.
			</p>
			<DockedCompose />
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ dockedSnippet }}</code></pre>
		</section>

		<section class="mb-10">
			<div class="text-base font-medium text-ink-gray-8">Comment thread</div>
			<p class="mb-3 mt-1 text-p-sm text-ink-gray-6">
				An activity feed with <code>CommentComposer</code> pinned underneath. Type
				<code>@</code> to mention a teammate. Submitted comments join the feed and the host
				calls <code>reset()</code>.
			</p>
			<CommentThread />
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ commentSnippet }}</code></pre>
		</section>

		<section class="mb-10">
			<div class="text-base font-medium text-ink-gray-8">Quick reply, custom header</div>
			<p class="mb-3 mt-1 text-p-sm text-ink-gray-6">
				A body-only reply under a message. <code>#header</code> replaces the built-in rows
				wholesale, here a "Replying to" pill, while the host seeds
				<code>v-model:to</code> so the payload still carries the recipient.
			</p>
			<QuickReply />
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ quickSnippet }}</code></pre>
		</section>

		<section class="mb-4">
			<div class="text-base font-medium text-ink-gray-8">Custom utilities</div>
			<p class="mb-3 mt-1 text-p-sm text-ink-gray-6">
				Host utilities in the <code>#actions</code> slot: a canned replies menu beside the
				built-in attach button, inserting through the exposed <code>editor</code>.
			</p>
			<CustomUtility />
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ utilitySnippet }}</code></pre>
		</section>
	</div>
</template>

<script setup lang="ts">
import CommentThread from "./CommentThread.vue";
import CustomUtility from "./CustomUtility.vue";
import DockedCompose from "./DockedCompose.vue";
import QuickReply from "./QuickReply.vue";
import TicketReply from "./TicketReply.vue";

const ticketSnippet = `<!-- Docked renders in-flow; the title bar pops the whole section out. -->
<FloatingWindow title="TICKET-1042 Reply" :minimizable="false">
  <TabButtons v-model="channel" :options="channels" />

  <div v-show="channel === 'reply'">
    <EmailComposer
      v-model="replyBody"
      v-model:to="to"
      v-model:quoted="quoted"
      :search-recipients="searchRecipients"
      @submit="onReply"
    />
  </div>
  <div v-show="channel === 'comment'">
    <CommentComposer v-model="commentBody" :mentions="agents" @submit="onComment" />
  </div>
</FloatingWindow>`;

const dockedSnippet = `<FloatingWindow title="New message">
  <EmailComposer
    v-model="body"
    v-model:to="to"
    v-model:subject="subject"
    v-model:from="from"
    show-from
    show-subject
    :senders="senders"
    @submit="onSend"
  />
</FloatingWindow>`;

const commentSnippet = `<CommentComposer v-model="draft" :mentions="teammates" @submit="onComment" />

async function onComment(payload) {
  await call("add_comment", payload); // { body, attachments }
  composer.value?.reset();
}`;

const quickSnippet = `<EmailComposer v-model="body" v-model:to="to" @submit="onSend">
  <template #header>
    <ReplyingToPill :recipient="to[0]" />
  </template>
</EmailComposer>`;

const utilitySnippet = `<EmailComposer ref="composer" v-model="body">
  <template #actions>
    <Dropdown :options="cannedReplies"><Button :icon="LucideZap" /></Dropdown>
  </template>
</EmailComposer>`;
</script>
