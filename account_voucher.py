from openerp.osv import osv, fields
from openerp.tools.translate import _
from genshi.template import TemplateLoader
import os
import datetime
import base64
import openerp.addons.decimal_precision as dp
from lxml import etree

TEMPLATE = "sepa_tpl.xml"


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
    }

    def generate_sepa(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        
        #Get data from wizard and save voucher ids
        data = self.read(cr, uid, ids, [], context=context)[0]
        if not data['voucher_ids']:
            return {'type': 'ir.actions.act_window_close'}
        voucher_ids = data['voucher_ids']

        batch_osv = self.pool.get("account.voucher.sepa_batch")
        account_voucher_osv = self.pool.get("account.voucher")
        ir_attachment_osv = self.pool.get("ir.attachment")
        payment_mode_osv = self.pool.get("payment.mode")

        list_voucher = account_voucher_osv.browse(cr, uid, voucher_ids, context=context)

        # Loading sepa template
        template_loader = TemplateLoader(
            [os.path.dirname(os.path.abspath(__file__))])
        tpl = template_loader.load(TEMPLATE)

        now = datetime.datetime.now()
        now_str = now.strftime("%Y%m%d%H%M%S")

        total_amount = 0.0
        list_bank = []
        list_lines = []
    
        # Verifying that : vouchers are posted
        #                  sepa not already generated
        #                  creditor bank exists
        #                  debtor bank exists
        for voucher in list_voucher:
            if voucher.state != 'posted':
                raise osv.except_osv(
                    _("State error"),
                    _("The voucher must be posted"
                      " before generating SEPA file")
                )
            if voucher.batch_id:
                raise osv.except_osv(
                    _("Integrity error"),
                    _("This voucher is already attached to a batch.")
                )
            total_amount += voucher.amount
            
            if not voucher.partner_bank_id:
                raise osv.except_osv(
                    _("Bank error"),
                    _("Please set a bank account on the partner %s." %
                      voucher.partner_id.name)
                )
            list_lines.append(voucher.line_ids)
            payment_mode_ids = payment_mode_osv.search(
                cr, uid,
                [("journal", "=", voucher.journal_id.id)],
                context=context)
            payment_modes = payment_mode_osv.browse(
                cr, uid,
                payment_mode_ids,
                context=context)
            banks = [pm.bank_id for pm in payment_modes]
            
            if not len(banks):
                banks = [bank
                         for bank in voucher.company_id.bank_ids
                         if bank.journal_id.id==voucher.journal_id.id]

            if len(banks):
                bank = banks[0]
            else:
                raise osv.except_osv(
                    _("No origin bank account found"),
                    _("Bank account for journal %s is not found" %
                      voucher.journal_id.name))
            if not bank.bank_bic:
                raise osv.except_osv(
                    _("Bank BIC"),
                    _("Please set the bank BIC for the bank %s" %
                      bank.name))

        # Save the total amount of all vouchers selected
        batch_vals = {
            'amount': total_amount,
            'creditor_bank_id': bank.id,
        }

        # Create the batch, associate all voucher with that batch
        batch_id = batch_osv.create(cr, uid, batch_vals, context=context)
        account_voucher_osv.write(
            cr, uid,
            voucher_ids,
            {'batch_id': batch_id},
            context=context
        )

        # Launch template to generate SEPA file
        content = str(
            tpl.generate(total_amount=total_amount,
                         company_name=list_voucher[0].company_id.name,
                         debtor_bank=bank,
                         list_voucher=list_voucher)
        )

        # We get the auto-generated name of the batch created
        batch_br = batch_osv.browse(cr, uid, [batch_id], context=context)[0]

        fname = "PAYMENT_%s_%s.xml" % (
            batch_br.name.replace(" ", "_"), now_str)

        att_values = dict(datas=base64.encodestring(content),
                            datas_fname=fname,
                            name=fname,
                            res_id = batch_id,
                            res_model = "account.voucher.sepa_batch")

        ir_attachment_osv.create(cr, uid, att_values, context=context)
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

    def onchange_voucher_ids(self, cr, uid, ids, voucher_ids, context=None):
        result = {'value': {'batch_valid': False}}
        return result


class account_voucher(osv.Model):
    _name = "account.voucher"
    _inherit = "account.voucher"

    #This method add a default value to partner_bank_id
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

    def _get_sepa_valid(self, cr, uid, ids, fields, arg, context):
        voucher_brs = self.browse(cr, uid, ids, context=context)
        res = {}
        for voucher_br in voucher_brs:
            res[voucher_br.id] = bool(voucher_br.partner_bank_id)
        return res

    #This field allow us to force the user to select only one account to pay
    # instead of always choose the first bank account of the partner
    _columns = {
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

