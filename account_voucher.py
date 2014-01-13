from openerp.osv import osv, fields
from openerp.tools.translate import _
from genshi.template import TemplateLoader, TemplateNotFound, TemplateSyntaxError
import os
import datetime
import base64
from lxml import etree

#TEMPLATE = "sepa_tpl.xml"


class account_voucher_sepa(osv.TransientModel):
    _name = "account.voucher.sepa"

    _columns = {
        'group_suppliers': fields.boolean(_("Group suppliers")),
        'voucher_ids': fields.many2many(
            "account.voucher",
            'account_voucher_rel_',
            'voucher_id',
            'sepa_id',
            _('Lines'),
        ),
        'wording': fields.char('Wording', size=20, required=True),
        'execution_date': fields.date('Execution Date', required=True),
    }


    def generate_sepa(self, cr, uid, batch_id,
                      list_voucher, date, context=None):
        #New version using account_credit_transfer

        batch_osv = self.pool.get("account.voucher.sepa_batch")
        batch_br = batch_osv.browse(cr, uid, [batch_id], context=context)[0]

        data = {
            'total_amount': batch_br.amount,
            'company_name': list_voucher[0].company_id.name,
            'debtor_bank': batch_br.creditor_bank_id,
            'list_voucher': list_voucher,
            'batch': batch_br,
            'date': date,
        }

        ct_config_osv = self.pool.get("account_credit_transfer.config")
        ct_config_osv.generate_credit_transfer_file(
            cr, uid, data, context=context
        )


#    def generate_sepa(self, cr, uid, batch_id, list_voucher, date, context=None):
#        # We get the auto-generated name of the batch created
#
#        batch_osv = self.pool.get("account.voucher.sepa_batch")
#        batch_br = batch_osv.browse(cr, uid, [batch_id], context=context)[0]
#
#        tpl = self.__load_sepa_template()
#
#        # Launch template to generate SEPA file
#        content = str(
#            tpl.generate(total_amount=batch_br.amount,
#                         company_name=list_voucher[0].company_id.name,
#                         debtor_bank=batch_br.creditor_bank_id,
#                         list_voucher=list_voucher,
#                         batch=batch_br,
#                         date=date,
#                         )
#        )
#
#        print content
#
#        fname = "PAYMENT%s%s.xml" % (
#            batch_br.name.replace(" ", ""), date)
#
#        att_values = dict(datas=base64.encodestring(content),
#                            datas_fname=fname,
#                            name=fname,
#                            res_id=batch_id,
#                            res_model="account.voucher.sepa_batch")
#
#        ir_attachment_osv = self.pool.get("ir.attachment")
#        ir_attachment_osv.create(cr, uid, att_values, context=context)

    def __get_data_from_wizard(self, cr, uid, ids, context=None):
        data = self.read(cr, uid, ids, [], context=context)[0]
        if not data['voucher_ids']:
            return False, False
        return True, data

    def __load_sepa_template(self):
        template_loader = TemplateLoader(
            [os.path.dirname(os.path.abspath(__file__))])
        try:
            return template_loader.load(TEMPLATE)
        except TemplateNotFound as e:
            raise osv.except_osv(_('Template Not Found'), e)
        except TemplateSyntaxError as e:
            raise osv.except_osv(_('Template Syntax Error'), e)

    def __get_bank_id(self, cr, uid, ids, voucher, context=None):
        # Search with payment modes
        payment_mode_osv = self.pool.get("payment.mode")
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

        voucher_ids = data['voucher_ids']

        batch_osv = self.pool.get("account.voucher.sepa_batch")
        account_voucher_osv = self.pool.get("account.voucher")

        list_voucher = account_voucher_osv.browse(
            cr, uid, voucher_ids, context=context
        )

        # Calcul the total amount of all selected vouchers

        total_amount = 0.0

        for voucher in list_voucher:
            total_amount += voucher.amount

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
        account_voucher_osv.write(
            cr, uid,
            voucher_ids,
            {'batch_id': batch_id},
            context=context
        )

        now_str = datetime.datetime.now().strftime("%Y-%m-%d")

        self.generate_sepa(cr, uid, batch_id, list_voucher, now_str, context=context)

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
        if not 'active_ids' in context:
            return {}
        vals = {}
        voucher_lines = [(6, 0, context['active_ids'])]
        vals['voucher_ids'] = voucher_lines
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

        if not context or not 'active_ids' in context:
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
            bank_osv = self.pool.get("res.partner.bank")
            bank_id = bank_osv.search(
                cr, uid, [('partner_id', '=', partner_id)], context=context
            )
            if bank_id:
                res['value']['partner_bank_id'] = bank_id[0]

        return res

    def validate_selected(self, cr, uid, ids, context=None):
        if not 'active_ids' in context:
            raise osv.except_osv(
                _("Integrity Error"),
                _("You must select one voucher to generate SEPA file.")
            )
        this_brs = self.browse(cr, uid, context['active_ids'], context=context)
        for this_br in this_brs:
            this_br._workflow_signal('proforma_voucher')
        return {}

    def launch_wizard_sepa(self, cr, uid, ids, context=None):
        if not 'active_ids' in context:
            raise osv.except_osv(
                _("Integrity Error"),
                _("You must select one voucher to generate SEPA file.")
            )
        this_brs = self.browse(cr, uid, context['active_ids'], context=context)
        for this_br in this_brs:
            if this_br.state != 'posted':
                raise osv.except_osv(
                    _("State error"),
                    _("The voucher %s must be posted"
                      " before generating SEPA file")
                )
            if this_br.batch_id:
                raise osv.except_osv(
                    _("Integrity error"),
                    _("The voucher %s is already attached to a batch." %
                      this_br.number)
                )
            if not this_br.partner_bank_id:
                raise osv.except_osv(
                    _("Bank error"),
                    _("Please set a bank account on the partner %s." %
                      this_br.partner_id.name)
                )

        ir_ui_view_osv = self.pool.get('ir.ui.view')
        view_id = ir_ui_view_osv.search(
            cr, uid,
            [('name', '=', 'view.account.voucher.sepa')],
            context=context
        )

        context['record_id'] = ids

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

    def _get_rem_letter_bot(self, cr, uid, ids, field_name, arg, context):
        ''' Override the remittance_letter_bottom function field set by
        account_streamline to add SEPA information. '''

        res = super(account_voucher, self)._get_rem_letter_bot(cr, uid, ids,
            field_name, arg, context)

        for id in res:
            voucher = self.browse(cr, uid, [id], context=context)[0]
            if voucher.batch_id:
                res[id] = res[id] + '''
                <h2 class="remittance_letter_bottom">
                    %s<br/>
                    %s<br/>
                    %s
                </h2>
                ''' % (_('Sepa:'),
                       voucher.batch_id.wording,
                       voucher.batch_id.execution_date)

        return res

    def _get_sepa_valid(self, cr, uid, ids, fields, arg, context):
        voucher_brs = self.browse(cr, uid, ids, context=context)
        res = {}
        for voucher_br in voucher_brs:
            res[voucher_br.id] = bool(voucher_br.partner_bank_id)
        return res

    _columns = {
        'remittance_letter_bottom': fields.function(_get_rem_letter_bot,
                                            type='text',
                                            method=True),
        # This field allows us to force the user to select only one account to
        # pay instead of always choosing the first bank account of the partner
        "sepa_valid": fields.function(
            _get_sepa_valid,
            type="boolean",
            method=True,
            string=_("Valid for SEPA payments")
        ),
        "partner_bank_id": fields.many2one(
            "res.partner.bank",
            _("Patner Bank"),
            domain="[('partner_id', '=', partner_id)]"
        ),
        "batch_id": fields.many2one(
            "account.voucher.sepa_batch",
            _("Sepa Batch")
        ),
    }

