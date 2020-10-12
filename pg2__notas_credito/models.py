# -*- coding: utf-8 -*-

from openerp import models, fields, api
from openerp.osv.orm import except_orm
from openerp.osv import osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import ValidationError
import re
import copy
import logging
# class pg2__notas_credito(models.Model):
#     _name = 'pg2__notas_credito.pg2__notas_credito'

#     name = fields.Char()
#nota_de_credito_ans
TYPE2REFUND = {
    'out_invoice': 'out_refund',        # Customer Invoice
    'in_invoice': 'in_refund',          # Supplier Invoice
    'out_refund': 'out_invoice',        # Customer Refund
    'in_refund': 'in_invoice',          # Supplier Refund
}

class Wizar_cancel_refund(models.TransientModel):
    _name = 'wizard.cancel.refund'
    _description = 'Modal para solicitar motivo de cancelacion.'
    motivo = fields.Char(string='Motivo')
    @api.multi
    def cancelar_nota_credito_p(self):
    	active_id = self._context.get('active_id', False)
    	if active_id:
    		invoices_obj = self.env['account.invoice']
    		print("Active id " + str(active_id))
    		inv = invoices_obj.search([('id','=',active_id)],limit=1)
    		if inv.cancelar_refund_p():
    			inv.write({'description':self.motivo})

class Invoices_lines_ans(models.Model):
	_inherit = 'account.invoice.line'
	@api.one
	def _computed_cant_facturada_p(self):
		cantidad_facturada = 0
		#cantidad_devuelta = 0
		if self.invoice_id.type == 'in_refund':
			invoices_obj = self.env['account.invoice'].search([('id','=',self.invoice_id.factura.id)])
			for inv_line in invoices_obj.invoice_line:
				if self.product_id.id == inv_line.product_id.id:
					cantidad_facturada += inv_line.quantity
					#print("Cantidad facturada: {0}".format(cantidad_facturada))
		self.cantidad_facturada = cantidad_facturada


	type_computed = fields.Selection(string='Filed Label',related="invoice_id.type")
	cantidad_devuelta = fields.Float(string='Cantidad devuelta',digits=dp.get_precision('Account'))
	cantidad_facturada = fields.Float(string='Cantidad Facturada',compute=_computed_cant_facturada_p,digits=dp.get_precision('Account'))



_logger = logging.getLogger(__name__)
class NotasCreditoDebito(models.Model):
    _inherit = ['account.invoice']

    @api.multi
    def onchange_partner_id(self, type, partner_id, date_invoice=False,
            payment_term=False, partner_bank_id=False, company_id=False,tipo=False):
        account_id = False
        payment_term_id = False
        fiscal_position = False
        bank_id = False
        p = self.env['res.partner'].browse(partner_id or False)
        
        
        if partner_id:
            rec_account = p.property_account_receivable
            pay_account = p.property_account_payable
            if company_id:
                if p.property_account_receivable.company_id and \
                        p.property_account_receivable.company_id.id != company_id and \
                        p.property_account_payable.company_id and \
                        p.property_account_payable.company_id.id != company_id:
                    prop = self.env['ir.property']
                    rec_dom = [('name', '=', 'property_account_receivable'), ('company_id', '=', company_id)]
                    pay_dom = [('name', '=', 'property_account_payable'), ('company_id', '=', company_id)]
                    res_dom = [('res_id', '=', 'res.partner,%s' % partner_id)]
                    rec_prop = prop.search(rec_dom + res_dom) or prop.search(rec_dom)
                    pay_prop = prop.search(pay_dom + res_dom) or prop.search(pay_dom)
                    rec_account = rec_prop.get_by_record(rec_prop)
                    pay_account = pay_prop.get_by_record(pay_prop)
                    if not rec_account and not pay_account:
                        action = self.env.ref('account.action_account_config')
                        msg = _('Cannot find a chart of accounts for this company, You should configure it. \nPlease go to Account Configuration.')
                        raise RedirectWarning(msg, action.id, _('Go to the configuration panel'))

            if type in ('out_invoice', 'out_refund'):
                account_id = rec_account.id
                payment_term_id = p.property_payment_term.id
            else:
                account_id = pay_account.id
                payment_term_id = p.property_supplier_payment_term.id
            fiscal_position = p.property_account_position.id

        result = {'value': {
            'account_id': account_id,
            'payment_term': payment_term_id,
            'fiscal_position': fiscal_position,
        }}
        #======================= Pg2 ===========================
        if type == 'in_refund' and tipo=='nota_credito_proveedores' and partner_id:
        	print(tipo)
        	print("Picadura de la cobra gei")
        	result['domain'] = {'factura':  [('type', '=', 'in_invoice'),('partner_id', '=', partner_id),('state','=','open'),('residual','!=',0 ),('type','!=','in_refund'),('type','!=','out_refund')]}
        #==================================================
        if type in ('in_invoice', 'out_refund'):
            bank_ids = p.commercial_partner_id.bank_ids
            bank_id = bank_ids[0].id if bank_ids else False
            result['value']['partner_bank_id'] = bank_id
            result['domain'] = {'partner_bank_id':  [('id', 'in', bank_ids.ids)]}

        if payment_term != payment_term_id:
            if payment_term_id:
                to_update = self.onchange_payment_term_date_invoice(payment_term_id, date_invoice)
                result['value'].update(to_update.get('value', {}))
            else:
                result['value']['date_due'] = False

        if partner_bank_id != bank_id:
            to_update = self.onchange_partner_bank(bank_id)
            result['value'].update(to_update.get('value', {}))

        return result

    tipo = fields.Selection([('nota_credito_proveedores', 'Nota de Credito'),('factura_proveedor', 'Nota de debito'),],'Tipo',default='nota_credito_proveedores')
    factura = fields.Many2one('account.invoice','Factura',domain=[('partner_id','=',0)])
    establecimiento = fields.Char(string='Establecimiento',size=3)
    punto_emision = fields.Char(string='Punto de emisión',size=3)
    secuencial = fields.Char(string='Secuencial',size=9)
    codigo_autorizacion = fields.Char(string='Autorización',size=43)
    description = fields.Char('Motivo')
    




    @api.constrains('secuencial','punto_emision','establecimiento')
    def validar_campos_especiales(self):
    	invoice_count = self.env['account.invoice'].search([('partner_id','=',self.partner_id.id),('state','in',['paid'])],order='date_invoice desc')
    	#print("Se ejecuta "+ str(self.punto_emision))
    	for inv in invoice_count:
    		if inv.secuencial == self.secuencial:
    			raise ValidationError("El numero secuencial se encuentra en uso.")
    		if inv.punto_emision == self.punto_emision:
    			raise ValidationError("El punto de emisión se encuentra en uso.")
    		if inv.establecimiento == self.establecimiento:
    			raise ValidationError("El numero de establecimiento se encuentra en uso.")
    	


    @api.constrains('secuencial','punto_emision','establecimiento','codigo_autorizacion')
    def _verificar_campos(self):
    	#self.validar_campos_especiales()
    	for record in self:
    		if re.search('[a-zA-Z]', record.secuencial):
    			raise ValidationError("El numero secuencial solo acepta valores numéricos.")
    		if re.search('[a-zA-Z]', record.punto_emision):
    			raise ValidationError("El punto de emisión solo acepta valores numéricos.")
    		if re.search('[a-zA-Z]', record.establecimiento):
    			raise ValidationError("El numero de establecimiento solo acepta valores numéricos." )
    		if re.search('[a-zA-Z]', record.codigo_autorizacion):
    			raise ValidationError("El numero de autorización solo acepta valores numéricos.")


    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_invoice_tax = self.env['account.invoice.tax']
        account_move = self.env['account.move']



        for inv in self:
            #print("++++++++++++++++++ Aqui empiezo ++++++++++++++++++++++++")
            if inv.type == 'in_refund' :
            	for line in inv.invoice_line: 
            		total_resta = 0.00
            		total_resta = float(line.cantidad_facturada - line.cantidad_devuelta)
            		if line.quantity > total_resta:
            			raise except_orm(_('Error!'), _("La cantidad de {0} es mayor a la cantidad restante. (Quedan {1})".format(line.product_id.name,int(total_resta)) ))
            		if line.quantity == 0.000:
            			line.unlink()
            if not inv.journal_id.sequence_id:
                raise except_orm(_('Error!'), _('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line:
                raise except_orm(_('No Invoice Lines!'), _('Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            company_currency = inv.company_id.currency_id
            if not inv.date_invoice:
                # FORWARD-PORT UP TO SAAS-6
                if inv.currency_id != company_currency and inv.tax_line:
                    raise except_orm(
                        _('Warning!'),
                        _('No invoice date!'
                            '\nThe invoice currency is not the same than the company currency.'
                            ' An invoice date is required to determine the exchange rate to apply. Do not forget to update the taxes!'
                        )
                    )
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice

            # create the analytical lines, one move line per invoice line
            iml = inv._get_analytic_lines()
            # check if taxes are all computed
            compute_taxes = account_invoice_tax.compute(inv.with_context(lang=inv.partner_id.lang))
            inv.check_tax_lines(compute_taxes)

            # I disabled the check_total feature
            if self.env.user.has_group('account.group_supplier_inv_check_total'):
                if inv.type in ('in_invoice', 'in_refund') and abs(inv.check_total - inv.amount_total) >= (inv.currency_id.rounding / 2.0):
                    raise except_orm(_('Bad Total!'), _('Please verify the price of the invoice!\nThe encoded total does not match the computed total.'))

            if inv.payment_term:
                total_fixed = total_percent = 0
                for line in inv.payment_term.line_ids:
                    if line.value == 'fixed':
                        total_fixed += line.value_amount
                    if line.value == 'procent':
                        total_percent += line.value_amount
                total_fixed = (total_fixed * 100) / (inv.amount_total or 1.0)
                if (total_fixed + total_percent) > 100:
                    raise except_orm(_('Error!'), _("Cannot create the invoice.\nThe related payment term is probably misconfigured as it gives a computed amount greater than the total invoiced amount. In order to avoid rounding issues, the latest line of your payment term must be of type 'balance'."))

            # Force recomputation of tax_amount, since the rate potentially changed between creation
            # and validation of the invoice
            inv._recompute_tax_amount()
            # one move line per tax line
            iml += account_invoice_tax.move_line_get(inv.id)

            if inv.type in ('in_invoice', 'in_refund'):
                ref = inv.reference
            else:
                ref = inv.number

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, ref, iml)

            name = inv.supplier_invoice_number or inv.name or '/'
            totlines = []
            if inv.payment_term:
                totlines = inv.with_context(ctx).payment_term.compute(total, date_invoice)[0]
            if totlines:
                res_amount_currency = total_currency
                ctx['date'] = date_invoice
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'ref': ref,
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'ref': ref
                })

            date = date_invoice

            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)

            line = [(0, 0, self.line_get_convert(l, part.id, date)) for l in iml]
            line = inv.group_lines(iml, line)

            journal = inv.journal_id.with_context(ctx)
            if journal.centralisation:
                raise except_orm(_('User Error!'),
                        _('You cannot create an invoice on a centralized journal. Uncheck the centralized counterpart box in the related journal from the configuration menu.'))

            line = inv.finalize_invoice_move_lines(line)

            move_vals = {
                'ref': inv.reference or inv.name,
                'line_id': line,
                'journal_id': journal.id,
                'date': inv.date_invoice,
                'narration': inv.comment,
                'company_id': inv.company_id.id,
            }
            ctx['company_id'] = inv.company_id.id
            period = inv.period_id
            if not period:
                period = period.with_context(ctx).find(date_invoice)[:1]
            if period:
                move_vals['period_id'] = period.id
                for i in line:
                    i[2]['period_id'] = period.id

            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)

            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'period_id': period.id,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
        if self.type == 'in_refund' and self.tipo == 'nota_credito_proveedores':
        	self.reconciliar_p()
        self._log_event()
        return True


    @api.multi
    def compute_cant_devuelta_p(self,id):
		cantidad_devuelta = 0
		#Nota de creditos de la factura

		if self.type == 'in_refund':
			invoices_obj = self.env['account.invoice'].search([('type','=','in_refund'),('factura.id','=',self.factura.id),('state','=','paid')])
			#print("Fuera del if {0}".format(invoices_obj))
			#print("ID DE LA FACTURA {0}".format(self.invoice_id.factura.id))
			if invoices_obj:
				#print("Dentro del If xD")
				for ntc in invoices_obj:
					for invoice_line in ntc.invoice_line:
						if invoice_line.product_id.id == id:
							cantidad_devuelta += invoice_line.quantity

						#print("===================================== {0}".format(ntc.number))
		#print("Cant devuelta: {0}".format(cantidad_devuelta))
		return cantidad_devuelta
    @api.multi
    def cancelar_refund_p(self):
        context = {}
        pago_cancelado = False
        voucher = None
        voucher_obj = self.pool.get('account.voucher')
        self._cr.execute("SELECT v.id FROM public.account_voucher as v join public.account_voucher_line as vl on v.id = vl.voucher_id where vl.name = %s",(self.number,))
        voucher = self._cr.fetchone()
        if voucher:
        	print("Se cancela")
        	pago_cancelado = voucher_obj.cancel_voucher(self._cr,self._uid,voucher,context=context)
        if pago_cancelado:
        	self.action_cancel_draft_p()
        return pago_cancelado

    @api.multi
    def action_cancel_draft_p(self):
        # go from canceled state to draft state
        self.write({'state': 'cancel'})
        self.delete_workflow()
        self.create_workflow()
        return True



	
        


    @api.multi
    @api.onchange('factura')
    def mostrar_monto_p(self):
		cantidad_facturada = 0
		cantidad_devuelta = 0
		#invoices_obj = self.env['account.invoice'].search([('factura','=',self.factura.id),('type','=','in_refund')])
		#self.partner_id = self.factura.partner_id
		self.invoice_line = [(6,0,[])]
		#Vaciando 
		lista = []
		for line in self.factura.invoice_line:
			values = {
            	'type': 'src',
            	'name': line.name.split('\n')[0][:64],
            	'price_unit': line.price_unit,
            	'quantity': float(0),
            	'price': line.price_subtotal,
            	'account_id': line.account_id.id,
            	'product_id': line.product_id.id,
          		'cantidad_devuelta' : self.compute_cant_devuelta_p(line.product_id.id),
            	'uos_id': line.uos_id.id,
            	'account_analytic_id': line.account_analytic_id.id,
            	'invoice_line_tax_id': line.invoice_line_tax_id,
        	}
			lista.append((0,0,values))
			#print("Ids: {0}".format(line.id))
		self.invoice_line = lista
		self.journal_id = self.factura.journal_id
		self.account_id = self.factura.account_id
		#self.residual = self.factura.residual
		#self.origin = self.factura.number
		self.period_id = self.factura.period_id
		self.fiscal_position = self.factura.fiscal_position

    @api.multi
    def button_reset_taxes_p(self,invoice):
        account_invoice_tax = self.env['account.invoice.tax']
        ctx = dict(self._context)
        self._cr.execute("DELETE FROM account_invoice_tax WHERE invoice_id=%s AND manual is False", (invoice.id,))
        self.invalidate_cache()
        partner = invoice.partner_id
        if partner.lang:
            ctx['lang'] = partner.lang
        for taxe in account_invoice_tax.compute(invoice.with_context(ctx)).values():
            account_invoice_tax.create(taxe)
        # dummy write on self to trigger recomputations
        return self.with_context(ctx).write({'invoice_line': []})

    @api.multi
    def write(self, vals):
        _logger.info('valor a guardar'+str(vals))
        record = super(NotasCreditoDebito, self).write(vals)
        if self.type == 'in_refund':    
        	invoices_obj = self.env['account.invoice'].search([('id','=',self.id)])[0]
        	self.env['account.invoice'].button_reset_taxes_p(invoices_obj)
        
        return record
    @api.model
    def create(self, values):
    	values['tipo'] = 'nota_credito_proveedores'
    	record = super(NotasCreditoDebito, self).create(values)
    	#_logger.info('valor a guardar'+str(self.type))
    	if values['tipo'] == 'nota_credito_proveedores':
    		self._cr.execute('select "id" from "account_invoice" order by "id" desc limit 1')
    		last_id = self._cr.fetchone()
    		invoices_obj = self.env['account.invoice'].search([('id','=',last_id)])[0]
    		self.env['account.invoice'].button_reset_taxes_p(invoices_obj)
        return record


    
    def reconciliar_p(self,cr,uid,ids,context=None):
    	res_currency = self.pool.get('res.currency')
        voucher_obj = self.pool.get('account.voucher')
        journal_obj_pool = self.pool.get('account.journal')
        voucher_line_pool = self.pool.get('account.voucher.line')
        move_lines = []

        for inv in self.browse(cr,uid, ids ,context=context):
        	journal_id = journal_obj_pool.search(cr,uid,[('nota_credito','=',True)],limit=1)
        	#Diario
        	journal = journal_obj_pool.browse(cr,uid,journal_id,context=context)
        	#Moneda
        	company_currency = currency_id = journal.company_id.currency_id.id


        	#print("Journal: " + str(journal) )
        	invoice_moves_ids = self.pool.get('account.invoice').search(cr,uid,[('id','in',[inv.id,inv.factura.id])])
        	invoice_moves_obj = self.pool.get('account.invoice').browse(cr,uid,invoice_moves_ids,context=context)
        	vourcher_vals = {
        					'date': inv.date_invoice,
        					'journal_id': journal.id,
        					'account_id': journal.default_credit_account_id.id,
        					'period_id': inv.period_id.id,
        					'currency_id': inv.currency_id.id,
        					'company_id': inv.company_id.id,
        					'state': 'draft',
        					'amount': 0.0,
        					'partner_id' : inv.partner_id.id,
         					'payment_option':'without_writeoff',
         					'type':'payment',
         					'pay_now':'pay_now'
         				    }

        	voucher_id = self.pool.get('account.voucher').create(cr,uid,vourcher_vals,context=context)
        	for facturas in invoice_moves_obj:
        		id = None 
        		account = None
        		monto_original = None
        		monto_no_reconciliado = None
        		date = None
        		date_due = None
        		for line in facturas.move_id.line_id:
        			if line.account_id.type == 'payable':
        				id = line.id
        				account = line.account_id.id
        				monto_original = res_currency.compute(cr,uid,company_currency,currency_id,line.credit or line.debit or 0.0,context=context)
        				monto_no_reconciliado = res_currency.compute(cr,uid,company_currency,currency_id,abs(line.amount_residual),context=context)
        				date = line.date
        				date_due = line.date_maturity
        		
        		res = {
        				'voucher_id':voucher_id,
        		        'name':facturas.move_id.name,
        				'move_line_id':id,
        				'account_id':account,
        				'amount_original':monto_original,
        				'amount':inv.amount_total,
        				'amount_unreconciled':monto_no_reconciliado,
        				'date_original':date,
        				'date_due':date_due,
        				'currency_id':currency_id
        			  }
        		if facturas.type == 'in_refund':
        			res['type'] = 'cr'
        		else:
        			res['type'] = 'dr'	
        		voucher_line_pool.create(cr,uid,res,context=context)
        	voucher_obj.action_move_line_create(cr,uid,[voucher_id],context=None)
        	inv.state = 'paid'
class InheritJournal(models.Model):
	_inherit = 'account.journal'
	nota_credito = fields.Boolean(string='nota_credito')

