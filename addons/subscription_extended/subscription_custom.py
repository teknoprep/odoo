# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from openerp.osv import fields,osv
from openerp.tools.translate import _
import time
from mx import DateTime
import mx.DateTime
from datetime import datetime
import openerp.addons.decimal_precision as dp
from openerp import netsvc


class subscription_subscription(osv.osv):
    _inherit = "subscription.subscription"
    _description = "Inherit Subscription"
    
    def onchange_source_doc(self, cr, uid, ids, source_id, context=None):
        if source_id:
#            sub_doc_brw = self.pool.get('subscription.document').browse(cr, uid, source_id)
#            rec_model_name = sub_doc_brw.model.model
            model_name = 'sale.order.template'
        return {'value': {'temp_model': model_name}}
    
    def onchange_template_first(self, cr, uid, ids, template_id1, source_doc_id, context=None):
        order_template = self.pool.get('sale.order.template')
        order_line = []
        order = []
        part_ids = []
        res = {}
        rec_model_name = ''
        if template_id1:
            order_brw = order_template.browse(cr, uid, template_id1)
            for order_line_obj in order_brw.sale_order_line:
                order_data = {
                    'name': order_line_obj.name,
                    'product_uom': order_line_obj.product_uom.id,
                    'price_unit': order_line_obj.price_unit,
                    'product_id': order_line_obj.product_id.id,
                    'product_uom_qty': order_line_obj.product_uom_qty,
                    'tax_id': [(6, 0, [x.id for x in order_line_obj.tax_id])],
                    'discount': order_line_obj.discount,
                    }
                order_line.append((0,0,order_data))
                
            data = {
                'subcription_doc_id': order_brw.subcription_doc_id.id,
                'name': order_brw.name,
                'date_order': order_brw.date_order,
                'shop_id': order_brw.shop_id.id,
                'pricelist_id': order_brw.pricelist_id.id,
                'model_name': order_brw.model_name,
                'invoice_type': order_brw.invoice_type,
                'sale_order_line': order_line,
                }
            order.append((0,0,data))
            
            
            if source_doc_id:
                sub_doc_brw = self.pool.get('subscription.document').browse(cr, uid, source_doc_id)
                rec_model_name = sub_doc_brw.model.model
                
            """Here we will create domain based on invoice type"""
            if order_brw.invoice_type == 'in_invoice':
                part_ids = self.pool.get('res.partner').search(cr, uid, [('supplier','=',True)])
            elif order_brw.invoice_type == 'out_invoice' or rec_model_name == 'sale.order':
                part_ids = self.pool.get('res.partner').search(cr, uid, [('customer','=',True)])
            else:
                part_ids = self.pool.get('res.partner').search(cr, uid, [])
                
        res['template_ids1'] = order
        return {'value': res, 'domain': {'partner_id': [('id', 'in', part_ids)]}}
    
    
    _columns = {
            'doc_source': fields.reference('Source Document', selection=[], size=128, help="User can choose the source document on which he wants to create documents"),
            'source_doc_id': fields.many2one('subscription.document', 'Source Document', required=True),
            'template_order_id': fields.many2one('sale.order.template', 'Sale order'),
            'temp_model': fields.char('Temp Model', size=60),
            'template_ids1': fields.one2many('sale.order.template', 'sub_doc_id', 'Sale Order Template View '),
            'term_condition': fields.text('Term & Condition'),
            'doc_type': fields.char('Doc type', size=40),
            'notify_by_mail': fields.boolean('Notify By Mail', help='Use notify by mail to customer/supplier after create invoice'),
            'valid_invoice': fields.boolean('Validate', help='Use to confirm Invoice after create'),
            'payment_term': fields.many2one('account.payment.term', 'Payment Terms',
            help="If you use payment terms, the due date will be computed automatically at the generation "\
                "of accounting entries. If you keep the payment term and the due date empty, it means direct payment. "\
                "The payment term may compute several due dates, for example 50% now, 50% in one month."),
         }
    
    def set_done(self, cr, uid, ids, context=None):
        res = self.read(cr,uid, ids, ['cron_id'])
        ids2 = [x['cron_id'][0] for x in res if x['id']]
        self.pool.get('ir.cron').write(cr, uid, ids2, {'active':False, 'doall': False})
        self.write(cr, uid, ids, {'state':'done'})
        return True
    
    
    def set_process(self, cr, uid, ids, context=None):
        for row in self.read(cr, uid, ids, context=context):
            mapping = {'name':'name','interval_number':'interval_number','interval_type':'interval_type','exec_init':'numbercall','date_init':'nextcall'}
            res = {'model':'subscription.subscription', 'args': repr([[row['id']]]), 'function':'model_copy', 'priority':1, 'user_id':row['user_id'] and row['user_id'][0]}
            for key,value in mapping.items():
                res[value] = row[key]
            id = self.pool.get('ir.cron').create(cr, uid, res)
            self.write(cr, uid, [row['id']], {'cron_id':id, 'state':'running'})
        return True
    
    def model_copy(self, cr, uid, ids, context=None):
        for row in self.read(cr, uid, ids, context=context):
            if not row.get('cron_id',False):
                continue
            cron_ids = [row['cron_id'][0]]
            remaining = self.pool.get('ir.cron').read(cr, uid, cron_ids, ['numbercall'])[0]['numbercall']
            try:
                temp_id = row['template_ids1'][0]
                partner_id = row['partner_id'][0]
                model_name_template = row['temp_model']
                source_doc_id = row['source_doc_id'][0]
                sub_doc_obj = self.pool.get('subscription.document').browse(cr, uid, source_doc_id)
                id = sub_doc_obj.model.id
                model_name = sub_doc_obj.model.model
                model = self.pool.get(model_name)
            except:
                raise osv.except_osv(_('Wrong Source Document!'), _('Please provide another source document.\nThis one does not exist!'))

            default = {'state':'draft'}
            doc_obj = self.pool.get('subscription.document')
            document_ids = doc_obj.search(cr, uid, [('model.model','=',model_name)])
            doc = doc_obj.browse(cr, uid, document_ids)[0]
            for f in doc.field_ids:
                if f.value=='date':
                    value = time.strftime('%Y-%m-%d')
                else:
                    value = False
                default[f.field.name] = value

            state = 'running'
            
            # if there was only one remaining document to generate
            # the subscription is over and we mark it as being done
            if remaining == 1:
                state = 'done'
            
            if model_name_template == 'sale.order.template':
                
                part = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
                addr = self.pool.get('res.partner').address_get(cr, uid, [part.id], ['delivery', 'invoice', 'contact'])
                pricelist = part.property_product_pricelist and part.property_product_pricelist.id or False
                payment_term = part.property_payment_term and part.property_payment_term.id or False
                fiscal_position = part.property_account_position and part.property_account_position.id or False
                account_id = int(part.property_account_receivable.id)
                dedicated_salesman = part.user_id and part.user_id.id or uid
                val = {
                    'partner_invoice_id': addr['invoice'],
                    'partner_shipping_id': addr['delivery'],
                    'payment_term': payment_term,
                    'fiscal_position': fiscal_position,
                    'user_id': dedicated_salesman,
                }
                
                ### Browse template record to get values
                order_brw = self.pool.get(str(model_name_template)).browse(cr, uid, temp_id)
                
                ### Create Dictionary for parent record
                default.update({
                    'partner_id': partner_id,
                    'payment_term': row['payment_term'] and row['payment_term'][0],
                    })
                
                
                ### Here we have check which object should be used to create new record
                ### Based on that assign values 
                if model_name == 'sale.order':
                    default.update({'partner_shipping_id': val['partner_shipping_id'],
                                    'shop_id': order_brw.shop_id.id,
                                    'partner_invoice_id': val['partner_invoice_id'],
                                    'pricelist_id': order_brw.pricelist_id.id,
                                    'date_order': time.strftime('%Y-%m-%d'),})
                
                if model_name == 'account.invoice':
                    default.update({'name': '',
#                                    'date_invoice': order_brw.date_order, 
                                    'date_invoice': time.strftime('%Y-%m-%d'),
                                    'type': order_brw.invoice_type,
                                    'account_id': account_id,
                                    'comment': row['note'],
                                    'company_id': order_brw.shop_id.company_id.id})
                    print "default",default
                    if order_brw.invoice_type == 'out_invoice':
                        journal_ids = self.pool.get('account.journal').search(cr, uid,
                            [('type', '=', 'sale'), ('company_id', '=', order_brw.shop_id.company_id.id)],
                            limit=1)
                        if not journal_ids:
                            raise osv.except_osv(_('Error!'),
                                _('Please define sales journal for this company: "%s" (id:%d).') % (order_brw.shop_id.company_id.name, order_brw.shop_id.company_id.id))
                        default.update({'journal_id': journal_ids[0],})
                        
                    if order_brw.invoice_type == 'in_invoice':
                        journal_ids = self.pool.get('account.journal').search(cr, uid,
                            [('type', '=', 'purchase'), ('company_id', '=', order_brw.shop_id.company_id.id)],
                            limit=1)
                        if not journal_ids:
                            raise osv.except_osv(_('Error!'),
                                _('Please define purchase journal for this company: "%s" (id:%d).') % (order_brw.shop_id.company_id.name, order_brw.shop_id.company_id.id))
                        default.update({'journal_id': journal_ids[0],})
                        
                ### CREate parent record for SO, and invoice
                data_id = self.pool.get(str(model_name)).create(cr, uid, default)
                
                ### Now get values from template line to create order line (child records)
                for order_line_obj in order_brw.sale_order_line:
                    if model_name == 'sale.order':
                        order_data = {
                            'order_id': data_id,
                            'name': order_line_obj.name,
                            'product_uom': order_line_obj.product_uom.id,
                            'price_unit': order_line_obj.price_unit,
                            'product_id': order_line_obj.product_id.id,
                            'product_uom_qty': order_line_obj.product_uom_qty,
                            'tax_id': [(6, 0, [x.id for x in order_line_obj.tax_id])],
                            'discount': order_line_obj.discount,
                            }
                        self.pool.get('sale.order.line').create(cr, uid, order_data)
                    
                    if model_name == 'account.invoice':
                        product_account_id = order_line_obj.product_id.property_account_income and order_line_obj.product_id.property_account_income.id or False
                        if not product_account_id:
                            product_account_id = order_line_obj.product_id.categ_id.property_account_income_categ.id
                        if not product_account_id:
                            raise osv.except_osv(_('Error!'),
                                    _('Please define income account for this product: "%s" (id:%d).') % \
                                        (order_line_obj.product_id.name, order_line_obj.product_id.id,))
                        order_data = {
                            'invoice_id': data_id,
                            'name': order_line_obj.name,
                            'uos_id': order_line_obj.product_uom.id,
                            'account_id': product_account_id,
                            'price_unit': order_line_obj.price_unit,
                            'product_id': order_line_obj.product_id.id,
                            'quantity': order_line_obj.product_uom_qty,
                            'invoice_line_tax_id':[(6, 0, [x.id for x in order_line_obj.tax_id])],
                            'discount': order_line_obj.discount,
                            }
                        self.pool.get('account.invoice.line').create(cr, uid, order_data)
                        
                if model_name == 'account.invoice':
                    ### Pass signal to confirm the invoice and show in open state
                    if row['valid_invoice']:
                        wf_service = netsvc.LocalService("workflow")
                        wf_service.trg_validate(uid, 'account.invoice', data_id, 'invoice_open', cr)
                    
                    """ Partner notify by mail after create invoice"""
                    email_template_obj = self.pool.get('email.template')
                    if row['notify_by_mail']:
                        template = self.pool.get('ir.model.data').get_object(cr, uid, 'account', 'email_template_edi_invoice')
                        email_template_obj.write(cr,uid,[template.id],{
                                                       'email_to':part.email,
                                                       })  
                        email_template_obj.send_mail(cr, uid, template.id, data_id , True, context=context)
                            
            self.pool.get('subscription.subscription.history').create(cr, uid, {'subscription_id': row['id'], 'date':time.strftime('%Y-%m-%d %H:%M:%S'), 'document_id': model_name+','+str(data_id)})
            self.write(cr, uid, [row['id']], {'state':state})
        return True
    
subscription_subscription()


""" Order line Template """
class sale_order_line_template(osv.osv):
    _name = "sale.order.line.template"
    _description = "Order Line"
    
    def product_id_change(self, cr, uid, ids, product_id, inv_type, context=None):
        res = {}
        if product_id:
           product_brw = self.pool.get('product.product').browse(cr, uid, product_id)
           res = {
            'name': product_brw.name,
            'product_uom': product_brw.uom_id.id,
            'price_unit': product_brw.list_price,
            }
           
           """For supplier invoice product price and unit of measure"""
           if inv_type == 'in_invoice':
               res.update({'price_unit': product_brw.standard_price,
                           'product_uom': product_brw.uom_po_id.id})
        return {'value': res} 
    
    def _amount_line(self, cr, uid, ids, field_name, arg, context=None):
        """Here calculate subtotal"""
        res = {}
        subtotal = 0.0
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            subtotal = line.product_id.list_price * line.product_uom_qty
            res[line.id] = subtotal
        return res
    
    _columns = {
        'order_temp_id': fields.many2one('sale.order.template','Sale Order template'),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'name': fields.char('Description', size=50),
        'product_uom_qty': fields.float('Quantity', digits_compute= dp.get_precision('Product UoS'), required=True),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure ', required=True),
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Product Price')),
        'tax_id': fields.many2many('account.tax', 'order_template_tax', 'order_line_id', 'tax_id', 'Taxes',),
        'discount': fields.float('Discount (%)', digits_compute= dp.get_precision('Discount')),
        'price_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account')),
        
        }
    _defaults = {
        'product_uom_qty': 1,
        }
sale_order_line_template()

"""Order Template"""
class sale_order_template(osv.osv):
    _name = "sale.order.template"
    _description = "Template Details"
    
    def onchange_sub_doc(self, cr, uid, ids, sub_doc_id, context=None):
        model_name = ''
        if sub_doc_id:
            model_name = self.pool.get('subscription.document').browse(cr, uid, sub_doc_id).model.model
        return {'value': {'model_name': model_name}}
    
    def onchange_shop_id(self, cr, uid, ids, shop_id, context=None):
        v = {}
        if shop_id:
            shop = self.pool.get('sale.shop').browse(cr, uid, shop_id, context=context)
            if shop.project_id.id:
                v['project_id'] = shop.project_id.id
            if shop.pricelist_id.id:
                v['pricelist_id'] = shop.pricelist_id.id
        return {'value': v}
    
    def onchange_pricelist_id(self, cr, uid, ids, pricelist_id, order_lines, context=None):
        context = context or {}
        if not pricelist_id:
            return {}
        value = {
            'currency_id': self.pool.get('product.pricelist').browse(cr, uid, pricelist_id, context=context).currency_id.id
        }
        if not order_lines:
            return {'value': value}
        warning = {
            'title': _('Pricelist Warning!'),
            'message' : _('If you change the pricelist of this order (and eventually the currency), prices of existing order lines will not be updated.')
        }
        return {'warning': warning, 'value': value}
    
    def create(self, cr, uid, vals, context=None):
        """Method override to create sequence of template"""
        if vals.get('name','/')=='/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'sale.order.template') or '/'
        return super(sale_order_template, self).create(cr, uid, vals, context=context)
    
    def _get_default_shop(self, cr, uid, context=None):
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        shop_ids = self.pool.get('sale.shop').search(cr, uid, [('company_id','=',company_id)], context=context)
        if not shop_ids:
            raise osv.except_osv(_('Error!'), _('There is no default shop for the current user\'s company!'))
        return shop_ids[0]
    
    _columns = {
        'name': fields.char('Template Reference', size=64, required=True),
        'sub_doc_id': fields.many2one('subscription.subscription', size=30),
        'subcription_doc_id': fields.many2one('subscription.document', 'Subscription Doc', required=True, size=128),
        'sale_order_line': fields.one2many('sale.order.line.template', 'order_temp_id', 'Order Lines'),
        'date_order': fields.date('Date', required=True,),
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True),
        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=True, help="Pricelist for current sales order."),
        'partner_id': fields.many2one('res.partner', 'Customer', change_default=True, select=True, track_visibility='always'),
        'recurring_record': fields.boolean('Recurring'),
        'invoice_type': fields.selection([('out_invoice','Customer Invoice'),('in_invoice','Supplier Invoice')], 'Invoice Type', size=40),
        'model_name': fields.char('Model Name', size=40),
        }
    
    _defaults = {  
        'name': lambda obj, cr, uid, context: '/',
        'date_order': fields.date.context_today,
        'shop_id': _get_default_shop,
        }
sale_order_template()

class account_invoice(osv.osv):
    _inherit = "account.invoice"
    _description = "Extend with Terms"
    _columns = {
           'comment': fields.text('Notes'),
            }
account_invoice()





