# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-2014 XCG Consulting (http://odoo.consulting/)
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

{
    "name": "Account Voucher SEPA",
    "version": "1.7",
    "author": "XCG Consulting",
    "website": "http://odoo.consulting/",
    'category' : 'Accounting & Finance',
    "description": """Account Voucher Payment SEPA Plugin for Open ERP.
    Currently only supports pain.001.001.03 with outbound bank transfer.
    """,

    "depends": [
        'base',
        'account_credit_transfer',
        'account_voucher',
        'account_streamline',
        'analytic_structure',
        'base_iban',
        'document',
    ],

    "data": [
        'account_voucher.xml',
        'sepa_batch.xml',
        'data/batch_sequence.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
    ],

    'demo_xml': [],
    'test': [],
    'installable': True,
    'active': False,
    'external_dependencies': {
        'python': ['genshi']
    }
}
