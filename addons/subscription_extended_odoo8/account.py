
from openerp.osv import osv, fields


class account_invoice(osv.osv):
    _inherit = "account.invoice"
    _columns = {
                    'comment': fields.text('Notes'),
    }
account_invoice()
