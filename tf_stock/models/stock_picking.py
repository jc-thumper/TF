from datetime import timedelta
from odoo.osv import expression
from odoo.tools.misc import split_every

from odoo import api, fields, models, _

from odoo.addons.stock.models.stock_move import StockMove
from odoo.addons.stock.models.stock_rule import ProcurementGroup

class StockPickingTypeInherit(models.Model):
    _inherit = 'stock.picking.type'

    reservation_method = fields.Selection(
        [('at_confirm', 'At Confirmation'), ('manual', 'Manually'), ('by_date', 'Before scheduled date')],
        'Reservation Method', required=True, default='at_confirm',
        help="How products in transfers of this operation type should be reserved.")

    reservation_days_before = fields.Integer('Days', help="Maximum number of days before scheduled date that products should be reserved.")


class StockMoveInherit(models.Model):
    _inherit = 'stock.move'

    reservation_date = fields.Date('Date to Reserve', compute='_compute_reservation_date', store=True,
                                   help="This is a technical field for calculating when a move should be reserved")

    @api.depends('picking_type_id', 'date')
    def _compute_reservation_date(self):
        for move in self:
            if move.picking_type_id.reservation_method == 'by_date' and move.state in ['draft', 'confirmed', 'waiting',
                                                                                       'partially_available']:
                days = move.picking_type_id.reservation_days_before
                move.reservation_date = fields.Date.to_date(move.date) - timedelta(days=days)

    # Copy from odoo.addons.stock.stock_move
    def _action_confirm(self, merge=True, merge_into=False):
        """ Confirms stock move or put it in waiting if it's linked to another move.
        :param: merge: According to this boolean, a newly confirmed move will be merged
        in another move of the same picking sharing its characteristics.
        """
        move_create_proc = self.env['stock.move']
        move_to_confirm = self.env['stock.move']
        move_waiting = self.env['stock.move']

        to_assign = {}
        for move in self:
            if move.state != 'draft':
                continue
            # if the move is preceeded, then it's waiting (if preceeding move is done, then action_assign has been called already and its state is already available)
            if move.move_orig_ids:
                move_waiting |= move
            else:
                if move.procure_method == 'make_to_order':
                    move_create_proc |= move
                else:
                    move_to_confirm |= move
            if move._should_be_assigned():
                key = (move.group_id.id, move.location_id.id, move.location_dest_id.id)
                if key not in to_assign:
                    to_assign[key] = self.env['stock.move']
                to_assign[key] |= move

        # create procurements for make to order moves
        procurement_requests = []
        for move in move_create_proc:
            values = move._prepare_procurement_values()
            origin = (move.group_id and move.group_id.name or (move.origin or move.picking_id.name or "/"))
            procurement_requests.append(self.env['procurement.group'].Procurement(
                move.product_id, move.product_uom_qty, move.product_uom,
                move.location_id, move.rule_id and move.rule_id.name or "/",
                origin, move.company_id, values))
        self.env['procurement.group'].run(procurement_requests)

        move_to_confirm.write({'state': 'confirmed'})
        (move_waiting | move_create_proc).write({'state': 'waiting'})
        (move_to_confirm | move_waiting | move_create_proc).filtered(lambda m: m.picking_type_id.reservation_method == 'at_confirm').write({'reservation_date': fields.Date.today()})

        # assign picking in batch for all confirmed move that share the same details
        for moves in to_assign.values():
            moves._assign_picking()

        self._push_apply()
        self._check_company()
        moves = self
        if merge:
            moves = self._merge_moves(merge_into=merge_into)

        # call `_action_assign` on every confirmed move which location_id bypasses the reservation + those expected to be auto-assigned
        moves.filtered(lambda move: not move.picking_id.immediate_transfer and move.state == 'confirmed'
                                    and (move._should_bypass_reservation()
                                         or move.picking_type_id.reservation_method == 'at_confirm'
                                         or (move.reservation_date and move.reservation_date <= fields.Date.today())))._action_assign()
        return moves

    StockMove._action_confirm = _action_confirm


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    def _get_moves_to_assign_domain(self, company_id):
        domain = super(ProcurementGroup, self)._get_moves_to_assign_domain(company_id)
        domain = expression.AND([domain, [('reservation_date', '<=', fields.Date.today())]])
        return domain

    # Copy from odoo.addons.stock.stock_rule
    @api.model
    def _run_scheduler_tasks(self, use_new_cursor=False, company_id=False):
        # Minimum stock rules
        self.sudo()._procure_orderpoint_confirm(use_new_cursor=use_new_cursor, company_id=company_id)
        if use_new_cursor:
            self._cr.commit()

        # Search all confirmed stock_moves and try to assign them
        domain = self._get_moves_to_assign_domain(company_id)
        moves_to_assign = self.env['stock.move'].search(domain, limit=None,
                                                        order='reservation_date, priority desc, date_expected asc')
        for moves_chunk in split_every(100, moves_to_assign.ids):
            self.env['stock.move'].browse(moves_chunk).sudo()._action_assign()
            if use_new_cursor:
                self._cr.commit()

        # Merge duplicated quants
        self.env['stock.quant']._quant_tasks()
        if use_new_cursor:
            self._cr.commit()

    ProcurementGroup._run_scheduler_tasks = _run_scheduler_tasks
