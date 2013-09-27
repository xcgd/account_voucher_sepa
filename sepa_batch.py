from openerp.osv import osv, fields

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
        'wording': fields.char("Wording", size=256),
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
