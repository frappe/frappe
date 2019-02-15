<template>
	<div>
		<div class="row form-section visible-section">
			<div class="col-sm-12">
				<h6 class="form-section-heading uppercase">SQL Queries</h6>
			</div>
			<div class="section-body">
				<div class="form-column col-sm-12">
					<form>
						<div class="frappe-control" data-fieldtype="Table" data-fieldname="fields" title="fields">
							<div data-fieldname="fields">
								<div class="form-grid">
									<div class="grid-heading-row">
										<div class="grid-row">
											<div class="data-row row">
												<div class="row-index sortable-handle col col-xs-1">
													<span>Index</span></div>
												<div class="col grid-static-col col-xs-8">
													<div class="static-area ellipsis">Query</div>
												</div>
												<div class="col grid-static-col col-xs-2">
													<div class="static-area ellipsis">Duration</div>
												</div>
											</div>
										</div>
									</div>
									<div class="grid-body">
										<div class="rows">
											<div class="grid-row" :class="showing == index ? 'grid-row-open' : ''" @click="showing = index"  v-for="(call, index) in sorted(filtered(request.calls))" :key="call.index" v-bind="call">
												<div class="data-row row" v-if="showing != index" style="display: block;">
													<div class="row-index sortable-handle col col-xs-1">
														<span>{{ call.index }}</span></div>
													<div class="col grid-static-col col-xs-8 " data-fieldname="code" data-fieldtype="Code">
														<div class="static-area">
															<span>{{ call.query }}</span>
														</div>
													</div>
													<div class="col grid-static-col col-xs-2 " data-fieldname="duration" data-fieldtype="Time">
														<div class="static-area ellipsis">{{ call.duration }}</div>
													</div>
													<div class="col col-xs-1 sortable-handle"><a class="close btn-open-row">
														<span class="octicon octicon-triangle-down"></span></a>
													</div>
												</div>
												<div class="form-in-grid">
													<div class="grid-form-heading"  @click="showing = null">
														<div class="toolbar grid-header-toolbar">
															<span class="panel-title">
																SQL Query #<span class="grid-form-row-index">{{ call.index }}</span></span>
															<button class="btn btn-default btn-xs pull-right" style="margin-left: 7px;">
																<span class="hidden-xs octicon octicon-triangle-up"></span>
															</button>
														</div>
													</div>
													<div class="grid-form-body">
														<div class="form-area">
															<div class="form-layout">
																<div class="form-page">
																	<div class="row form-section visible-section">
																		<div class="section-body">
																			<div class="form-column col-sm-12">
																				<form>
																					<div class="frappe-control">
																						<div class="form-group">
																							<div class="clearfix"><label class="control-label" style="padding-right: 0px;">Query</label></div>
																							<div class="control-input-wrapper">
																								<div class="control-value like-disabled-input for-description"><pre>{{ call.query }}</pre></div>
																							</div>
																						</div>
																					</div>
																					<div class="frappe-control input-max-width">
																						<div class="form-group">
																							<div class="clearfix"><label class="control-label" style="padding-right: 0px;">Duration</label></div>
																							<div class="control-input-wrapper">
																								<div class="control-value like-disabled-input">{{ call.duration }}</div>
																							</div>
																						</div>
																					</div>
																					<div class="frappe-control">
																						<div class="form-group">
																							<div class="clearfix"><label class="control-label" style="padding-right: 0px;">Stack Trace</label></div>
																							<div class="control-input-wrapper">
																								<div class="control-value like-disabled-input for-description"><pre>{{ call.stack }}</pre></div>
																							</div>
																						</div>
																					</div>
																				</form>
																			</div>
																		</div>
																	</div>
																</div>
															</div>
														</div>
													</div>
												</div>
											</div>
										</div>
										<div class="grid-empty text-center hide">No Data</div>
									</div>
								</div>
							</div>
						</div>
					</form>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
export default {
	name: "RequestDetail",
 	data() {
		return {
			showing: null,
			request: {
				calls: [],
			},
			query: {
				sort: "index",
				order: "asc",
				filters: {},
			},
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_request_data",
			args: {
				uuid: this.$route.params.request_uuid
			}
		}).then( r => {
			this.request = r.message
		});
	},
	methods: {
		filtered: function(calls) {
			calls = calls.slice();
			const filters = Object.entries(this.query.filters);
			calls = calls.filter(
				(r) => filters.map((f) => (r[f[0]] || "").match(f[1])).every(Boolean)
			);
			return calls;
		},
		sorted: function(calls) {
			calls = calls.slice();
			const order = (this.query.order == "asc") ? 1 : -1;
			const sort = this.query.sort;
			return calls.sort((a,b) => (a[sort] > b[sort]) ? order : -order);
		},
		sort: function(key) {
			if(key == this.query.sort) {
				this.query.order = (this.query.order == "asc") ? "desc" : "asc";
			} else {
				this.query.order = "asc";
			}
			this.query.sort = key;
		},
		glyphicon: function(key) {
			if(key == this.query.sort) {
				return (this.query.order == "asc") ? "glyphicon-sort-by-attributes" : "glyphicon-sort-by-attributes-alt";
			} else {
				return "glyphicon-sort";
			}
		},
	}
};
</script>
