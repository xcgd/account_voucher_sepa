# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-2015 XCG Consulting
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
import datetime
from lxml import etree
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
import openerp.addons.decimal_precision as dp


class account_voucher_wizard(osv.TransientModel):
    _name = "account.voucher.wizard"

    _columns = {
        'operation': fields.selection(
            [('direct_debit', 'Direct Debit'),
             ('transfer', 'Transfer')],
        ),
        'partner_id': fields.many2one('res.partner', u"Partner"),
        'amount': fields.float(
            u"Total",
            digits_compute=dp.get_precision('Account')
        ),
        'partner_bank_id': fields.many2one(
            'res.partner.bank',
            u"Partner Bank",
            domain='[("partner_id", "=", partner_id)]'
        ),
        'mandate_id': fields.many2one(
            'account.sdd.mandate',
            'Mandate',
            domain='[("creditor_id", "=", "partner_bank_id.partner_id")]'
        ),
        'sepa_id': fields.many2one('account.voucher.sepa'),
        'sepa_regeneration_id': fields.many2one('account.voucher.sepa_regeneration'),
        'voucher_id': fields.many2one('account.voucher'),
    }


class account_voucher_sepa(osv.TransientModel):
    _name = "account.voucher.sepa"

    _columns = {
        'operation': fields.selection(
            [('direct_debit', 'Direct Debit'),
             ('transfer', 'Transfer')],
            string='Type of operation',
            help='Either Direct Debit or Transfer',
        ),
        'group_suppliers': fields.boolean(_("Group suppliers")),
        'voucher_wizard_ids': fields.one2many(
            "account.voucher.wizard",
            'sepa_id',
            "Lines",
        ),
        'wording': fields.char('Wording', size=20, required=True),
        'execution_date': fields.date('Execution Date', required=True),
    }

    def generate_credit_transfer_file(self, cr, uid, data, context=None):
        """
        Looks for the appropriate parser for data['debtor_bank'] then
        creates an ir.attachment record with the XML document created
        by said parser.

        :param data: dictionary of values to be passed on the parser
        """
        # Not sure what this does
        voucher_wizards = data['list_voucher_wizard']
        if not all(vw.partner_bank_id.acc_number for vw in voucher_wizards):
            raise osv.except_osv(
                _(u"Error"),
                _(u"Cannot create SEPA batch: no IBAN number.")
            )

        parser_osv = self.pool.get("account_credit_transfer.parser")
        parsers = parser_osv.browse(
            cr, uid,
            [data['debtor_bank'].bank.transfer_parser],
            context=context
        )

        if not parsers:
            raise osv.except_osv(
                _('No parser was found for this bank for transfer operation')
            )

        # There should be at most one element in 'parsers'
        parser = parsers[0]

        att_values = parser.compute(parser.template, data)
        ir_attachment_osv = self.pool.get('ir.attachment')
        ir_attachment_osv.create(cr, uid, att_values, context=context)

    def generate_sepa(self, cr, uid, batch_id,
                      list_voucher_wizard, list_voucher, date, context=None):
        # New version using account_credit_transfer

        batch_osv = self.pool['account.voucher.sepa_batch']
        batch_br = batch_osv.browse(cr, uid, [batch_id], context=context)[0]

        data = {
            'total_amount': batch_br.amount,
            'company_name': list_voucher[0].company_id.name,
            'debtor_bank': batch_br.creditor_bank_id,
            'list_voucher': list_voucher,
            'list_voucher_wizard': list_voucher_wizard,
            'batch': batch_br,
            'date': date,
        }

        self.generate_credit_transfer_file(
            cr, uid, data, context=context
        )

    def __get_data_from_wizard(self, cr, uid, ids, context=None):
        data = self.read(cr, uid, ids, [], context=context)[0]
        if not data['voucher_wizard_ids']:
            return False, False
        return True, data

    def __get_bank_id(self, cr, uid, ids, voucher, context=None):
        # Search with payment modes
        payment_mode_osv = self.pool['payment.mode']
        payment_mode_ids = payment_mode_osv.search(
            cr, uid,
            [("journal", "=", voucher.journal_id.id)],
            context=context
        )
        payment_modes = payment_mode_osv.browse(
            cr, uid,
            payment_mode_ids,
            context=context
        )
        banks = [pm.bank_id for pm in payment_modes]

        # Search in company
        if len(banks):
            return banks[0]

        banks = [bank
                 for bank in voucher.company_id.bank_ids
                 if bank.journal_id.id == voucher.journal_id.id]

        # No banks found
        if not len(banks):
            raise osv.except_osv(
                _("No origin bank account found"),
                _("Bank account for journal %s is not found" %
                  voucher.journal_id.name))

        bank = banks[0]
        if not bank.bank_bic:
            raise osv.except_osv(
                _("Bank BIC"),
                _("Please set the bank BIC for the bank %s" %
                  bank.name))
        return bank

    def prepare_sepa(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        test, data = self.__get_data_from_wizard(cr, uid, ids, context=context)
        if not test:
            return {'type': 'ir.actions.act_window_close'}

        voucher_wizard_ids = data['voucher_wizard_ids']

        batch_osv = self.pool['account.voucher.sepa_batch']
        account_voucher_wizard_osv = self.pool['account.voucher.wizard']

        list_voucher_wizard = account_voucher_wizard_osv.browse(
            cr, uid, voucher_wizard_ids, context=context
        )

        # Compute the total amount of all selected vouchers

        total_amount = 0.0

        for voucher in list_voucher_wizard:
            total_amount += voucher.amount

        voucher_osv = self.pool['account.voucher']
        voucher_ids = [v.voucher_id.id for v in list_voucher_wizard]
        list_voucher = voucher_osv.browse(
            cr, uid, voucher_ids, context=context
        )

        # Get the creditor bank

        bank = self.__get_bank_id(
            cr, uid, ids,
            list_voucher[0],
            context=context
        )

        batch_vals = {
            'amount': total_amount,
            'creditor_bank_id': bank.id,
            'wording': data['wording'],
            'execution_date': data['execution_date']
        }

        # Create the batch, associate all voucher with that batch
        batch_id = batch_osv.create(cr, uid, batch_vals, context=context)
        voucher_osv.write(
            cr, uid,
            voucher_ids,
            {'batch_id': batch_id},
            context=context
        )

        self.generate_sepa(
            cr, uid,
            batch_id,
            list_voucher_wizard,
            list_voucher,
            data['execution_date'],
            context=context
        )

        context['active_id'] = batch_id
        context['active_model'] = 'account.voucher.sepa_batch'
        del context['active_ids']
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': batch_id,
            'res_model': 'account.voucher.sepa_batch',
            'name': 'Batch',
            'context': context,
        }

    def default_get(self, cr, uid, fields_list=None, context=None):
        if 'active_ids' not in context:
            return {}
        vals = {}
        voucher_obj = self.pool['account.voucher']
        vouchers = voucher_obj.read(
            cr, uid,
            context['active_ids'],
            ['partner_id', 'amount', 'partner_bank_id', 'type'],
            context=context
        )
        for v in vouchers:
            v['voucher_id'] = v.pop('id')
            v['partner_id'] = v['partner_id'][0]
            if v['partner_bank_id']:
                v['partner_bank_id'] = v['partner_bank_id'][0]
            # receipt refund need to be positive when paid
            if v['type'] == 'receipt':
                v['amount'] = -v['amount']
            # TODO remove type from dic

        vals['operation'] = (context.get('operation', 'transfer')
                             if context else 'transfer')
        vals['voucher_wizard_ids'] = [(0, 0, v) for v in vouchers]
        return vals

    def fields_view_get(self, cr, uid,
                        view_id=None, view_type='form',
                        context=None, toolbar=False, submenu=False):
        res = super(account_voucher_sepa, self).fields_view_get(
            cr, uid, view_id=view_id,
            view_type=view_type,
            context=context,
            toolbar=toolbar,
            submenu=submenu
        )

        if not context or 'active_ids' not in context:
            return res

        domain = '[("id", "in", ' + str(context["active_ids"]) + ')]'
        doc = etree.XML(res['arch'])
        nodes = doc.xpath("//field[@name='voucher_ids']")

        for node in nodes:
            node.set('domain', domain)
        res['arch'] = etree.tostring(doc)

        return res


class account_voucher(osv.Model):
    _name = "account.voucher"
    _inherit = "account.voucher"

    # This method add a default value to partner_bank_id
    def onchange_partner_id(self, cr, uid, ids,
                            partner_id, journal_id,
                            amount, currency_id, ttype,
                            date, context=None):
        res = super(account_voucher, self).onchange_partner_id(
            cr, uid, ids, partner_id, journal_id, amount,
            currency_id, ttype, date, context
        )

        if not ttype == 'sale' and not ttype == 'purchase':
            bank_osv = self.pool['res.partner.bank']
            bank_id = bank_osv.search(
                cr, uid, [('partner_id', '=', partner_id)], context=context
            )
            if bank_id:
                # Apparently not always present (TKT/2014/00507)
                if 'value' not in res:
                    res['value'] = {}
                res['value']['partner_bank_id'] = bank_id[0]

        return res

    def validate_selected(self, cr, uid, ids, context=None):
        if 'active_ids' not in context:
            raise osv.except_osv(
                _("Integrity Error"),
                _("You must select one voucher to generate SEPA file.")
            )
        this_brs = self.browse(cr, uid, context['active_ids'], context=context)
        for this_br in this_brs:
            this_br._workflow_signal('proforma_voucher')
        return {}

    # TODO Needs refactoring
    def launch_wizard_sepa(self, cr, uid, ids, context=None):
        if 'active_ids' not in context:
            raise osv.except_osv(
                _("Integrity Error"),
                _("You must select one voucher to generate SEPA file.")
            )
        this_brs = self.browse(cr, uid, context['active_ids'], context=context)
        err = ""
        err_post_ids = []
        err_att_ids = []
        err_acc_ids = []
        err_wrong_type_ids = []
        err_amount_ids = []
        type_of_operation = None
        for this_br in this_brs:
            if this_br.type not in ('payment', 'receipt'):
                err_wrong_type_ids.append(this_br.number)
            # Allow payment but only with debit value
            # What should we do when amount == 0
            if this_br.type == 'payment':
                if not this_br.amount >= 0:
                    if not type_of_operation:
                        type_of_operation = 'direct_debit'
                    elif type_of_operation == 'transfer':
                        err_amount_ids.append(this_br.number)
                elif type_of_operation == 'direct_debit':
                    err_amount_ids.append(this_br.number)
                else:
                    type_of_operation = 'transfer'
            # Allow receipt but only with credit value
            if this_br.type == 'receipt':
                if not this_br.amount <= 0:
                    if not type_of_operation:
                        type_of_operation = 'direct_debit'
                    elif type_of_operation == 'transfer':
                        err_amount_ids.append(this_br.number)
                elif type_of_operation == 'direct_debit':
                    err_amount_ids.append(this_br.number)
                else:
                    type_of_operation = 'transfer'
            if this_br.state != 'posted':
                if this_br.number not in err_post_ids:
                    err_post_ids.append(this_br.number)
            if this_br.batch_id:
                if this_br.number not in err_att_ids:
                    err_att_ids.append(this_br.number)
            if not this_br.partner_id.bank_ids:
                if this_br.partner_id.name not in err_acc_ids:
                    err_acc_ids.append(this_br.partner_id.name)

        def stringify(l):
            return [str(x) for x in l]

        # XXX I don't think there is a language where the separator for list
        # would be dependent on the sentence so using _(', ') should be fine
        if err_wrong_type_ids:
            err += _(
                "The voucher %s is not of type 'payment' nor 'receipt'.\n\n"
            ) % _(", ").join(stringify(err_wrong_type_ids))
        else:
            if err_amount_ids:
                err += _(
                    "The voucher %s has an incorrect amount considering its"
                    " type.\n\n"
                ) % _(", ").join(stringify(err_amount_ids))
            if err_post_ids:
                err += _(
                    "The voucher %s must be posted before generating SEPA file"
                    "\n\n"
                ) % _(", ").join(stringify(err_post_ids))
            if err_att_ids:
                err += _(
                    "The voucher %s is already attached to a batch.\n\n"
                ) % _(", ").join(stringify(err_att_ids))
            if err_acc_ids:
                err += _(
                    "Please set a bank account on the partner %s.\n\n"
                ) % _(", ").join(stringify(err_acc_ids))
        if err:
            raise osv.except_osv(
                _(u"Invalid Voucher(s)"),
                err
            )
        ir_ui_view_osv = self.pool['ir.ui.view']
        view_id = ir_ui_view_osv.search(
            cr, uid,
            [('name', '=', 'view.account.voucher.sepa')],
            context=context
        )

        context = context.copy()
        context['record_id'] = ids
        context['operation'] = type_of_operation

        return {
            'name': 'Generate SEPA',
            'type': 'ir.actions.act_window',
            'res_model': 'account.voucher.sepa',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'context': context,
            'target': 'new',
        }

    def _get_iban(self, cr, uid, ids, field_name, arg, context=None):
        """Override the iban function field set by account_streamline to add
        bank information.
        """

        ret = super(account_voucher, self)._get_iban(
            cr, uid, ids, field_name, arg, context=context
        )

        # FIXME avoid using browse in for
        for voucher_id in ret:
            voucher = self.browse(cr, uid, [voucher_id], context=context)[0]
            bank = voucher.partner_bank_id
            if bank:
                ret[voucher_id] = ret[voucher_id] + bank.acc_number

        return ret

    def _get_rem_letter_bot(self, cr, uid, ids, field_name, arg, context=None):
        """Override the remittance_letter_bottom function field set by
        account_streamline to add SEPA information.
        """

        ret = super(account_voucher, self)._get_rem_letter_bot(
            cr, uid, ids, field_name, arg, context=context
        )

        # Grab the date format for the context 'lang'
        pool_lang = self.pool['res.lang']
        lang = context and context.get('lang', 'en_US') or 'en_US'
        lang_ids = pool_lang.search(cr, uid, [('code', '=', lang)])
        lang_obj = pool_lang.browse(cr, uid, lang_ids[0])
        date_format = lang_obj.date_format

        for voucher_id in ret:
            voucher = self.browse(cr, uid, [voucher_id], context=context)[0]
            if voucher.batch_id:
                # Transform into a datetime object
                date = datetime.datetime.strptime(
                    voucher.batch_id.execution_date,
                    DEFAULT_SERVER_DATE_FORMAT)
                # Reform datetime correctly (lang dependent)
                pretty_date = datetime.datetime.strftime(
                    date, date_format)
                ret[voucher_id] = ret[voucher_id] + '''
                <h2 class="remittance_letter_bottom">
                    %s<br/>
                    %s<br/>
                    %s
                </h2>
                ''' % (_('Sepa:'),
                       voucher.batch_id.wording,
                       pretty_date)

        return ret

    def _get_sepa_valid(self, cr, uid, ids, fields, arg, context):
        voucher_brs = self.browse(cr, uid, ids, context=context)
        res = {}
        for voucher_br in voucher_brs:
            res[voucher_br.id] = bool(voucher_br.partner_bank_id)
        return res

    _columns = {
        'iban': fields.function(
            _get_iban,
            method=True,
            type='char',
        ),
        'remittance_letter_bottom': fields.function(
            _get_rem_letter_bot,
            method=True,
            type='text',
        ),

        # This field allows us to force the user to select only one account to
        # pay instead of always choosing the first bank account of the partner
        "sepa_valid": fields.function(
            _get_sepa_valid,
            type="boolean",
            method=True,
            string="Valid for SEPA payments"
        ),
        "partner_bank_id": fields.many2one(
            "res.partner.bank",
            "Partner Bank",
            domain="[('partner_id', '=', partner_id)]"
        ),
        "batch_id": fields.many2one(
            "account.voucher.sepa_batch",
            "Sepa Batch"
        ),
    }

    def cancel_voucher(self, cr, uid, ids, context=None):
        data = self.read(cr, uid, ids, ['batch_id'], context=context)
        for d in data:
            if d['batch_id']:
                raise osv.except_osv(
                    _(u"Error"),
                    _(u"You can't cancel a voucher attached to a batch.")
                )
        return super(account_voucher, self).cancel_voucher(
            cr, uid, ids, context=context
        )
