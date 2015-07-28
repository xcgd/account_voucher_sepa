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
            [('first', 'FRST'),
             ('recurring', 'RCUR'),
             ('final', 'FNAL'),
             ('one_off', 'OOFF')],
            string='Creditor Name',
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
        )
    }
