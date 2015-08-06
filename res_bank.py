# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-2015 XCG Consulting
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
import datetime
from lxml import etree
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
import openerp.addons.decimal_precision as dp


class res_bank:
    _name = "res.bank"

    _columns = {
        'direct_debit_parser': fields.many2one(
            'account_credit_transfer.parser',
            string='Direct Debit Parser',
            help='The parser to use for creating direct debit payment files',
        ),
        'transfer_parser': fields.many2one(
            'account_credit_transfer.parser',
            string='Transfer Parser',
            help='The parser to use for creating transfer payment files',
        ),
    }

