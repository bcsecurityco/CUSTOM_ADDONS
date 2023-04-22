from odoo import models, fields, api, _

class AccountPaymentRegister(models.TransientModel):
	_inherit='account.payment.register'

	account_id = fields.Many2one(
		comodel_name='account.account',
		string='Cuenta de origen',
		store=True, readonly=False,
		domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
		check_company=True)
	destination_account_id = fields.Many2one(
		comodel_name='account.account',
		string='Destination Account',
		store=True, readonly=False,
		domain="[('user_type_id.type', 'in', ('receivable', 'payable')), ('company_id', '=', company_id)]",
		check_company=True)
	change_destination_account = fields.Char(string="cambio de cuenta destino")

	def _create_payment_vals_from_wizard(self):
		payment_vals = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard()
		if self.account_id:
			payment_vals['account_id'] = self.account_id.id
		if self.destination_account_id:
			payment_vals['destination_account_id'] = self.destination_account_id.id
		return payment_vals

class AccountMove(models.Model):
	_inherit = "account.move"

	def _get_reconciled_invoices(self):
		"""Helper used to retrieve the reconciled payments on this journal entry"""
		if self._context.get('account_id'):
			reconciled_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable') and line.account_id == self._context.get('account_id'))
		else:
			reconciled_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
		reconciled_amls = reconciled_lines.mapped('matched_debit_ids.debit_move_id') + \
						  reconciled_lines.mapped('matched_credit_ids.credit_move_id')
		return reconciled_amls.move_id.filtered(lambda move: move.is_invoice(include_receipts=True))

class AccountMoveLine(models.Model):
	_inherit = "account.move.line"

	@api.depends('ref', 'move_id')
	def name_get(self):
		super().name_get()
		result = []
		for line in self:
			if self._context.get('show_number', False):
				name = '%s - %s' %(line.move_id.name, abs(line.amount_residual_currency or line.amount_residual))
				result.append((line.id, name))
			elif line.ref:
				result.append((line.id, (line.move_id.name or '') + '(' + line.ref + ')'))
			else:
				result.append((line.id, line.move_id.name))
		return result

	# def _create_exchange_difference_move(self):
	# 	exchange_move = super(AccountMoveLine, self)._create_exchange_difference_move()
	# 	exchange_move_lines = exchange_move.line_ids.filtered(lambda line: line.account_id == account)
	# 	self._append_move_diff_payment(aml_to_fix, move)
	# 	return

	def _append_move_diff_payment(self, aml_to_fix, move):
		for aml in aml_to_fix:
			if aml.payment_id:
				aml.payment_id.move_diff_ids += move

	def reconcile(self):
		res = super(AccountMoveLine, self).reconcile()
		if res.get('full_reconcile'):
			exchange_move = res.get('full_reconcile').exchange_move_id
			if exchange_move:
				line_ids = exchange_move.line_ids
				self._append_move_diff_payment(line_ids, exchange_move)
		return res

class AccountFullReconcile(models.Model):
	_inherit = "account.full.reconcile"

	@api.model
	def create(self, vals):
		self._set_invoice_diff_by_aml(vals)
		res = super(AccountFullReconcile, self).create(vals)
		return res

	def _set_invoice_diff_by_aml(self, vals):
		if vals.get('reconciled_line_ids'):
			move_lines = self.env['account.move.line'].browse(vals['reconciled_line_ids'][0][2])
			extrange_diff_pay = move_lines.filtered(lambda l: l.name == _('Currency exchange rate difference'))
			if extrange_diff_pay:
				for rec in move_lines - extrange_diff_pay:
					if rec.invoice_id:
						values = {
							'ref': rec.invoice_id.number
							}
						extrange_diff_pay.write(values)
