import calendar
import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class VendorBillTemplate(models.Model):
    _name = "vendor.bill.template"
    _description = "Vendor Bill Template"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        domain="[(\"supplier_rank\", \">\", 0)]",
    )
    contract_id = fields.Many2one(
        "hr.contract",
        string="Employee Contract",
        domain="[('company_id', '=', company_id)]",
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[(\"type\", \"=\", \"purchase\"), (\"company_id\", \"=\", company_id)]",
    )
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id
    )
    payment_term_id = fields.Many2one("account.payment.term")
    partner_bank_id = fields.Many2one(
        "res.partner.bank",
        domain="[('partner_id', '=', partner_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    l10n_ec_sri_payment_id = fields.Many2one("l10n_ec.sri.payment")
    bill_date_day = fields.Integer(default=1, required=True)
    auto_generate = fields.Boolean(default=False)
    prevent_duplicate_period = fields.Boolean(default=True)
    use_reference_sequence = fields.Boolean(default=True)
    sequence_id = fields.Many2one("ir.sequence", copy=False, string="Reference Sequence")
    line_ids = fields.One2many("vendor.bill.template.line", "template_id", copy=True)
    note = fields.Text()

    generated_move_ids = fields.One2many("account.move", "vendor_bill_template_id")
    generated_count = fields.Integer(compute="_compute_generated_count")
    last_generated_date = fields.Date(readonly=True, copy=False)
    last_generated_move_id = fields.Many2one("account.move", readonly=True, copy=False)
    next_generation_date = fields.Date(compute="_compute_next_generation_date")
    amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_amount_total")

    _sql_constraints = [
        (
            "vendor_bill_template_name_company_unique",
            "unique(name, company_id)",
            "Template name must be unique by company.",
        )
    ]

    @api.constrains("bill_date_day")
    def _check_bill_date_day(self):
        for record in self:
            if record.bill_date_day < 1 or record.bill_date_day > 31:
                raise ValidationError(_("Generation day must be between 1 and 31."))

    def _get_contract_partner_domain(self):
        self.ensure_one()
        domain = [("company_id", "=", self.company_id.id)]
        if not self.partner_id:
            return domain

        employee_fields = self.env["hr.employee"]._fields
        partner_conditions = []
        if "address_home_id" in employee_fields:
            partner_conditions.append(("employee_id.address_home_id", "=", self.partner_id.id))
        if "work_contact_id" in employee_fields:
            partner_conditions.append(("employee_id.work_contact_id", "=", self.partner_id.id))

        if not partner_conditions:
            return [("id", "=", 0)]
        if len(partner_conditions) == 1:
            return domain + partner_conditions
        return domain + ["|"] + partner_conditions

    def _is_contract_matching_partner(self, contract):
        self.ensure_one()
        if not contract:
            return True
        if contract.company_id != self.company_id:
            return False
        if not self.partner_id:
            return True

        employee = contract.employee_id
        employee_fields = employee._fields
        matches = False
        if "address_home_id" in employee_fields:
            matches = matches or employee.address_home_id == self.partner_id
        if "work_contact_id" in employee_fields:
            matches = matches or employee.work_contact_id == self.partner_id
        return matches

    @api.onchange("partner_id", "company_id")
    def _onchange_contract_domain(self):
        domain = self._get_contract_partner_domain()
        if self.contract_id and not self._is_contract_matching_partner(self.contract_id):
            self.contract_id = False
        return {"domain": {"contract_id": domain}}

    @api.constrains("contract_id", "partner_id", "company_id")
    def _check_contract_partner_consistency(self):
        for record in self.filtered("contract_id"):
            if not record._is_contract_matching_partner(record.contract_id):
                raise ValidationError(
                    _(
                        "Selected contract must belong to the same company and to the same contact/employee."
                    )
                )

    @api.depends("generated_move_ids")
    def _compute_generated_count(self):
        grouped_data = self.env["account.move"].read_group(
            [("vendor_bill_template_id", "in", self.ids)],
            ["vendor_bill_template_id"],
            ["vendor_bill_template_id"],
        )
        count_by_template = {
            data["vendor_bill_template_id"][0]: data["vendor_bill_template_id_count"]
            for data in grouped_data
        }
        for template in self:
            template.generated_count = count_by_template.get(template.id, 0)

    @api.depends("line_ids.price_unit", "line_ids.quantity")
    def _compute_amount_total(self):
        for template in self:
            template.amount_total = sum(template.line_ids.mapped("subtotal"))

    @api.depends("bill_date_day")
    def _compute_next_generation_date(self):
        today = fields.Date.context_today(self)
        for template in self:
            template.next_generation_date = template._compute_candidate_date(today)

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        for template in templates.filtered(lambda t: not t.sequence_id):
            template.sequence_id = self.env["ir.sequence"].create(template._prepare_sequence_vals())
        return templates

    def _prepare_sequence_vals(self):
        self.ensure_one()
        sequence_name = _("Vendor Bill Template %s") % self.name
        return {
            "name": sequence_name,
            "code": f"vendor.bill.template.{self.id}",
            "prefix": "VB/%(year)s/%(month)s/",
            "padding": 4,
            "company_id": self.company_id.id,
            "implementation": "no_gap",
        }

    def _compute_candidate_date(self, base_date):
        self.ensure_one()
        year = base_date.year
        month = base_date.month
        day = min(self.bill_date_day, calendar.monthrange(year, month)[1])
        candidate = date(year, month, day)
        if candidate < base_date:
            month = month + 1
            if month > 12:
                month = 1
                year += 1
            day = min(self.bill_date_day, calendar.monthrange(year, month)[1])
            candidate = date(year, month, day)
        return candidate

    def _get_period_bounds(self, generation_date):
        first_day = generation_date.replace(day=1)
        last_day = generation_date.replace(
            day=calendar.monthrange(generation_date.year, generation_date.month)[1]
        )
        return first_day, last_day

    def _has_generated_bill_in_period(self, generation_date):
        self.ensure_one()
        first_day, last_day = self._get_period_bounds(generation_date)
        count = self.env["account.move"].search_count(
            [
                ("vendor_bill_template_id", "=", self.id),
                ("move_type", "=", "in_invoice"),
                ("state", "!=", "cancel"),
                ("invoice_date", ">=", first_day),
                ("invoice_date", "<=", last_day),
            ]
        )
        return bool(count)

    def _next_bill_reference(self):
        self.ensure_one()
        if not self.use_reference_sequence or not self.sequence_id:
            return False
        return self.sequence_id.next_by_id()

    @api.model
    def _increment_document_number(self, number):
        if not number:
            return False
        match = re.match(r"^(.*?)(\d+)$", number)
        if not match:
            return False
        prefix, numeric_part = match.groups()
        next_number = int(numeric_part) + 1
        return f"{prefix}{next_number:0{len(numeric_part)}d}"

    @api.model
    def _extract_vendor_document_number(self, move):
        candidates = [
            move.l10n_latam_document_number if "l10n_latam_document_number" in move._fields else False,
            move.ref,
            move.name,
        ]
        for value in candidates:
            if not value:
                continue
            match = re.search(r"\b(\d{3}-\d{3}-\d{9})\b", value)
            if match:
                return match.group(1)
        return False

    def _next_vendor_document_number(self):
        self.ensure_one()
        move_model = self.env["account.move"]
        if "l10n_latam_document_number" not in move_model._fields:
            return False

        recent_bills = move_model.search(
            [
                ("move_type", "=", "in_invoice"),
                ("state", "!=", "cancel"),
                ("partner_id", "=", self.partner_id.id),
                ("company_id", "=", self.company_id.id),
            ],
            order="invoice_date desc, id desc",
            limit=50,
        )
        for bill in recent_bills:
            candidate_number = self._extract_vendor_document_number(bill)
            next_number = self._increment_document_number(candidate_number)
            if next_number:
                return next_number
        return False

    def _apply_vendor_document_number(self, move, document_number):
        if not move or not document_number:
            return
        if "l10n_latam_document_type_id" in move._fields and move.l10n_latam_document_type_id:
            formatted_number = document_number
            if hasattr(move, "_skip_format_document_number") and not move._skip_format_document_number():
                formatted_number = move.l10n_latam_document_type_id._format_document_number(
                    document_number
                )
            move.name = "%s %s" % (move.l10n_latam_document_type_id.doc_code_prefix, formatted_number)
            return
        move.name = document_number

    def _prepare_move_line_vals(self):
        self.ensure_one()
        line_vals = []
        for line in self.line_ids.sorted("sequence"):
            values = {
                "name": line.name,
                "product_id": line.product_id.id,
                "quantity": line.quantity,
                "price_unit": line.price_unit,
                "tax_ids": [(6, 0, line.tax_ids.ids)],
                "analytic_distribution": line.analytic_distribution or False,
            }
            if line.account_id:
                values["account_id"] = line.account_id.id
            line_vals.append((0, 0, values))
        return line_vals

    def _prepare_move_vals(self, generation_date):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Template %s has no lines.") % self.name)
        reference = self._next_bill_reference()
        move_vals = {
            "move_type": "in_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": generation_date,
            "date": generation_date,
            "journal_id": self.journal_id.id,
            "currency_id": self.currency_id.id,
            "invoice_payment_term_id": self.payment_term_id.id,
            "partner_bank_id": self.partner_bank_id.id,
            "l10n_ec_sri_payment_id": self.l10n_ec_sri_payment_id.id,
            "narration": self.note,
            "ref": reference,
            "invoice_origin": self.name,
            "vendor_bill_template_id": self.id,
            "employee_contract_id": self.contract_id.id,
            "invoice_line_ids": self._prepare_move_line_vals(),
            "company_id": self.company_id.id,
        }
        return move_vals

    def action_generate_bill(self, generation_date=False, allow_duplicates=False):
        generation_date = generation_date or fields.Date.context_today(self)
        created_moves = self.env["account.move"]
        for template in self:
            if template.prevent_duplicate_period and not allow_duplicates:
                if template._has_generated_bill_in_period(generation_date):
                    raise UserError(
                        _(
                            "Template %(template)s already generated a vendor bill in %(month)s/%(year)s."
                        )
                        % {
                            "template": template.name,
                            "month": str(generation_date.month).zfill(2),
                            "year": generation_date.year,
                        }
                    )
            next_document_number = template._next_vendor_document_number()
            move = self.env["account.move"].create(template._prepare_move_vals(generation_date))
            template._apply_vendor_document_number(move, next_document_number)
            template.last_generated_date = generation_date
            template.last_generated_move_id = move.id
            created_moves |= move

        return {
            "name": _("Generated Vendor Bills"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", created_moves.ids)],
            "context": {"create": False},
        }

    def action_generate_bill_today(self):
        self.ensure_one()
        return self.action_generate_bill(fields.Date.context_today(self), allow_duplicates=False)

    def action_open_generate_wizard(self):
        if not self:
            raise UserError(_("Select at least one template."))
        return {
            "name": _("Generate Vendor Bills"),
            "type": "ir.actions.act_window",
            "res_model": "vendor.bill.template.generate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_ids": self.ids},
        }

    def action_view_generated_bills(self):
        self.ensure_one()
        return {
            "name": _("Generated Vendor Bills"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("vendor_bill_template_id", "=", self.id)],
            "context": {
                "default_move_type": "in_invoice",
                "create": False,
            },
        }

    def action_open_reference_sequence(self):
        self.ensure_one()
        if not self.sequence_id:
            raise UserError(_("No sequence configured for this template."))
        return {
            "name": _("Reference Sequence"),
            "type": "ir.actions.act_window",
            "res_model": "ir.sequence",
            "view_mode": "form",
            "res_id": self.sequence_id.id,
            "target": "current",
        }

    @api.model
    def cron_generate_vendor_bills(self):
        today = fields.Date.context_today(self)
        templates = self.search([
            ("active", "=", True),
            ("auto_generate", "=", True),
        ])
        for template in templates:
            due_day = min(
                template.bill_date_day,
                calendar.monthrange(today.year, today.month)[1],
            )
            if today.day != due_day:
                continue
            try:
                template.action_generate_bill(today, allow_duplicates=False)
            except UserError:
                continue


class VendorBillTemplateLine(models.Model):
    _name = "vendor.bill.template.line"
    _description = "Vendor Bill Template Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    template_id = fields.Many2one(
        "vendor.bill.template", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="template_id.company_id", store=True)
    currency_id = fields.Many2one(related="template_id.currency_id")

    name = fields.Char(required=True)
    product_id = fields.Many2one("product.product")
    account_id = fields.Many2one(
        "account.account",
        domain="[(\"deprecated\", \"=\", False), (\"company_id\", \"=\", company_id)]",
    )
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Monetary(required=True)
    tax_ids = fields.Many2many("account.tax")
    analytic_distribution = fields.Json()

    subtotal = fields.Monetary(compute="_compute_subtotal", currency_field="currency_id")

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
