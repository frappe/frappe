/**
 * frappe.views.GoalsView
 */
frappe.provide("frappe.views");

frappe.views.GoalsView = frappe.views.ListRenderer.extend({
    name: 'Goals',
    render_view: function (values) {
        this.frequencies = ["Daily", "Weekly", "Monthly", "Annually"];

        this.get_goal_summaries(this.render_goals_view.bind(this));
    },
    set_defaults: function() {
        this._super();
        this.page_title = this.page_title + ' ' + __('Goals');
    },
    get_header_html: function() {
        return null;
    },

    render_goals_view: function () {
        // let html = this.goals.map(this.render_goal.bind(this)).join("");
        this.container = $('<div>')
            .addClass('goals-view-container')
            .appendTo(this.wrapper);

        this.frequencies.map((f) => {
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
        console.log("this.goals", this.goals);
        let all_goals = this.goals[frequency].count.concat(this.goals[frequency].aggregation);
        all_goals.map((goal) => {
            $goal_list.append(this.render_goal(goal));
        });

        $frequency_section.append($goal_list);

        return $frequency_section;
    },

    render_goal: function(goal) {
        let current_value = parseInt(goal.current_value);
        let goal_target = parseInt(goal.target);
        let break_up_string = goal.break_up.map(b => b.value).reverse().join(' | ');
        let title = goal.based_on ? goal.based_on : this.doctype + "s";

        console.log("all goal mode", current_value, goal, goal_target);

        // different for completed state
        let $goal_card = frappe.render_template('goal_item',
            {
                title: title,
                completed: current_value + "",
                remaining: (goal_target - current_value) + "",
                break_up_freq: goal.break_up_freq,
                break_up: break_up_string,

                doc_count: goal.doc_count,
                average: goal.average,

                // Verbose args, but best not to do more calculations in template?
                completed_percent: (current_value/goal_target * 100) + "",
                remaining_percent: ((goal_target - current_value)/goal_target * 100) + "",

                // depending on state
                color:""
            }
        );

        return $goal_card;
    },

    get_goal_summaries: function(callback) {
        let me = this;
        return frappe.call({
            method: 'frappe.core.doctype.goal.goal.get_goals',
            args: {
                doctype: me.doctype
            },
            callback: function(r) {
                console.log("ALL SUMMARIES", r.message);
                me.goals = r.message;
                callback();
            }
        });
    }

});