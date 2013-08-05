from openerp.osv import osv
from openerp.tools.translate import _
from genshi.template import TemplateLoader
import os
import datetime
import base64

TEMPLATE = "sepa_tpl.xml"


class account_voucher(osv.Model):
    _name = "account.voucher"
    _inherit = "account.voucher"

    def generate_sepa(self, cr, uid, ids, context=None):
        items = self.browse(cr, uid, ids, context=context)

        ir_attachment_osv = self.pool.get("ir.attachment")
        payment_mode_osv = self.pool.get("payment.mode")

        template_loader = TemplateLoader(
            [os.path.dirname(os.path.abspath(__file__))])
        tpl = template_loader.load(TEMPLATE)

        now = datetime.datetime.now()
        now_str = now.strftime("%Y%m%d%H%M%S")

        for voucher in items:
            if not len(voucher.partner_id.bank_ids):
                raise osv.except_osv(
                    _("No bank account for Partner"),
                    _("This partner should have a bank account."))

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
