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
        sepas = self.browse(cr, uid, ids, context=context)
        vouchers = []

        for sepa in sepas:
            vouchers.extend(sepa.line_ids)

        emails = {}  # email -> voucher list
        for voucher in vouchers:
            if voucher.partner_id.email:
                if voucher.partner_id.email not in emails:
                    emails[voucher.partner_id.email] = []
                emails[voucher.partner_id.email].append(voucher)

        # TODO don't hardcode / use an email template
        email_from = 'billing@numergy.com'
        subject = 'Avis de règlement'
        message = 'Cher fournisseur, veuillez prendre connaissance en pièce jointe du détail du règlement effectué sur votre compte bancaire.'

        for email, vouchers in emails.iteritems():
            attachments = [self._get_attachment(cr, uid, voucher, context)
                           for voucher in vouchers]
            self.send_email(cr, uid, [vouchers[0].id], subject, message,
                            email_from, email, attachments, 'account.voucher',
                            context=context)

    def _get_attachment(self, cr, uid, voucher, context):
        att_osv = self.pool.get('ir.attachment')
        att_id = att_osv.search(
            cr, uid,
            [('res_id', '=', voucher.id), ('name', '=like', 'AR-%')],
            context=context
        )

        if not att_id:
            raise osv.except_osv('Error', 'No Remittance Letter found for '
                                 'the specified vouchers; please generate '
                                 'them then re-run this.')
            # TODO generate remittance letter

        return att_id[0]

    # TODO move elsewhere
    def send_email(self, cr, uid, ids, subject, message, email_from, email_to,
                   attachments, model, context=None):
        print 'sending email from %s to %s, msg=%s, attachments=%s' % (
            email_from, email_to, subject, str(attachments))
        mail_server_obj = self.pool.get('ir.mail_server')
        mail_message_obj = self.pool.get('mail.message')
        mail_mail_obj = self.pool.get('mail.mail')
        for id in ids:
            mail_message_id = mail_message_obj.create(cr, uid, {
                'attachment_ids': [(6, 0, attachments)],  # TODO more atts
                'body': message,
                'email_from': email_from,
                'model': model,
                'res_id': id,
                'subject': subject,
            }, context=context)
            mail_server_ids = mail_server_obj.search(cr, uid, [], context=context)
            mail_mail_id = mail_mail_obj.create(cr, uid, {
                'body_html': message,
                'email_from': email_from,
                'email_to': email_to,
                'mail_message_id': mail_message_id,
                'mail_server_id': mail_server_ids and mail_server_ids[0],
                'state': 'outgoing',
            }, context=context)
            if mail_mail_id:
                mail_mail_obj.send(cr, uid, [mail_mail_id], context=context)


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
