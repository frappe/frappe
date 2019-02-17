<template>
	<div>
		<div class="row form-section visible-section shaded-section">
			<div class="section-body">
				<div class="form-column col-sm-6">
					<form>
						<div class="frappe-control input-max-width" data-fieldtype="Data" data-fieldname="data_1" title="data_1">
							<div class="form-group">
								<div class="clearfix"> <label class="control-label" style="padding-right: 0px;">Path</label></div>
								<div class="control-input-wrapper">
									<div class="control-value like-disabled-input" style="">{{ request.path }}</div>
								</div>
							</div>
						</div>
						<div class="frappe-control input-max-width" data-fieldtype="Data" data-fieldname="data_2" title="data_2">
							<div class="form-group">
								<div class="clearfix"> <label class="control-label" style="padding-right: 0px;">CMD</label></div>
								<div class="control-input-wrapper">
									<div class="control-value like-disabled-input" style="">{{ request.cmd }}</div>
								</div>
							</div>
						</div>
						<div class="frappe-control input-max-width" data-fieldtype="Data" data-fieldname="data_3" title="data_3">
							<div class="form-group">
								<div class="clearfix"> <label class="control-label" style="padding-right: 0px;">Method</label></div>
								<div class="control-input-wrapper">
									<div class="control-value like-disabled-input" style="">{{ request.method }}</div>
								</div>
							</div>
						</div>
					</form>
				</div>
				<div class="form-column col-sm-6">
					<form>
						<div class="frappe-control input-max-width" data-fieldtype="Data" data-fieldname="data_4" title="data_4">
							<div class="form-group">
								<div class="clearfix"> <label class="control-label" style="padding-right: 0px;">Duration</label>
								</div>
								<div class="control-input-wrapper">
									<div class="control-value like-disabled-input" style="">{{ request.duration }}</div>
								</div>
							</div>
						</div>
						<div class="frappe-control input-max-width" data-fieldtype="Data" data-fieldname="queries_duration"
							title="queries_duration">
							<div class="form-group">
								<div class="clearfix"> <label class="control-label" style="padding-right: 0px;">Queries Duration</label></div>
								<div class="control-input-wrapper">
									<div class="control-value like-disabled-input" style="">{{ request.time_queries }}</div>
								</div>
							</div>
						</div>
						<div class="frappe-control input-max-width" data-fieldtype="Data" data-fieldname="time" title="time">
							<div class="form-group">
								<div class="clearfix"> <label class="control-label" style="padding-right: 0px;">Time</label></div>
								<div class="control-input-wrapper">
									<div class="control-value like-disabled-input" style="">{{ request.time }}</div>
								</div>
							</div>
						</div>
					</form>
				</div>
			</div>
		</div>
		<div class="row form-section visible-section">
			<div class="section-body">
				<div class="form-column col-sm-12">
					<form>
						<div class="frappe-control" data-fieldtype="Small Text" data-fieldname="request_headers" title="request_headers">
							<div class="form-group">
								<div class="clearfix"> <label class="control-label" style="padding-right: 0px;">Request Headers</label></div>
								<div class="control-input-wrapper">
									<div class="control-value like-disabled-input for-description" style=""><pre>{{ JSON.stringify(request.http.headers, null, 1) }}</pre></div>
								</div>
							</div>
						</div>
						<div class="frappe-control" data-fieldtype="Small Text" data-fieldname="reponse_headers" title="reponse_headers">
							<div class="form-group">
								<div class="clearfix"> <label class="control-label" style="padding-right: 0px;">Form Dict</label></div>
								<div class="control-input-wrapper">
									<div class="control-value like-disabled-input for-description" style=""><pre>{{ JSON.stringify(request.http.data, null, 1) }}</pre></div>
								</div>
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
											<div class="grid-row" :class="showing == index ? 'grid-row-open' : ''"  v-for="(call, index) in request.calls" :key="index" v-bind="call">
												<div class="data-row row" v-if="showing != index" style="display: block;" @click="showing = index" >
													<div class="row-index sortable-handle col col-xs-1">
														<span>{{ index }}</span></div>
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
																SQL Query #<span class="grid-form-row-index">{{ index }}</span></span>
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
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.recorder.get",
			args: {
				uuid: this.$route.params.request_uuid
			}
		}).then( r => {
			this.request = r.message
		});
	}
};
</script>
