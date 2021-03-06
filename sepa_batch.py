# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-2014 XCG Consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import osv, fields
from openerp.tools.translate import _


class account_voucher_sepa_batch(osv.Model):
    _name = "account.voucher.sepa_batch"
    _columns = {
        'name': fields.char("Name", size=256),
        'amount': fields.float("Total"),
        'creditor_bank_id': fields.many2one(
            "res.partner.bank",
            "Creditor bank",
            readonly=True,
        ),
        'line_ids': fields.one2many("account.voucher", "batch_id", "Lines"),
        'wording': fields.char("Wording", size=20),
        'execution_date': fields.date('Execution Date'),
        'company_id': fields.many2one('res.company', "Company", select=1),
    }

    _defaults = {
        'company_id': lambda s,cr,uid,c: s.pool['res.company']._company_default_get(cr, uid, 'account.voucher.sepa_batch', context=c),
    }

    _sql_constraints = [
        (
            'unique_name',
            'unique(name, company_id)',
            "The name must be unique by company!")
    ]

    def create(self, cr, uid, vals, context=None):
        vals['name'] = self.pool['ir.sequence'].get(
            cr, uid, 'account.voucher.sepa_batch'
        )
        return super(account_voucher_sepa_batch, self).create(
            cr, uid, vals, context=context)

    def launch_wizard_regenerate_sepa(self, cr, uid, ids, context=None):
        if context and 'active_ids' in context:
            if len(context['active_ids']) != 1:
                raise osv.except_osv(
                    _('Error'),
                    _('Please select only one Batch.')
                )
        ir_ui_view_osv = self.pool['ir.ui.view']
        view_id = ir_ui_view_osv.search(
            cr, uid,
            [('name', '=', 'view.account.voucher.sepa_regeneration')],
            context=context
        )

        context['record_id'] = ids

        return {
            'name': 'Regenerate SEPA',
            'type': 'ir.actions.act_window',
            'res_model': 'account.voucher.sepa_regeneration',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'context': context,
            'target': 'new',
        }

    def sepa_email_remittance_letters(self, cr, uid, ids, context=None):
        ''' Launch the Remittance Letter email wizard for the vouchers in
        selected SEPA batches. '''

        # Store voucher ids in the context.
        if 'active_ids' not in context:
            raise osv.except_osv(
                _('Error'),
                _('No item selected.')
            )
        sepas = self.browse(cr, uid, context['active_ids'], context=context)
        context['active_ids'] = []
        for sepa in sepas:
            context['active_ids'].extend(
                [voucher.id for voucher in sepa.line_ids])

        view_obj = self.pool['ir.ui.view']
        view_id = view_obj.search(
            cr, uid,
            [('name', '=', 'email.remittance')])

        return {
            'context': context,
            'name': _('Email Remittance Letters'),
            'res_model': 'email.remittance',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_id': view_id,
            'view_mode': 'form',
            'view_type': 'form',
        }


class account_voucher_sepa_regeneration(osv.TransientModel):
    _name = 'account.voucher.sepa_regeneration'
    _columns = {
        'voucher_wizard_ids': fields.one2many(
            'account.voucher.wizard',
            'sepa_regeneration_id',
            "Lines",
        ),
        'wording': fields.char('Wording', size=128, required=True),
        'execution_date': fields.date('Execution Date', required=True),
    }

    def __get_data_from_wizard(self, cr, uid, ids, context=None):
        data = self.read(cr, uid, ids, [], context=context)[0]
        if not data['voucher_wizard_ids']:
            return False, False
        return True, data

    def default_get(self, cr, uid, fields_list=None, context=None):
        if 'active_ids' not in context:
            return {}

        vals = {}
        voucher_osv = self.pool['account.voucher']
        batch_osv = self.pool['account.voucher.sepa_batch']
        batch_br = batch_osv.browse(
            cr, uid,
            context['active_ids'][0],
            context=context
        )
        voucher_ids = [v.id for v in batch_br.line_ids]
        vouchers = voucher_osv.read(
            cr, uid, voucher_ids,
            ['partner_id', 'amount', 'partner_bank_id'],
            context=context,
        )

        for v in vouchers:
            v['voucher_id'] = v.pop('id')
            v['partner_id'] = v['partner_id'][0]
            if v['partner_bank_id']:
                v['partner_bank_id'] = v['partner_bank_id'][0]

        vals['voucher_wizard_ids'] = [(0, 0, v) for v in vouchers]
        vals['wording'] = batch_br.wording
        vals['execution_date'] = batch_br.execution_date

        return vals

    def __delete_attachement(self, cr, uid, _id, context=None):
        att_osv = self.pool['ir.attachment']
        att_id = att_osv.search(
            cr, uid,
            [('res_id', '=', _id)],
            context=context
        )
        if att_id:
            att_osv.unlink(cr, uid, att_id, context=context)

    def regenerate_sepa(self, cr, uid, ids, context=None):
        active_id = context['active_ids'][0]

        test, data = self.__get_data_from_wizard(cr, uid, ids, context=context)
        if not test:
            return {'type': 'ir.actions.act_window_close'}

        voucher_wizard_ids = data['voucher_wizard_ids']

        account_voucher_wizard_osv = self.pool['account.voucher.wizard']

        list_voucher_wizard = account_voucher_wizard_osv.browse(
            cr, uid, voucher_wizard_ids, context=context
        )

        voucher_osv = self.pool['account.voucher']
        voucher_ids = [v.voucher_id.id for v in list_voucher_wizard]
        list_voucher = voucher_osv.browse(
            cr, uid, voucher_ids, context=context
        )

        self.__delete_attachement(cr, uid, active_id, context=context)

        vals = {
            'wording': data['wording'],
            'execution_date': data['execution_date'],
        }

        batch_osv = self.pool['account.voucher.sepa_batch']
        batch_osv.write(cr, uid, active_id, vals, context=context)

        sepa_osv = self.pool['account.voucher.sepa']
        sepa_osv.generate_sepa(
            cr, uid, active_id, list_voucher_wizard, list_voucher,
            data['execution_date'], context=context
        )

        context['active_id'] = active_id
        context['active_model'] = 'account.voucher.sepa_batch'
        del context['active_ids']

        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': active_id,
            'res_model': 'account.voucher.sepa_batch',
            'name': 'Batch',
            'context': context,
        }
