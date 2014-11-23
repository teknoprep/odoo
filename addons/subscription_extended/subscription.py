# -*- coding: utf-8 -*-

from openerp.osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc


from datetime import datetime
import time


class subscription_subscription(osv.osv):
    _inherit = "subscription.subscription"
    _columns = {
                    'doc_source'        : fields.reference('Source doc', required=False, selection=[('res.partner','Partner')], size=128, help="User can choose the source document on which he wants to create documents"),
                    'source_doc_id'     : fields.many2one('subscription.document', 'Source Document', required=True),
                    'template_order_id' : fields.many2one('sale.order.template', 'Sale order'),
                    'temp_model'        : fields.char('Temp Model', size=60),
                    'template_ids1'     : fields.one2many('sale.order.template', 'sub_doc_id', 'Sale Order Template View '),
                    'term_condition'    : fields.text('Term & Condition'),
                    'doc_type'          : fields.char('Doc type', size=40),
                    'notify_by_mail'    : fields.boolean('Notify By Mail', help='Use notify by mail to customer/supplier after create invoice'),
                    'valid_invoice'     : fields.boolean('Validate', help='Use to confirm Invoice after create'),
                    'payment_term'      : fields.many2one('account.payment.term', 'Payment Terms'),
     }

    _defaults = {
                    'doc_source' : 'res.partner,1'
    }

    def onchange_source_doc(self, cr, uid, ids, source_id, context=None):
        if source_id:
            return {'value': {'temp_model': 'sale.order.template'}}
        return {'value': {'temp_model': ''}}

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
                'pricelist_id': order_brw.pricelist_id.id,
                'model_name': order_brw.model_name,
                'invoice_type': order_brw.invoice_type,
                'sale_order_line': order_line,
                'company_id' : order_brw.company_id and order_brw.company_id.id or False 
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
    
    def set_done(self, cr, uid, ids, context=None):
        res = self.read(cr,uid, ids, ['cron_id'])
        ids2 = [x['cron_id'][0] for x in res if x['id']]
        self.pool.get('ir.cron').write(cr, uid, ids2, {'active':False, 'doall': False})
        self.write(cr, uid, ids, {'state':'done'})
        return True
    
    def set_process(self, cr, uid, ids, context=None):
        for row in self.read(cr, uid, ids, context=context):
            mapping = {'name':'name','interval_number':'interval_number','interval_type':'interval_type','exec_init':'numbercall','date_init':'nextcall'}
            res = {'model':'subscription.subscription', 'args': repr([[row['id']]]), 'function':'model_copy', 'priority':1, 'user_id':row['user_id'] and row['user_id'][0], 'doall':True}
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
                print ">>>>>>>>>>>>>>>>>>>>", model_name_template
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
                                    'company_id': order_brw.company_id.id
                                    })
                    print "default",default
                    print order_brw.name
                    print order_brw.company_id.id
                    print order_brw.company_id.name
                    if order_brw.invoice_type == 'out_invoice':
                        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'sale'), ('company_id', '=', order_brw.company_id.id)], limit=1)
                        if not journal_ids:
                            raise osv.except_osv(_('Error!'),
                                _('Please define sales journal for this company: "%s" (id:%d).') % (order_brw.company_id.name, order_brw.company_id.id))
                        default.update({'journal_id': journal_ids[0],})
                        
                    if order_brw.invoice_type == 'in_invoice':
                        journal_ids = self.pool.get('account.journal').search(cr, uid,
                            [('type', '=', 'purchase'), ('company_id', '=', order_brw.company_id.id)],
                            limit=1)
                        if not journal_ids:
                            raise osv.except_osv(_('Error!'),
                                _('Please define purchase journal for this company: "%s" (id:%d).') % (order_brw.company_id.name, order_brw.company_id.id))
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
                    self.pool.get('account.invoice').button_reset_taxes(cr, uid, [data_id])
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
