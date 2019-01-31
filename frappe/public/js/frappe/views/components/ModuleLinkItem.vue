<template>
    <div class="link-item">
        <div v-if="dependencies && incomplete_dependencies"
            @mouseover="hover = true" @mouseleave="hover = false"
            class="disabled-link indicator grey"
        >
            <span class="text-muted">{{ label || __(name) }}</span>

            <div v-show="hover"
                class="popover fade top in" role="tooltip"
            >

                <div class="arrow"></div>
                <h3 class="popover-title" style="display: none;"></h3>
                <div class="popover-content">
                    <div class="small text-muted">{{ __("You need to create these first: ") }}</div>
                    <div>{{ __(incomplete_dependencies.join(", ")) }}</div>
                </div>
            </div>

        </div>

        <div v-else>
            <a class="indicator"
                :class="onboard && !count ? 'orange' : 'grey'"
                :href="route"
            >
                {{ label || __(name) }}
            </a>
            <span class="open-notification global hide"
                @click="doctype || name ? frappe.ui.notifications.show_open_count_list(doctype || name) : false"
                :data-doctype="doctype || name"></span>
        </div>
    </div>
</template>

<script>
export default {
    props: ['label', 'name', 'dependencies', 'incomplete_dependencies', 'onboard', 'count', 'route', 'doctype'],
    data() {
        return {
            hover: false
        }
    },
}
</script>


<style lang="less" scoped>
.link-item {
		position: relative;
		margin: 10px 0px;
	}

a:hover, a:focus {
	text-decoration: underline;
}

// Overriding indicator styles
.indicator {
	font-weight: inherit;
    color: inherit;
}

.disabled-link > span {
    margin-left: 4px;
}

.popover {
    display: block;
    top: -60px;
    max-width: 220px;
}

.popover.top > .arrow {
    left: 20%;
}
</style>
