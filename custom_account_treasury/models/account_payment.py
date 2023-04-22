from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
	_inherit = 'account.payment'


	@api.depends('payment_lines.invoice_id')
	def _compute_domain_move_line(self):
		for pay in self:
			invoices = pay.mapped('payment_lines.invoice_id')
			pay.domain_move_lines = [(6,0,invoices.ids)]

	move_diff_ids = fields.Many2many('account.move', 'account_move_payment_rel_ids', 'move_id', 'payment_id', copy=False)
	payment_line_ids = fields.One2many('account.payment.detail', 'payment_id', copy=False,
		string="Detalle de pago", help="detalle de pago")
	payment_lines = fields.One2many('account.payment.detail', 'payment_id', copy=False,
		domain=[('exclude_from_payment_detail', '=', False)], string="Documentos", help="detalle de pago y/o cobro")

	# fields account origin and destination
	# account_id = fields.Many2one('account.account', string='Cuenta de origen', default=_default_account_id)
	account_id = fields.Many2one(
		comodel_name='account.account',
		string='Cuenta de origen',
		store=True, readonly=False,
		compute='_compute_destination_account_id',
		domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
		check_company=True)
	destination_account_id = fields.Many2one(
		comodel_name='account.account',
		string='Destination Account',
		store=True, readonly=False,
		compute='_compute_destination_account_id',
		domain="[('user_type_id.type', 'in', ('receivable', 'payable')), ('company_id', '=', company_id)]",
		check_company=True)
	change_destination_account = fields.Char(string="cambio de cuenta destino")

	company_currency_id = fields.Many2one('res.currency', string="Moneda de la compañia",
		required=True, default=lambda self: self.env.user.company_id.currency_id)

	customer_invoice_ids = fields.Many2many("account.move", "customer_invoice_payment_rel", 'invoice_id', 'payment_id',
		string="Buscar Documentos Clientes")
	supplier_invoice_ids = fields.Many2many("account.move", "supplier_invoice_payment_rel", 'invoice_id', 'payment_id',
		string="Buscar Documentos Proveedores")
	account_move_payment_ids = fields.Many2many("account.move.line", "account_move_payment_rel", 'moe_line_id','payment_id',
		string="Buscar Otros Documentos")

	domain_move_lines = fields.Many2many("account.move", 'domain_move_line_pay_rel', string="restriccion de campos", compute="_compute_domain_move_line")

	payment_difference_line = fields.Monetary(string="Diferencia de pago",
		store=True, readonly=True, compute="_compute_payment_difference_line", tracking=True)
	# journal_id = fields.Many2one(track_visibility='always')
	payment_date = fields.Date(tracking=True)
	account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')

	# advane

	advance_type_id = fields.Many2one('advance.type', string="Tipo de anticipo")
	advance = fields.Boolean('Anticipo', default=False)
	code_advance = fields.Char(string="Número de anticipo", copy=False)
	# partner_type = fields.Selection(selection_add=[('employee','Empleado')])
	partner_type = fields.Selection(selection_add=[
		('employee', 'Empleado'),
	], ondelete={'employee': 'set default'})
	writeoff_account_id = fields.Many2one('account.account', string="Cuenta de diferencia", copy=False,
		domain="[('deprecated', '=', False), ('company_id', '=', company_id)]")
	writeoff_label = fields.Char(string='Journal Item Label', default='Write-Off',
		help='Change label of the counterpart that will hold the payment difference')


	def _prepare_move_line_default_vals(self, write_off_line_vals=None):
		''' Prepare the dictionary to create the default account.move.lines for the current payment.
		:param write_off_line_vals: Optional dictionary to create a write-off account.move.line easily containing:
			* amount:       The amount to be added to the counterpart amount.
			* name:         The label to set on the line.
			* account_id:   The account on which create the write-off.
		:return: A list of python dictionary to be passed to the account.move.line's 'create' method.
		'''
		self.ensure_one()
		write_off_line_vals = write_off_line_vals or {}

		if not self.journal_id.payment_debit_account_id or not self.journal_id.payment_credit_account_id:
			raise UserError(_(
				"You can't create a new payment without an outstanding payments/receipts account set on the %s journal.",
				self.journal_id.display_name))

		# Compute amounts.
		write_off_amount_currency = write_off_line_vals.get('amount', 0.0)

		if self.payment_type == 'inbound':
			# Receive money.
			liquidity_amount_currency = self.amount
		elif self.payment_type == 'outbound':
			# Send money.
			liquidity_amount_currency = -self.amount
			write_off_amount_currency *= -1
		else:
			liquidity_amount_currency = write_off_amount_currency = 0.0

		write_off_balance = self.currency_id._convert(
			write_off_amount_currency,
			self.company_id.currency_id,
			self.company_id,
			self.date,
		)
		liquidity_balance = self.currency_id._convert(
			liquidity_amount_currency,
			self.company_id.currency_id,
			self.company_id,
			self.date,
		)
		counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
		counterpart_balance = -liquidity_balance - write_off_balance
		currency_id = self.currency_id.id

		if self.is_internal_transfer:
			if self.payment_type == 'inbound':
				liquidity_line_name = _('Transfer to %s', self.journal_id.name)
			else: # payment.payment_type == 'outbound':
				liquidity_line_name = _('Transfer from %s', self.journal_id.name)
		else:
			liquidity_line_name = self.payment_reference

		# Compute a default label to set on the journal items.

		payment_display_name = {
			'outbound-customer': _("Customer Reimbursement"),
			'inbound-customer': _("Customer Payment"),
			'outbound-supplier': _("Vendor Payment"),
			'inbound-supplier': _("Vendor Reimbursement"),
			'outbound-employee': _("Employee Payment"),
			'inbound-employee': _("Employee Reimbursement"),
		}

		default_line_name = self.env['account.move.line']._get_default_line_name(
			_("Internal Transfer") if self.is_internal_transfer else payment_display_name['%s-%s' % (self.payment_type, self.partner_type)],
			self.amount,
			self.currency_id,
			self.date,
			partner=self.partner_id,
		)

		line_vals_list = [
			# Liquidity line.
			{
				'name': liquidity_line_name or default_line_name,
				'date_maturity': self.date,
				'amount_currency': liquidity_amount_currency,
				'currency_id': currency_id,
				'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
				'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
				'partner_id': self.partner_id.id,
				'account_id': self.journal_id.payment_credit_account_id.id if liquidity_balance < 0.0 else self.journal_id.payment_debit_account_id.id,
			},
			# Receivable / Payable.
			{
				'name': self.payment_reference or default_line_name,
				'date_maturity': self.date,
				'amount_currency': counterpart_amount_currency,
				'currency_id': currency_id,
				'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
				'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
				'partner_id': self.partner_id.id,
				'account_id': self.destination_account_id.id,
			},
		]
		if not self.currency_id.is_zero(write_off_amount_currency):
			# Write-off line.
			line_vals_list.append({
				'name': write_off_line_vals.get('name') or default_line_name,
				'amount_currency': write_off_amount_currency,
				'currency_id': currency_id,
				'debit': write_off_balance if write_off_balance > 0.0 else 0.0,
				'credit': -write_off_balance if write_off_balance < 0.0 else 0.0,
				'partner_id': self.partner_id.id,
				'account_id': write_off_line_vals.get('account_id'),
			})
		return line_vals_list

	@api.onchange('advance_type_id')
	def _onchange_advance_type_id(self):
		self._onchange_payment_type()

	@api.onchange('advance')
	def _onchange_advance(self):
		res = {}
		if not self.reconciled_invoice_ids:
			if self.payment_type == 'transfer':
				self.advance = False
				self.advance_type_id = False
			elif not self.advance:
				self.advance_type_id = False
		if self.advance:
			self.advance_type_id = False
			res['domain'] = {'advance_type_id': [('internal_type','=', self.payment_type == 'outbound' and 'receivable' or 'payable')]}
		return res

	def action_post(self):
		print('------------post new----------')
		# pay_details = self.env['account.payment.detail']
		for rec in self:
			print('-------rec', rec)
			if not rec.code_advance:
				sequence_code = ''
				if rec.advance:
					if rec.partner_type == 'customer':
						sequence_code = 'account.payment.advance.customer'
					if rec.partner_type == 'supplier':
						sequence_code = 'account.payment.advance.supplier'
					if rec.partner_type == 'employee':
						sequence_code = 'account.payment.advance.employee'

				rec.code_advance = self.env['ir.sequence'].with_context(ir_sequence_date=rec.date).next_by_code(sequence_code)
				if not rec.code_advance and rec.advance:
					raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))
			if not rec.name:
				if rec.partner_type == 'employee':
					sequence_code = 'account.payment.employee'
					rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.date).next_by_code(sequence_code)
					if not rec.name:
						raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))
			if self.payment_line_ids and self.payment_type != 'transfer':
				amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
				self._create_payment_entry_line(rec.move_id)
				super().action_post()
				lst = [line.invoice_id for line in rec.payment_line_ids if line.invoice_id]
				print('-------lst',lst)
				# pay_details.search([('payment_id', '=', self.id)])
				# pay_amt =0.0
				# for vals in pay_details:
				# 	pay_amt = vals.payment_amount
				# 	print('pay_amt----->', pay_amt)
				
				for invoice in lst:
					# invoice.update({'invoice_payments_widget': pay_amt, 'state': 'posted'})
					# payments = invoice.mapped('transaction_ids.payment_id').filtered(lambda p: p.state == 'posted')
					move_lines = rec.line_ids.filtered(lambda line: line.account_internal_type in ('receivable', 'payable') and not line.reconciled)
					for line in move_lines:
						print('line=====1212121212=', line)
						invoice.with_context(skip_account_move_synchronization=True).js_assign_outstanding_line(line.id)
			else:
				super(AccountPayment, rec).action_post()
		return True

	# def _get_counterpart_move_line_vals(self, invoice=False):
	# 	res = super(AccountPayment, self)._get_counterpart_move_line_vals(invoice=invoice)
	# 	if self.advance:
	# 		name = ''
	# 		if self.partner_type == 'employee':
	# 			name += _('Employee Payment Advance')
	# 		elif self.partner_type == 'customer':
	# 			name += _('Customer Payment Advance')
	# 		elif self.partner_type == 'supplier':
	# 			name += _('Vendor Payment Advance')
	# 		name += self.code_advance or ''
	# 		res.update(name=name)
	# 	return res

	##### END advance

	@api.onchange('journal_id', 'payment_type')
	def _onchange_account_id(self):
		account = self._compute_destination_account_id()
		self.account_id = account

	@api.onchange('payment_type')
	def _onchange_payment_type(self):
		# res = super(AccountPayment, self)._onchange_payment_type()
		self.change_destination_account = None
		# return res

	@api.onchange('reconciled_invoice_ids', 'payment_type', 'partner_type', 'partner_id', 'journal_id', 'destination_account_id')
	def _change_destination_account(self):
		change_destination_account = '0'
		account_id = None
		partner = self.partner_id.with_context(company_id=self.company_id.id)
		if self.reconciled_invoice_ids:
		# if self.invoice_ids:
		# 	self.change_destination_account = self.invoice_ids[0].account_id.id
			self.change_destination_account = self.reconciled_invoice_ids[0].account_id.id
			return
		elif self.payment_type == 'transfer':
			self._onchange_amount()
			if not self.company_id.transfer_account_id.id:
				raise UserError(_('There is no Transfer Account defined in the accounting settings. Please define one to be able to confirm this transfer.'))
			account_id = self.company_id.transfer_account_id.id

			# Esta comentado porque no corresponde al modulo
			# account_id = self.destination_journal_id and self.destination_journal_id.default_debit_account_id.id or False
		elif self.partner_id:
			if self.partner_type == 'customer':
				account_id = partner.property_account_receivable_id.id
			else:
				account_id = partner.property_account_payable_id.id
		elif self.partner_type == 'customer':
			# default_account = self.env['ir.property'].with_context(force_company=self.company_id.id).get('property_account_receivable_id', 'res.partner')
			default_account = partner.property_account_receivable_id
			account_id = default_account.id
		elif self.partner_type == 'supplier':
			# default_account = self.env['ir.property'].with_context(force_company=self.company_id.id).get('property_account_payable_id', 'res.partner')
			default_account = partner.property_account_payable_id
			account_id = default_account.id

		if self.destination_account_id.id != account_id:
			change_destination_account = self.destination_account_id.id
		self.change_destination_account = change_destination_account

	# @api.depends('invoice_ids', 'payment_type', 'partner_type', 'partner_id', 'change_destination_account', 'advance_type_id')
	@api.depends('journal_id','partner_id','is_internal_transfer','reconciled_invoice_ids','journal_id','payment_type', 'partner_type', 'partner_id', 'change_destination_account', 'advance_type_id')
	# @api.depends('journal_id', 'partner_id', 'partner_type', 'is_internal_transfer')
	def _compute_destination_account_id(self):
		for val in self:
			journal_id = self._get_default_journal()
			account = val.payment_type in ('outbound','transfer') and journal_id.payment_debit_account_id.id or journal_id.payment_credit_account_id.id
			if account:
				val.account_id = account
			if val.change_destination_account not in (False,'0') :
				val.destination_account_id = int(val.change_destination_account)
			if val.advance_type_id:
				val.destination_account_id = val.advance_type_id.account_id.id
			else:
				super(AccountPayment, self)._compute_destination_account_id()
			if val.partner_type == 'employee':
				val.destination_account_id = int(val.change_destination_account)

	def _get_liquidity_move_line_vals(self, amount):
		res = super(AccountPayment, self)._get_liquidity_move_line_vals(amount)
		res.update(
			account_id = self.account_id and self.account_id.id or res.get('account_id'),
			name = self.advance and self.code_advance or res.get('name')
			)
		return res

	def button_journal_difference_entries(self):
		return {
			'name': _('Diarios'),
			'view_type': 'form',
			'view_mode': 'tree,form',
			'res_model': 'account.move',
			'view_id': False,
			'type': 'ir.actions.act_window',
			'domain': [('id', 'in', self.move_diff_ids.ids)],
		}

	### END manual account ###

	@api.depends('payment_line_ids.balance', 'amount')
	def _compute_payment_difference_line(self):
		amount = 0.0
		for val in self:
			if val.payment_type != 'transfer':
				for line in val.payment_line_ids:
					sign = 1.0
					if not line.is_counterpart and not line.is_account_line and not line.is_manual_currency and not line.is_diff:
						if line.move_line_id and line.balance < 0:
							sign = -1.0
						amount += (line.payment_amount * sign)
					if line.is_account_line or line.is_counterpart:
						amount += (line.payment_amount * sign) or val.amount
				if val.payment_type == 'outbound':
					amount *= -1.0
			val.payment_difference_line = val.currency_id.round(amount)

	@api.onchange('currency_id')
	def _onchange_currency(self):
		for line in self.payment_line_ids:
			line.payment_currency_id = self.currency_id.id or False
			line._onchange_to_pay()
			line._onchange_payment_amount()
		# return super(AccountPayment, self)._onchange_currency()

	@api.returns('self', lambda value: value.id)
	def copy(self, default=None):
		default = dict(default or {})
		default.update(payment_line_ids=[])
		return super(AccountPayment, self).copy(default)

	@api.onchange('customer_invoice_ids')
	def _onchange_customer_invoice_ids(self):
		if self.customer_invoice_ids:
			where_clause = "account_move_line.amount_residual != 0 AND ac.reconcile AND am.id in %s"
			where_params = [tuple(self.customer_invoice_ids.ids)]
			self._cr.execute('''
			SELECT account_move_line.id
			FROM account_move_line
			LEFT JOIN account_move am ON (account_move_line.move_id = am.id)
			LEFT JOIN account_account ac ON (account_move_line.account_id = ac.id)
			WHERE ''' + where_clause, where_params
			)
			res = self._cr.fetchall()
			if res:
				moves = self.env['account.move.line'].browse(res[0])
				self._change_and_add_payment_detail(moves)
			# moves = self.customer_invoice_ids.mapped('move_id').mapped('line_ids').filtered(lambda line: line.amount_residual != 0 and line.account_id.reconcile)
		self.customer_invoice_ids = None

	@api.onchange('supplier_invoice_ids')
	def _onchange_supplier_invoice_ids(self):
		if self.supplier_invoice_ids:
			where_clause = "account_move_line.amount_residual != 0 AND ac.reconcile AND am.id in %s"
			where_params = [tuple(self.supplier_invoice_ids.ids)]
			self._cr.execute('''
			SELECT account_move_line.id
			FROM account_move_line
			LEFT JOIN account_move am ON (account_move_line.move_id = am.id)
			LEFT JOIN account_account ac ON (account_move_line.account_id = ac.id)
			WHERE ''' + where_clause, where_params
			)
			res = self._cr.fetchall()
			if res:
				moves = self.env['account.move.line'].browse(res[0])
				self._change_and_add_payment_detail(moves)
		self.supplier_invoice_ids = None

	def _change_and_add_payment_detail(self, moves):
		SelectPaymentLine = self.env['account.payment.detail']
		current_payment_lines = self.payment_line_ids.filtered(lambda line: not line.exclude_from_payment_detail)
		move_lines = moves - current_payment_lines.mapped('move_line_id')
		other_lines = self.payment_line_ids - current_payment_lines
		self.payment_line_ids = other_lines + self.payment_lines
		for line in move_lines:
			data = self._get_data_move_lines_payment(line)
			pay = SelectPaymentLine.new(data)
			pay._onchange_move_lines()
			pay._onchange_to_pay()
			pay._onchange_payment_amount()

	def _get_data_move_lines_payment(self, line):
		data = {
			'move_line_id': line.id,
			'account_id': line.account_id.id,
			'payment_id': self.id,
			'payment_currency_id': self.currency_id.id,
			'payment_difference_handling': 'open',
			'writeoff_account_id': False,
			'to_pay': True
			}
		return data

	@api.onchange('payment_lines')
	def _onchange_payment_lines(self):
		current_payment_lines = self.payment_line_ids.filtered(lambda line: not line.exclude_from_payment_detail)
		other_lines = self.payment_line_ids - current_payment_lines
		self.payment_line_ids = other_lines + self.payment_lines
		self._onchange_recompute_dynamic_line()

	@api.onchange('currency_id', 'amount', 'payment_type')
	def _onchange_payment_amount_currency(self):
		# self.writeoff_account_id = self._get_account_diff_currency(self.payment_difference_line)
		self.writeoff_account_id = self._get_account_diff_currency(self.payment_difference_line)
		self._recompute_dynamic_lines()

	def _get_account_diff_currency(self, amount):
		account = False
		company = self.env.user.company_id
		exchange_journal = company.currency_exchange_journal_id
		# account = amount > 0 and exchange_journal.default_debit_account_id or exchange_journal.default_credit_account_id
		account = amount > 0 and exchange_journal.payment_debit_account_id or exchange_journal.payment_credit_account_id
		if not account:
			account = company.income_currency_exchange_account_id
		return account

	@api.onchange('payment_difference_line', 'account_id','writeoff_account_id')
	def _onchange_diference_account(self):
		self._recompute_dynamic_lines()

	@api.onchange('date')
	def _onchange_payment_date(self):
		for line in self.payment_line_ids.filtered(lambda line: not line.exclude_from_payment_detail):
			line._onchange_to_pay()
			line._onchange_payment_amount()
			line._compute_payment_difference()
			line._compute_debit_credit_balance()
		self._recompute_dynamic_lines()

	@api.onchange('payment_line_ids', 'account_id', 'destination_account_id')
	def _onchange_recompute_dynamic_line(self):
		self._recompute_dynamic_lines()

	def _recompute_dynamic_lines(self):
		amount = self.amount * (self.payment_type in ('outbound', 'transfer') and 1 or -1)
		self._onchange_accounts(-amount, account_id=self.account_id, is_account_line=True)

		# Diferencia de cambio
		if self.payment_type != 'transfer':
			payment_lines = self.payment_line_ids.filtered(lambda line: not line.exclude_from_payment_detail)
			if not payment_lines:
				counter_part_amount = amount
			else:
				counter_part_amount = 0.0
			self._onchange_accounts(counter_part_amount, account_id=self.destination_account_id, is_counterpart=True)
			payment_difference =  self.payment_difference_line * (self.payment_type in ('outbound', 'transfer') and 1.0 or -1.0)
			self._onchange_accounts(payment_difference, account_id=self.writeoff_account_id, is_diff=True)
			# self._onchange_accounts(payment_difference, account_id=self.account_id, is_diff=True)

		# para destino transferencia y/o destin
		if self.payment_type == 'transfer':
			self._onchange_accounts(amount, account_id=self.destination_account_id, is_transfer=True)

		if self != self._origin:
			self.payment_lines = self.payment_line_ids.filtered(lambda line: not line.exclude_from_payment_detail)

	def _onchange_accounts(self, amount,
								account_id=None, is_account_line=False, is_manual_currency=False, is_transfer=False, is_diff=False, is_counterpart=False):
		self.ensure_one()
		in_draft_mode = self != self._origin
		def _create_origin_and_transfer_payment(self, total_balance, account, journal, new_payment_line):
			line_values = self._set_fields_detail(total_balance, is_account_line, is_manual_currency, is_counterpart, is_transfer, is_diff, account)
			if self.payment_type == 'transfer' and (journal and journal.type == 'bank'):
				if journal.bank_account_id and journal.bank_account_id.partner_id:
					line_values.update({
						'partner_id': journal.bank_account_id.partner_id.id
						})
			if new_payment_line:
				new_payment_line.update(line_values)
			else:
				line_values.update({
					'company_id': self.company_id and self.company_id.id or False,
					})
				create_method = in_draft_mode and self.env['account.payment.detail'].new or self.env['account.payment.detail'].create
				new_payment_line = create_method(line_values)

			new_payment_line._onchange_to_pay()
			new_payment_line._onchange_payment_amount()
		journal = self.journal_id
		if is_account_line:
			existing_account_origin_line = self.payment_line_ids.filtered(lambda line: line.is_account_line)
		elif is_counterpart:
			existing_account_origin_line = self.payment_line_ids.filtered(lambda line: line.is_counterpart)
		elif is_manual_currency:
			existing_account_origin_line = self.payment_line_ids.filtered(lambda line: line.is_manual_currency)
		elif is_diff:
			existing_account_origin_line = self.payment_line_ids.filtered(lambda line: line.is_diff)
		elif is_transfer:
			existing_account_origin_line = self.payment_line_ids.filtered(lambda line: line.is_transfer)
			journal = self.destination_journal_id
		if not account_id:
			self.payment_line_ids -= existing_account_origin_line
			return
		if self.currency_id.is_zero(amount):
			self.payment_line_ids -= existing_account_origin_line
			return

		_create_origin_and_transfer_payment(self, amount, account_id, journal, existing_account_origin_line)

	def _set_fields_detail(self, total_balance, is_account_line, is_manual_currency, is_counterpart, is_transfer, is_diff, account):
		line_values = {
			'payment_amount': total_balance,
			'partner_id': self.partner_id.id or False,
			'payment_id': self.id,
			'company_currency_id': self.env.user.company_id.currency_id.id,
			'is_account_line': is_account_line,
			'is_manual_currency': is_manual_currency,
			'is_counterpart': is_counterpart,
			'is_transfer': is_transfer,
			'is_diff': is_diff,
			'name':	self.ref or '/',
			'currency_id' : self.currency_id.id,
			'account_id': account,
			'ref': self.name or '/',
			'exclude_from_payment_detail': True,
			'payment_currency_id': self.currency_id.id,
		}
		company_currency = self.env.user.company_id.currency_id
		if self.currency_id and self.currency_id != company_currency:
			amount = company_currency._convert(total_balance, self.currency_id, self.env.user.company_id, self.date or fields.Date.today())
			line_values.update({
				'amount_currency' : amount
				})
		return line_values

	def _move_autocomplete_payment_lines_create(self, vals_list):
		new_vals_list = []
		for vals in vals_list:
			if not vals.get('payment_lines'):
				new_vals_list.append(vals)
				continue
			if vals.get('payment_line_ids'):
				vals.pop('payment_lines', None)
				new_vals_list.append(vals)
				continue

			vals['payment_line_ids'] = vals.pop('payment_lines')
		return new_vals_list

	def _move_autocomplete_payment_lines_write(self, vals):
		enable_autocomplete = 'payment_lines' in vals and 'payment_line_ids' not in vals and True or False
		if not enable_autocomplete:
			return False
		# self._recompute_dynamic_lines()
		vals.pop('payment_lines', None)
		self.write(vals)
		return True

	@api.model_create_multi
	def create(self, vals_list):
		vals_list = self._move_autocomplete_payment_lines_create(vals_list)
		return super(AccountPayment, self).create(vals_list)

	def write(self, vals):
		if self._move_autocomplete_payment_lines_write(vals):
			return True
		else:
			vals.pop('payment_lines', None)
			res = super(AccountPayment, self).write(vals)
		return res


	def _get_counterpart_move_line_vals(self, invoice=False):
		res = super(AccountPayment, self)._get_counterpart_move_line_vals(invoice=invoice)
		if self.advance:
			name = ''
			if self.partner_type == 'employee':
				name += _('Employee Payment Advance')
			elif self.partner_type == 'customer':
				name += _('Customer Payment Advance')
			elif self.partner_type == 'supplier':
				name += _('Vendor Payment Advance')
			name += self.code_advance or ''
			res.update(name=name)
		return res


	def _create_payment_entry_line(self, move):
		print('------Create Payment Entry Line-------')
		aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
		# obj1 = self.env['account.payment.detail'].search([('state', '=', 'posted'), ('id', '=', self.payment_id.id)])
		# move = self.env['account.move'].create(self._get_move_vals())
		# payments = 0.0
		# for val in obj1:
		# 	payments = val.payment_amount
		balance = 0.0
		to_write = {'payment_id': self.id}
		self.line_ids.unlink()
		for line in self.payment_line_ids:
			sign = line.balance > 0.0 and 1.0 or -1.0
			balance += line.balance
			# to_write['line_ids'] = [(0, 0, line_vals) for line_vals in self.with_context(from_payment_line=True)._prepare_move_line_default_vals()]
			# to_write['line_ids'] = [(0, 0, line_vals) [(0, 0, line_vals) for line_vals in self._prepare_move_line_default_vals()]
			currency = line.account_id.currency_id or line.currency_id
			counterpart_aml_dict = {
				'partner_id': self.payment_type in ('inbound', 'outbound') and self.env['res.partner']._find_accounting_partner(self.partner_id).id or False,
				# '_id': invoice_id and invoice_id.id or False,
				'move_id': move.id,
				'debit': line.debit,
				'credit': line.credit,
				'amount_currency': abs(line.amount_currency) * sign or False,
				'payment_id': self.id,
				'journal_id': self.journal_id.id,
				'account_id':line.account_id.id,
			}
			counterpart_aml_dict.update(line._get_counterpart_move_line_vals())
			counterpart_aml = aml_obj.with_context(skip_account_move_synchronization=True).create(counterpart_aml_dict)
			# self._create_conciled(line, counterpart_aml)

		# PAra la diferencia de cambio
		if self.currency_id.round(balance):
			company = self.company_id
			balance *= -1
			if self.currency_id != company.currency_id:
				balance = company.currency_id._convert(balance, self.currency_id, company, self.date or fields.Date.today(), round=False)
			line_debit, line_credit, line_amount_currency, line_currency_id = aml_obj.with_context(
				date=self.date)._compute_amount_fields(balance, self.currency_id, company.currency_id)
			counterpart_aml_dict = self._get_shared_move_line_vals(line_debit, line_credit, line_amount_currency, move.id, False)
			account = self._get_account_diff_currency(balance)
			analytic = account.account_tag_id and account.account_tag_id.ids or []
			counterpart_aml_dict.update({
				'name': "Diferencia de cambio",
				'account_id' : account.id,
				'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
				'partner_id': self.partner_id.id or False
				})
			aml_obj.with_context(skip_account_move_synchronization=True).create(counterpart_aml_dict)
			# obj = self.env['account.move'].write({'invoice_payments_widget': payments})
		return True

