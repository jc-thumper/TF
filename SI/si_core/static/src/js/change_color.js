odoo.define('si_core.change_color', function (require) {
    // To use this widget, define in view:
    // <field name=FIELD_NAME widget="change_color" attrs='{"color": "#f37c21", "header-color": "#f37c21"}'/>
    // color: the color of the field's value
    // header-color: the color of the field's header'
    // If there's any field is not set, the value will be default as black

    "use strict";
    // import packages
    let basic_fields = require('web.basic_fields'),
        registry = require('web.field_registry');

    // widget implementation
    let ChangeColorWidget = basic_fields.FieldChar.extend({

        init: function(){
            this._super.apply(this, arguments);

            // Get color value from attrs value in field definition
            // Ex: <field name="Name" widget="change_color" attrs = '{"color": "#f37c21"}'/>
            this.newColor = 'black';
            if (this.attrs.hasOwnProperty('attrs')) {
                try{
                    let json_obj = JSON.parse(this.attrs.attrs);

                    if (json_obj.hasOwnProperty('color')){
                        this.newColor = json_obj['color'];
                    }
                }
                catch(err){
                    console.log("There're somes problems when parsing JSON for Change Color Widget.");
                }
            }

        },

        isSet: function(){
            // Keep 0 value on screen instead of showing blank field
            return true;
        },

        _renderReadonly: function () {
            this._super();

            let old_html_render = this.$el.html(),
                new_html_render = '<span style="color:' + this.newColor + ';">' + old_html_render + '</span>';

            this.$el.html(new_html_render);
        },
    });

    registry.add("change_color", ChangeColorWidget);
});
