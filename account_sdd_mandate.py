# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 XCG Consulting
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


class account_sdd_mandate(osv.Model):
    """
    Represents the mandate document used to generate SDD SEPA payments
    """
    _name = 'account.sdd.mandate'

    def create(self, cr, uid, vals, context=None):
        if(not vals['ultimate_debtor_id']):
            vals['ultimate_debtor'] = vals['debtor']

        if(not vals['ultimate_creditor_id']):
            vals['ultimate_creditor'] = vals['ultimate_creditor']

        res_partner_osv = self.pool['res.partner']
        debtor = res_partner_osv.browse(cr, uid, [vals['ultimate_debtor_id']],
                                        context=context)[0]

        if not debtor.bank_ids:
            raise osv.except_osv('Error', _(
                'No bank accounts associated with {}').format(debtor)
            )
        vals['debtor_account_id'] = debtor.bank_ids[0].id
        vals['debtor_agent_id'] = debtor.bank_ids[0].bank.id

        return super(account_sdd_mandate, self).create(cr, uid, vals,
                                                       context=context)

    def get_sequence_type(self, cr, uid, id, number, context=None):
        """
        Returns the 'sequence type' of the SDD SEPA mandate.
        This value depends on the number of times this mandate was
        used in the context of a 'payment information' block.

        :param number: integer greater or equal to one,
                       increment this value for each batch
        :return: string, one of 'OOFF', 'RCUR', 'FRST', 'FNAL'
        """
        mandate_obj = self.pool['account.sdd.mandate']
        mandate_id = self.browse(cr, uid, id, context)

        if mandate_obj.sequence_type == 'recurring':
            count = mandate_obj.count + number
            if mandate_id.count == 0:
                seq_type = 'RCUR'
            elif mandate_id.count and count < mandate_id.count:
                seq_type = 'RCUR'
            else:
                seq_type = 'FNAL'
        else:
            seq_type = 'OOFF'

        return seq_type

    _columns = {
        'active': fields.boolean(
            string='Active',
        ),
        'identification': fields.char(
            string='Mandate Identification',
            size=128,
            required=True,
        ),
        'name': fields.related(
            'identification',
            type='char',
        ),
        'debtor_id': fields.many2one(
            'res.partner',
            string='Debtor',
            required=True,
        ),
        'debtor_account_id': fields.many2one(
            'res.partner.bank',
            string='Debtor Account',
            domain='[("partner_id", "=", debtor_id)]',
        ),
        'debtor_agent_id': fields.many2one(
            'res.bank',
            string='Financial Institution',
        ),
        'creditor_id': fields.many2one(
            'res.partner',
            string='Creditor Name',
            required=True,
        ),
        'count': fields.integer(
            string='Count',
            help='Number of times this mandate has been used'
        ),
        # TODO remove this field
        'sequence_type': fields.selection(
            [('one_off', 'One Off'),
             ('recurring', 'Recurring')],
            string='Sequence Type',
        ),
        'date_of_signature': fields.date(
            string='Date of Signature',
            required=True,
        ),
        'ultimate_debtor_id': fields.many2one(
            'res.partner',
            string='Ultimate Debtor',
            help='Can be the same as the Debtor',
            domain='''[
                "|",
                    ("id", "=", debtor_id),
                    ("id", "child_of", "debtor_id")
            ]''',
        ),
        'ultimate_creditor_id': fields.many2one(
            'res.partner',
            string='Ultimate Debtor',
            help='Can be the same as the Creditor',
            domain='''[
                "|",
                    ("id", "=", creditor_id),
                    ("id", "child_of", "creditor_id")
            ]''',
        ),
        'amends_mandate': fields.boolean(
            string='Amends another mandate',
            help='Means that this mandate replace another if ticked'
        ),
        'original_mandate_id': fields.many2one(
            'account.sdd.mandate',
            string='Original Mandate',
            help='Must be specified if the mandate is the'
                 'amendment of another',
        )
    }

    _defaults = {
        'active': True,
    }

    def _check_original_mandate(self, cr, uid, ids, context=None):
        """
        Makes sure that 'original_mandate_id' is filled in when
        'ammends_mandate' is  checked
        """
        for record in self.browse(cr, uid, ids, context=context):
            if record.amends_mandate and not record.original_mandate_id:
                return False
        return True

    _constraints = [
        (_check_original_mandate,
         'Please specify mandate',
         ['amends_mandate', 'original_mandate_id'])
    ]
