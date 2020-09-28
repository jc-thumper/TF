odoo.define('so_line_item_number.OptionalProductsModal', function (require) {
    "use strict";

    var OptionalProductsModal = require('sale_product_configurator.OptionalProductsModal');


    return OptionalProductsModal.include({

        getSelectedProducts: function () {
            var root_product_id = this.rootProduct.product_id;
            var products = this._super.apply(this, arguments);

            _.each(products, function (product) {
                if (product.product_id != root_product_id) {
                    product.parent_product_id = root_product_id || false;
                }
            });

            return products;
        },

    });

});
