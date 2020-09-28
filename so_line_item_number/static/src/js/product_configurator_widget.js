odoo.define('so_line_item_number.product_configurator', function (require) {
    "use strict";

    var ProductConfiguratorWidget = require('sale_product_configurator.product_configurator');


    return ProductConfiguratorWidget.include({

        _productsToRecords: function (products) {
            var records = this._super.apply(this, arguments);

            _.each(records, function (record) {
                var product = _.find(products, function (product) {
                    return product.product_id === record.default_product_id;
                });
                record.default_parent_product_id = product.parent_product_id;
            });

            return records;
        }
    });
});
