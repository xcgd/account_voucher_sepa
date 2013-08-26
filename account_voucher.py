from openerp.osv import osv, fields
from openerp.tools.translate import _
from genshi.template import TemplateLoader
import os
import datetime
import base64

TEMPLATE = "sepa_tpl.xml"


class account_voucher_sepa(osv.TransientModel):
    _name = "account.voucher.sepa"
    _columns = {
        'group_suppliers': fields.boolean("Group suppliers"),
    }

    def _group_by_suppliers(self, items):

        return items

#THIS FUNCTION WILL REPLACE THE FIRST ONE WHEN FINISHED

#    def generate_sepa_v2(self, cr, uid, ids, context=None):
#        if not context:
#            context = {}
#
#        active_ids = context.get("active_ids")
#
#        batch_osv = self.pool.get("account.voucher.sepa_batch")
#        batch_line_osv = self.pool.get("account.voucher.sepa_batch.line")
#        ir_attachement_osv = self.pool.get("ir.attachment")
#        payment_mode_osv = self.pool.get("payment.mode")
#        account_voucher_osv = self.pool.get("account.voucher")
#        account_voucher_sepa_osv = self.pool.get("account.voucher.sepa")
#
#        account_voucher_sepa_br = account_voucher_sepa_osv.browse(
#            cr, uid, ids, context=context
#        )[0]
#        if account_voucher_sepa_br.group_suppliers:
#            items = self._group_by_suppliers(cr, uid, active_ids, context)
#        else:
#            items = account_voucher_osv.browse(
#                cr, uid, active_ids, context=context
#            )
#        
#        template_loader = TemplateLoader(
#            [os.path.dirname(os.path.abspath(__file__))]
#        )
#        tpl = template_loader.load(TEMPLATE)
#
#        now = datetime.datetime.now()
#        now_str = now.strftime("%Y%m%d%H%M%S")
#        for voucher in items:

    def generate_sepa(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        active_ids = context.get("active_ids")
        account_voucher_osv = self.pool.get("account.voucher")
        items = account_voucher_osv.browse(cr, uid, active_ids, context=context)

        ir_attachment_osv = self.pool.get("ir.attachment")
        payment_mode_osv = self.pool.get("payment.mode")

        template_loader = TemplateLoader(
            [os.path.dirname(os.path.abspath(__file__))])
        tpl = template_loader.load(TEMPLATE)

        now = datetime.datetime.now()
        now_str = now.strftime("%Y%m%d%H%M%S")

        #We sort to group faster the voucher by partner_id
        items = sorted(items, key=lambda i: i.partner_id.id)
        items = self._group_by_suppliers(items)

        for voucher in items:
            if voucher.state != 'posted':
                raise osv.except_osv(
                    _("State error"),
                    _("The voucher must be posted"
                      " before generating SEPA file"))

            payment_mode_ids = payment_mode_osv.search(
                cr, uid,
                [("journal", "=", voucher.journal_id.id)],
                context=context)
            payment_modes = payment_mode_osv.browse(
                cr, uid,
                payment_mode_ids,
                context=context)
            # We get the bank account of the payment mode setted
            banks = [pm.bank_id for pm in payment_modes]

            # if no payment mode setted, we get company bank account
            if not len(banks):
                if not voucher.company_id or not voucher.company_id.bank_ids:
                    raise osv.except_osv(
                        _("No bank account for your Company"),
                        _("Your company should have a bank account."))
                banks = [
                    company_bank
                    for company_bank in voucher.company_id.bank_ids
                    if company_bank.journal_id.id == voucher.journal_id.id]

            if len(banks):
                company_bank = banks[0]
            else:
                raise osv.except_osv(
                    _("No origin bank account found"),
                    _("Bank account for journal %s is not found" %
                      voucher.journal_id.name))
            if not company_bank.bank_bic:
                raise osv.except_osv(
                    _("Bank BIC"),
                    _("Please set the bank BIC for the bank %s" %
                      company_bank.name))

            lines = voucher.line_ids
            content = str(tpl.generate(bank=company_bank,
                                       voucher=voucher,
                                       lines=lines))
            fname = "PAYMENT_%s_%s.xml" % (
                voucher.partner_id.name.replace(" ", "_"), now_str)
            att_values = dict(datas=base64.encodestring(content),
                              datas_fname=fname,
                              name=fname,
                              res_id=voucher.id,
                              res_model="account.voucher")
            ir_attachment_osv.create(cr, uid, att_values, context=context)
            # don't write for now (testing)


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

    #This field allow us to force the user to select only one account to pay
    # instead of always choose the first bank account of the partner
    _columns = {
        "partner_bank_id": fields.many2one(
            "res.partner.bank",
            "Patner Bank",
            domain="[('partner_id', '=', partner_id)]"
        )
    }

