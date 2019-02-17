<template>
	<div>
		<div class="row form-section visible-section shaded-section">
			<div class="section-body">
				<div class="form-column col-sm-12">
					<form>
						<div class="frappe-control input-max-width col-sm-6" :data-fieldtype="column.type" v-for="(column, index) in columns" :key="index">
							<div class="form-group">
								<div class="clearfix"><label class="control-label">{{ column.label }}</label></div>
								<div class="control-value like-disabled-input">{{ request[column.slug] }}</div>
							</div>
						</div>
					</form>
				</div>
			</div>
		</div>
		<div class="row form-section visible-section">
			<div class="col-sm-12">
				<h6 class="form-section-heading uppercase">SQL Queries</h6>
			</div>
			<div class="section-body">
				<div class="form-column col-sm-12">
					<form>
						<div class="frappe-control" data-fieldtype="Table">
							<div>
								<div class="form-grid">
									<div class="grid-heading-row">
										<div class="grid-row">
											<div class="data-row row">
												<div class="row-index col col-xs-1">
													<span>Index</span></div>
												<div class="col grid-static-col col-xs-8">
													<div class="static-area ellipsis">Query</div>
												</div>
												<div class="col grid-static-col col-xs-2">
													<div class="static-area ellipsis">Duration (ms)</div>
												</div>
											</div>
										</div>
									</div>
									<div class="grid-body">
										<div class="rows">
											<div class="grid-row" :class="showing == index ? 'grid-row-open' : ''"  v-for="(call, index) in request.calls" :key="index" v-bind="call">
												<div class="data-row row" v-if="showing != index" style="display: block;" @click="showing = index" >
													<div class="row-index col col-xs-1"><span>{{ index }}</span></div>
													<div class="col grid-static-col col-xs-8" data-fieldtype="Code">
														<div class="static-area"><span>{{ call.query }}</span></div>
													</div>
													<div class="col grid-static-col col-xs-2">
														<div class="static-area ellipsis">{{ call.duration }}</div>
													</div>
													<div class="col col-xs-1"><a class="close btn-open-row">
														<span class="octicon octicon-triangle-down"></span></a>
													</div>
												</div>
												<div class="form-in-grid">
													<div class="grid-form-heading" @click="showing = null">
														<div class="toolbar grid-header-toolbar">
															<span class="panel-title">SQL Query #<span class="grid-form-row-index">{{ index }}</span></span>
															<div class="btn btn-default btn-xs pull-right" style="margin-left: 7px;">
																<span class="hidden-xs octicon octicon-triangle-up"></span>
															</div>
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
																							<div class="clearfix"><label class="control-label">Query</label></div>
																							<div class="control-value like-disabled-input for-description"><pre>{{ call.query }}</pre></div>
																						</div>
																					</div>
																					<div class="frappe-control input-max-width">
																						<div class="form-group">
																							<div class="clearfix"><label class="control-label">Duration (ms)</label></div>
																							<div class="control-value like-disabled-input">{{ call.duration }}</div>
																						</div>
																					</div>
																					<div class="frappe-control">
																						<div class="form-group">
																							<div class="clearfix"><label class="control-label">Stack Trace</label></div>
																							<div class="control-value like-disabled-input for-description"><pre>{{ call.stack }}</pre></div>
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
										<div v-if="request.calls.length == 0" class="grid-empty text-center">No Data</div>
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
			columns: [
				{label: "Path", slug: "path", type: "Data"},
				{label: "CMD", slug: "cmd", type: "Data"},
				{label: "Time", slug: "time", type: "Time"},
				{label: "Duration (ms)", slug: "duration", type: "Float"},
				{label: "Number of Queries", slug: "queries", type: "Int"},
				{label: "Time in Queries (ms)", slug: "time_queries", type: "Float"},
				{label: "Request Headers", slug: "headers", type: "Small Text"},
				{label: "Form Dict", slug: "form_dict", type: "Small Text"},
			],
			showing: null,
			request: {
				calls: [],
			},
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.recorder.get",
			args: {
				uuid: this.$route.params.id
			}
		}).then( r => {
			this.request = r.message
		});
	}
};
</script>
