/**
 * frappe.views.GoalsView
 */
frappe.provide("frappe.views");

frappe.views.GoalsView = frappe.views.ListRenderer.extend({
	name: 'Goals',
	render_view: function (values) {
		this.frequencies = ["Daily", "Weekly", "Monthly", "Annually"];
        this.make_goals();
        this.get_doc_count(this.render_goals_view.bind(this));
	},
	set_defaults: function() {
		this._super();
		this.page_title = this.page_title + ' ' + __('Goals');
	},
	get_header_html: function() {
		return null;
	},

    make_goals: function() {
        // Arrange goals as:
        // this.goals = {
        //     "Daily": {
        //         count: [
        //             {
        //                 filters: {},
        //                 target: "10"
        //             }, {} ...
        //         ],
        //         aggregation: [
        //             {
        //                 filters: {},
        //                 based_on: "",
        //                 target: "",
        //                 type: "sum"
        //             }
        //         ],
        //     },
        //     "Weekly": {

        //     }, ...
        // }
        let meta = frappe.get_meta(this.doctype);
		let goals = meta && meta.__goals;

        console.log("goals", goals);

        this.goals = {};
        this.frequencies.map((freq) => {
            this.goals[freq] = {count: [], aggregation: []};
        });

        goals.map((g) => {
            let goal = {};
            if(g.type_of_aggregation === "Count") {
                this.goals[g.frequency].count.push({
                    filters: g.source_filter,
                    target: g.target
                });
            } else {
                this.goals[g.frequency].aggregation.push({
                    filters: g.source_filter,
                    target: g.target,
                    based_on: g.based_on,
                    type: g.type_of_aggregation
                });
            }
        });

        console.log("this.goals", this.goals);
    },

	render_goals_view: function () {
		// let html = this.goals.map(this.render_goal.bind(this)).join("");
		this.container = $('<div>')
			.addClass('goals-view-container')
			.appendTo(this.wrapper);

        // TODO: only 2 frequencies for viewing, has to depend on goals present
        this.frequencies.splice(0, 2).map((f) => {
            this.container.append(this.render_frequency_section(f));
        });

	},

    render_frequency_section: function(frequency) {
        let title = [frequency].map((f) => {
            switch(f) {
                case "Daily":
                    return "Today";
                case "Weekly":
                    return "This Week";
                case "Monthly":
                    return "This Month";
                case "Annually":
                    return "This Year";
                default:
                    return "";
            }
        });

        let $frequency_section = $('<div>')
			.addClass('frequency-section');

        $frequency_section.append($('<div>')
            .addClass('frequency-title')
            .html(title)
        );

        let $goal_list = $('<div>').addClass('goal-list');

        // only 'count' goal for testing
        this.goals[frequency].count.map((goal) => {
            $goal_list.append(this.render_goal(goal));
        });

        $frequency_section.append($goal_list);

        return $frequency_section;
    },

    render_goal: function(goal) {
        let doc_count = parseInt(this.doc_count);
        let goal_target = parseInt(goal.target);
        console.log(doc_count, goal, goal_target);
        let $goal_card = frappe.render_template('goal_item',
            {
                title: this.doctype + "s",
                completed: doc_count + "",
                remaining: (goal_target - doc_count) + "",

                completed_percent: (doc_count/goal_target * 100) + "",
                remaining_percent: ((goal_target - doc_count)/goal_target * 100) + ""
            }
        );

        return $goal_card;
    },

    get_doc_count: function(callback) {
        let me = this;
		return frappe.call({
			method: 'frappe.core.doctype.goal.goal.get_doc_count',
			args: {
				doctype: me.doctype,
                // filters: me.filters
			},
			callback: function(r) {
                console.log("doc count", r.message);
                me.doc_count = r.message;
                callback();
			}
		});
    }

});