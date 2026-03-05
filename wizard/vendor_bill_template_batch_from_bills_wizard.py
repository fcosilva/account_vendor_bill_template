from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VendorBillTemplateBatchFromBillsWizard(models.TransientModel):
    _name = "vendor.bill.template.batch.from.bills.wizard"
    _description = "Create Vendor Bill Templates from Selected Bills"

    bill_ids = fields.Many2many(
        "account.move",
        string="Vendor Bills",
        required=True,
        domain=[("move_type", "=", "in_invoice")],
    )
    name_prefix = fields.Char(default="Template")
    auto_generate = fields.Boolean(default=False)
    bill_date_day = fields.Integer(default=1, required=True)
    prevent_duplicate_period = fields.Boolean(default=True)
    use_reference_sequence = fields.Boolean(default=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids and "bill_ids" in fields_list:
            bills = self.env["account.move"].browse(active_ids).filtered(
                lambda m: m.move_type == "in_invoice"
            )
            values["bill_ids"] = [(6, 0, bills.ids)]
        return values

    def _get_unique_name(self, base_name, company_id):
        name = base_name
        index = 2
        while self.env["vendor.bill.template"].search_count(
            [("name", "=", name), ("company_id", "=", company_id)]
        ):
            name = _("%s (%s)") % (base_name, index)
            index += 1
        return name

    def _prepare_line_vals(self, bill):
        lines = []
        for line in bill.invoice_line_ids.filtered(self._is_template_line):
            lines.append(
                (
                    0,
                    0,
                    {
                        "sequence": line.sequence,
                        "name": line.name,
                        "product_id": line.product_id.id,
                        "account_id": line.account_id.id,
                        "quantity": line.quantity,
                        "price_unit": line.price_unit,
                        "tax_ids": [(6, 0, line.tax_ids.ids)],
                        "analytic_distribution": line.analytic_distribution or False,
                    },
                )
            )
        return lines

    def action_create_templates(self):
        self.ensure_one()
        bills = self.bill_ids.filtered(lambda b: b.move_type == "in_invoice")
        if not bills:
            raise UserError(_("Select at least one vendor bill."))

        templates = self.env["vendor.bill.template"]
        for bill in bills:
            lines = self._prepare_line_vals(bill)
            if not lines:
                continue

            bill_label = bill.ref or bill.name or str(bill.id)
            base_name = _("%s - %s") % (self.name_prefix or _("Template"), bill_label)
            unique_name = self._get_unique_name(base_name, bill.company_id.id)

            template = self.env["vendor.bill.template"].create(
                {
                    "name": unique_name,
                    "company_id": bill.company_id.id,
                    "partner_id": bill.partner_id.id,
                    "contract_id": bill.employee_contract_id.id,
                    "journal_id": bill.journal_id.id,
                    "currency_id": bill.currency_id.id,
                    "payment_term_id": bill.invoice_payment_term_id.id,
                    "partner_bank_id": bill.partner_bank_id.id,
                    "l10n_ec_sri_payment_id": bill.l10n_ec_sri_payment_id.id,
                    "bill_date_day": self.bill_date_day,
                    "auto_generate": self.auto_generate,
                    "prevent_duplicate_period": self.prevent_duplicate_period,
                    "use_reference_sequence": self.use_reference_sequence,
                    "note": bill.narration,
                    "line_ids": lines,
                }
            )
            templates |= template

        if not templates:
            raise UserError(_("No templates were created. Selected bills have no invoice lines."))

        return {
            "name": _("Vendor Bill Templates"),
            "type": "ir.actions.act_window",
            "res_model": "vendor.bill.template",
            "view_mode": "list,form",
            "domain": [("id", "in", templates.ids)],
        }
    @staticmethod
    def _is_template_line(line):
        return line.display_type not in ("line_section", "line_note")
