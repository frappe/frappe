frappe.pages['goals'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Goals',
        single_column: true
    });
    frappe.goals = new frappe.Goals({page:page});
}

frappe.pages['goals'].on_page_show = function() {
    // frappe.goals.refresh();
}

frappe.Goals = class Goals {
    constructor({
        page = null
    } = {}) {
        this.page = page
        this.goals = {};
        this.frequencies = ["Daily", "Weekly", "Monthly", "Annually"];
        this.render_page();
    }

    render_page() {
        this.container = $('<div>')
            .addClass('goals-page-container')
            .appendTo(this.page.main);

        this.load_goals();
    }

    load_goals() {
        // As:
        // this.goals = {
        //     "Sales Order": {summary},
        //     "Customer": {summary},
        //     ...
        // }
        let me = this;
        return frappe.call({
            method: 'frappe.core.doctype.goal.goal.get_doctype_goals',
            args: {},
            callback: function(r) {
                me.goals = r.message;
                me.render_goals();
            }
        });
    }

    render_goals() {
        Object.keys(this.goals).map((doctype) => {
            this.render_doctype_goals(doctype);
        });
    }

    render_doctype_goals(doctype) {
        let summary = this.goals[doctype];
        let goals = []

        this.frequencies.map((f) => {
            goals = goals.concat(summary[f].count, summary[f].aggregation);
        });

        goals.map(this.add_goal_card.bind(this));

    }

    add_goal_card(goal) {
        let $goal_card = new frappe.GoalCard({
            parent: this.container,
            goal: goal
        });
    }

}

frappe.GoalCard = class GoalCard {
    constructor({
        parent = null,
        goal = {}

    } = {}) {
        this.goal = goal;
        this.parent = parent;

		this.parent.append(this.render_goal(this.goal));

    }

    render_goal(goal) {
        let title = goal.doctype + "s" + (goal.based_on ? " - " + goal.based_on : "");
        let current_value = parseInt(goal.current_value);
        let goal_target = parseInt(goal.target);

		let break_up_list = goal.break_up.map(b => b.value).reverse();
        let break_up_dates = goal.break_up.map(b => b.day).reverse();
        let break_up_string = break_up_list.join(' | ');

        function get_upper_limit(array) {

            let max_val = Math.max(...array);
            let multiplier = 0;
            if((max_val+"").length <= 1) {
                return 10;
            } else {
                multiplier = Math.pow(10, ((max_val+"").length - 1));
                return Math.ceil(max_val/multiplier) * multiplier;
            }

        }

        function get_y_axis(array, parts) {
            let upper_limit = get_upper_limit(array);
            let y_axis = [];
            for(var i = 0; i < parts; i++){
                y_axis.push(upper_limit / parts * i);
            }
            return y_axis;
        }

        console.log("goal", current_value, goal, goal_target);

        let $goal_card = frappe.render_template('goal_card',
            {
                title: title,
                target: goal_target,
                completed: current_value + "",
                remaining: (goal_target - current_value) + "",

				break_up_list: break_up_list,
                break_up_dates: break_up_dates,
                break_up_freq: goal.break_up_freq,
                break_up: break_up_string,

                upper_graph_bound: get_upper_limit(break_up_list),


                // for graph
                y_axis: get_y_axis(break_up_list, 5),

                doc_count: goal.doc_count,
                average: goal.average ? goal.average.toFixed(2) : undefined,

                // Verbose args, but best not to do more calculations in template?
                completed_percent: (current_value/goal_target * 100).toFixed(0) + "",
                remaining_percent: ((goal_target - current_value)/goal_target * 100).toFixed(2) + "",

                // depending on state
                color:""
            }
        );

        return $goal_card;
    }


}
