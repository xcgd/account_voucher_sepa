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


class account_sepa_purpose(osv.Model):
    """
    Represents the payment category purpose code for SEPA payments specified
    by ISO 20022.
    """
    _name = 'account.sepa.purpose'

    _columns = {
        'code': fields.char(
            size=8,
            string='Code',
            required=True,
        ),
        'name': fields.char(
            size=64,
            string='Name',
            required=True,
        ),
    }
