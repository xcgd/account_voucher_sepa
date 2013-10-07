# -*- coding: utf-8 -*-

from openerp.osv import osv, fields
from openerp.tools.translate import _
from lxml import etree

class account_voucher_sepa_batch(osv.Model):
    _name = "account.voucher.sepa_batch"
    _columns = {
        'name': fields.char("Name", size=256),
        'amount': fields.integer("Total"),
        'creditor_bank_id': fields.many2one(
            "res.partner.bank",
            "Creditor bank",
            readonly=True,
        ),
        'line_ids': fields.one2many("account.voucher", "batch_id", "Lines"),
        'wording': fields.char("Wording", size=128),
        'execution_date': fields.date('Execution Date'),
    }

    _sql_constraints = [
        ('unique_name',
        'unique(name)',
        'The name must be unique.')
    ]

    def create(self, cr, uid, vals, context=None):
        vals['name'] = self.pool.get('ir.sequence').get(
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
        ir_ui_view_osv = self.pool.get('ir.ui.view')
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

    def sepa_remittance_letters(self, cr, uid, ids, context=None):
        ''' Send one email for each selected voucher; the email template
        should generate attachments automagically. '''

        voucher_obj = self.pool.get('account.voucher')
        sepas = self.browse(cr, uid, ids, context=context)
        for sepa in sepas:
            voucher_obj.email_remittance_letters(cr, uid,
                [voucher.id for voucher in sepa.line_ids], context=context)


class account_voucher_sepa_regeneration(osv.TransientModel):
    _name = 'account.voucher.sepa_regeneration'
    _columns = {
        'voucher_ids': fields.many2many(
            "account.voucher",
            'account_voucher_reg_rel_',
            'voucher_id',
            'sepa_id',
            _('Lines'),
        ),
        'wording': fields.char('Wording', size=128, required=True),
        'execution_date': fields.date('Execution Date', required=True),
    }

    def default_get(self, cr, uid, fields_list=None, context=None):
        if not 'active_ids' in context:
            return {}
        voucher_osv = self.pool.get('account.voucher')
        voucher_ids = voucher_osv.search(
            cr, uid,
            [('batch_id', '=', context['active_ids'][0])],
            context=context
        )
        batch_osv = self.pool.get('account.voucher.sepa_batch')
        batch_br = batch_osv.browse(
            cr, uid,
            context['active_ids'][0],
            context=context
        )
        return {
            'wording': batch_br.wording,
            'execution_date': batch_br.execution_date,
            'voucher_ids': [(6, 0, voucher_ids)],
        }

    def __delete_attachement(self, cr, uid, _id, context=None):
        att_osv = self.pool.get('ir.attachment')
        att_id = att_osv.search(
            cr, uid,
            [('res_id', '=', _id)],
            context=context
        )
        if att_id:
            att_osv.unlink(cr, uid, att_id, context=context)

    def regenerate_sepa(self, cr, uid, ids, context=None):
        active_id = context['active_ids'][0]

        self.__delete_attachement(cr, uid, active_id, context=context)

        this_br = self.browse(cr, uid, ids[0], context=context)

        voucher_osv = self.pool.get('account.voucher')

        vals = {
            'wording': this_br.wording,
            'execution_date': this_br.execution_date,
        }

        batch_osv = self.pool.get('account.voucher.sepa_batch')
        batch_osv.write(cr, uid, active_id, vals, context=context)

        sepa_osv = self.pool.get('account.voucher.sepa')
        sepa_osv.generate_sepa(
            cr, uid, active_id, this_br.voucher_ids,
            this_br.execution_date, context=context
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
