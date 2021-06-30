odoo.define('si_core.ListRenderer', function (require) {
    "use strict";

    let ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        /** Overrider function
         * */
        _renderHeaderCell: function (node) {
            let $th = this._super(node);

            let attrs = node.attrs,
                name = attrs.name,
                widget = attrs.widget,
                field = this.state.fields[name];

            if (field !== undefined
                && widget === 'change_color') {
                    if (attrs.hasOwnProperty('attrs')) {
                        try{
                            let json_obj = JSON.parse(attrs.attrs);

                            if (json_obj.hasOwnProperty('header-color')){
                                let newColor = json_obj['color'] || 'black';

                                $th.css('color', newColor);
                            }

                        }
                        catch(err){
                            console.log("There're somes problems when parsing JSON for Change Color Widget.");
                        }
                    }
            }

            return $th;
        },

    });
});
