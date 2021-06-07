odoo.define('si_core.onchange_fake_btn', function (require) {
    /*
    This widget is used to make a fake button on the Odoo view,
    which lead to using an onchange method to update front-end only.
    To use this widget, do as below:
    1. Define an Odoo Boolean fields whose store attribute is False
        Ex: fake_btn = fields.Boolean(store=False, default=False)
    2. Define a field in view (List, Form, ...) whose options attribute
    has a key named 'text' which is your button's text and 'nolabel="1"' to keep out of showing label
    (In this case is "Fake Btn")
        If you want you button is only shown in edit mode, add 'class="oe_edit_only"'
    to the field definition.
        Ex: (In views.xml)
            <field name="fake_btn"
                   widget="bool_view_btn"
                   class="oe_edit_only" nolabel="1"
                   options="{'text':'RESET ALL'}"/>
    3. Create an onchange method to update Odoo view (front-end) whenever user clicking on the button
        Ex: (In models/"model_name".py)
            @api.onchange('fake_btn')
            def _onchange_fake_btn(self):
            """
                Handle fake button click event
            """
                pass

    To make a fake button run local javascript function, create a new widget extend this one,
    override the "_onClick" function and not create the "onchange" method on your python code,
    change the widget attribute in step 2 to your new widget name
        Ex:
            odoo.define('si_core.run_js_fake_btn', function (require) {
                var registry = require('web.field_registry');
                var OnChangeFakeBtn = require('si_core.onchange_fake_btn');

                var RunJSFakeBtn = OnChangeFakeBtn.extend({
                    _onClick: function (event) {
                        this._super.apply(this, arguments);

                        // Do whatever you want
                    }
                });

                registry.add('run_js_fake_btn', RunJSFakeBtn);
            });
    */

    let basic_fields = require('web.basic_fields'),
        FieldBoolean = basic_fields.FieldBoolean,
        registry = require('web.field_registry');

    let OnChangeFakeBtn = FieldBoolean.extend({
        className: FieldBoolean.prototype.className + ' btn',

        events: {
            'click': '_onClick'
        },

        init: function () {
            this._super.apply(this, arguments);
            this.button_type = this.attrs.button_type;
        },

        _render: function () {
            this._super.apply(this, arguments);
            this.$el.empty();

            let text = this.nodeOptions.text,
                $val = $('<span>').addClass('o_stat_text').text(text);

            this.$el.append($val);
            this.$el.removeClass('custom-control');

            switch (this.button_type) {
                case 'secondary':
                    this.$el.addClass('btn-secondary');
                    break;
                case 'primary':
                    this.$el.addClass('btn-primary');
                    break;
                default:
                    this.$el.addClass('btn-primary');
                    break;
            }
        },

        _onClick: function (event) {
            event.stopPropagation();

            //Trigger the onchange function
            this._setValue(!this.value);
        },
    });

    registry.add('onchange_fake_btn', OnChangeFakeBtn);

    return OnChangeFakeBtn;

});
