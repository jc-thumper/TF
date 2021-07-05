odoo.define('account_billable_expense.section_and_note_backend', function (require) {
    'use strict';

    let SectionAndNoteListRenderer = require('account.section_and_note_backend');

    SectionAndNoteListRenderer.include({
        /**
         * By default, Odoo only use widget `section_and_note_text` for field `name`.
         * This method is to apply for field `usa_description`.
         *
         * @override
         */
        _renderBodyCell: function (record, node, index, options) {
            let $cell = this._super.apply(this, arguments);

            let isSection = record.data.display_type === 'line_section';
            let isNote = record.data.display_type === 'line_note';

            if (isSection || isNote) {
                if (node.attrs.widget === "handle") {
                    return $cell;
                }
                if (node.attrs.name === "usa_description") {
                    // Revert remove/add class
                    $cell.removeClass('o_hidden');

                    let nbrColumns = this._getNumberOfCols();
                    if (this.handleField) {
                        nbrColumns--;
                    }
                    if (this.addTrashIcon) {
                        nbrColumns--;
                    }
                    $cell.attr('colspan', nbrColumns);
                }
            }

            return $cell;
        },
    })
});