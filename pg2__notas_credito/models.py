# -*- coding: utf-8 -*-

from openerp import models, fields, api
from openerp.osv.orm import except_orm
from openerp.osv import osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
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

class Invoices_lines_ans(models.Model):
	_inherit = 'account.invoice.line'

	@api.one
	def _computed_cant_facturada(self):
		cantidad_facturada = 0
		#cantidad_devuelta = 0
		if self.invoice_id.type == 'in_refund' or self.invoice_id.type == 'out_refund':
			invoices_obj = self.env['account.invoice'].search([('id','=',self.invoice_id.factura.id)])
			for inv_line in invoices_obj.invoice_line:
				if self.product_id.id == inv_line.product_id.id:
					cantidad_facturada += inv_line.quantity
					print("Cantidad facturada: {0}".format(cantidad_facturada))
		self.cantidad_facturada = cantidad_facturada

#	@api.one    
#	def _compute_cant_devuelta(self):
#		cantidad_devuelta = 0
#		#Nota de creditos de la factura
#		if self.invoice_id.type == 'in_refund' or self.invoice_id.type == 'out_refund':
#			invoices_obj = self.env['account.invoice'].search([('type','=','in_refund'),('factura.id','=',self.invoice_id.factura.id),('state','=','paid')])
#			print("Fuera del if {0}".format(invoices_obj))
#			print("ID DE LA FACTURA {0}".format(self.invoice_id.factura.id))
#			if invoices_obj:
#				print("Dentro del If xD")
#				for ntc in invoices_obj:
#					for invoice_line in ntc.invoice_line:
#						if invoice_line.product_id.id == self.product_id.id:
#							cantidad_devuelta += invoice_line.quantity
#						print("===================================== {0}".format(ntc.number))
#		print("Cant devuelta: {0}".format(cantidad_devuelta))
#		self.cantidad_devuelta = cantidad_devuelta

	type_computed = fields.Selection(string='Filed Label',related="invoice_id.type")
	cantidad_devuelta = fields.Float(string='Cantidad devuelta',digits=dp.get_precision('Account'))
	cantidad_facturada = fields.Float(string='Cantidad Facturada',compute=_computed_cant_facturada,digits=dp.get_precision('Account'))


_logger = logging.getLogger(__name__)
class NotasCreditoDebito(models.Model):
    _inherit = ['account.invoice']
    tipo = fields.Selection([('credito', 'Nota de Credito'),('debito', 'Nota de debito'),],'Tipo',default='credito')
    factura = fields.Many2one('account.invoice','Factura',domain="['&','&','&',('state','=','open'),('residual','!=',0 ),('type','!=','in_refund'),('type','!=','out_refund')]")
    establecimiento = fields.Char(string='Establecimiento',size=3)
    punto_emision = fields.Char(string='Punto de emision',size=3)
    secuencial = fields.Char(string='Secuencial',size=3)
    codigo_autorizacion = fields.Char(string='Codigo autorizacion', size=43)
    description = fields.Char('Motivo', required=True)




    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_invoice_tax = self.env['account.invoice.tax']
        account_move = self.env['account.move']


        for inv in self:
            #print("++++++++++++++++++ Aqui empiezo ++++++++++++++++++++++++")
            if inv.type == 'in_refund' or inv.type == 'out_refund':
            	for line in inv.invoice_line: 
            		total_resta = 0.00
            		if line.quantity == 0.000:
            			line.unlink()
            		total_resta = float(line.cantidad_facturada - line.cantidad_devuelta)
            		if line.quantity > total_resta:
            			raise except_orm(_('Error!'), _("La cantidad de {0} es mayor a la cantidad restante. (Quedan {1})".format(line.product_id.name,int(total_resta)) ))		 

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
        
        self._log_event()
        return True


    @api.multi
    def compute_cant_devuelta(self,id):
		cantidad_devuelta = 0
		#Nota de creditos de la factura

		if self.type == 'in_refund' or self.type == 'out_refund':
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
    @api.onchange('factura')
    def mostrar_monto(self):
		cantidad_facturada = 0
		cantidad_devuelta = 0
		invoices_obj = self.env['account.invoice'].search([('factura','=',self.factura.id),('type','=','in_refund')])
		self.partner_id = self.factura.partner_id
		self.invoice_line = []
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
          		'cantidad_devuelta' : self.compute_cant_devuelta(line.product_id.id),
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


		#print(self.monto)

    @api.multi
    def write(self, vals):
        _logger.info('valor a guardar'+str(vals))	        
        return super(NotasCreditoDebito, self).write(vals)



    @api.depends('tipo')
    def _onchange_estado(self):
    	if self.tipo == 'credito':
    		self.type = 'in_refund'
    		self.write = ({'type':'in_refund'})
    	if self.tipo == 'debito':
    		self.type = 'out_refund'
    		self.write = ({'type':'out_refund'})
    
    def reconciliar(self,cr,uid,ids,context=None):
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


        	print("Journal: " + str(journal) )
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

