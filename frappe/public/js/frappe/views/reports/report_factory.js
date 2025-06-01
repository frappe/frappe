// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

nts.views.ReportFactory = class ReportFactory extends nts.views.Factory {
	make(route) {
		const _route = ["List", route[1], "Report"];

		if (route[2]) {
			// custom report
			_route.push(route[2]);
		}

		nts.set_route(_route);
	}
};
