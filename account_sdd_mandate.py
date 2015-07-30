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

    def write(self, cr, uid, vals, context=None):
        if(not vals['ultimate_debtor']):
            vals['ultimate_debtor'] = vals['debtor']

        if(not vals['ultimate_creditor']):
            vals['ultimate_creditor'] = vals['ultimate_creditor']

        return super(account_sdd_mandate, self).write(self, cr, uid, vals,
                                                      context)

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
        'identification': fields.char(
            string='Mandate Identification',
            size=128,
        ),
        'debtor': fields.many2one(
            'res.partner',
            string='Debtor',
        ),
        'debtor_account': fields.many2one(
            'account.account',
            string='Debtor Account',
        ),
        'debtor_agent': fields.many2one(
            'res.partner',
            string='Financial Institution',
        ),
        'creditor': fields.many2one(
            'res.partner',
            string='Creditor Name',
        ),
        'count': fields.integer(
            string='Count',
            help='Number of times this mandate has been used'
        ),
        'sequence_type': fields.selection(
            [('one_off', 'One Off'),
             ('recurring', 'Recurring')],
            string='Sequence Type',
        ),
        'date_of_signature': fields.date(
            string='Date of Signature',
        ),
        'ultimate_debtor': fields.many2one(
            'res.partner',
            string='Ultimate Debtor',
            help='Can be the same as the Debtor',
        ),
        'ultimate_creditor': fields.many2one(
            'res.partner',
            string='Ultimate Debtor',
            help='Can be the same as the Creditor',
        ),
        'amends_mandate': fields.boolean(
            string='Amends another mandate',
            help='Means that this mandate replace another if ticked'
        ),
        'original_mandate': fields.many2one(
            'account.sdd.mandate',
            string='Original Mandate',
            help='Must be specified if the mandate is the'
                 'amendment of another',
        )
    }