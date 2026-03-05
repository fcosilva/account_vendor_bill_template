from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VendorBillTemplateFromBillWizard(models.TransientModel):
    _name = "vendor.bill.template.from.bill.wizard"
    _description = "Create Vendor Bill Template from Bill"

    bill_id = fields.Many2one(
        "account.move",
        required=True,
        domain=[("move_type", "=", "in_invoice")],
    )
    name = fields.Char(required=True)
    auto_generate = fields.Boolean(default=False)
    bill_date_day = fields.Integer(default=1, required=True)
    prevent_duplicate_period = fields.Boolean(default=True)
    use_reference_sequence = fields.Boolean(default=True)

    @staticmethod
    def _is_template_line(line):
        return line.display_type not in ("line_section", "line_note")

    def _prepare_template_line_vals(self, bill):
        line_vals = []
        for line in bill.invoice_line_ids.filtered(self._is_template_line):
            line_vals.append(
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
        return line_vals

    def action_create_template(self):
        self.ensure_one()
        if self.bill_id.move_type != "in_invoice":
            raise UserError(_("You can only use vendor bills for this action."))

        if not self.bill_id.invoice_line_ids.filtered(self._is_template_line):
            raise UserError(_("Selected vendor bill does not contain invoice lines."))

        bill = self.bill_id
        template = self.env["vendor.bill.template"].create(
            {
                "name": self.name,
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
                "line_ids": self._prepare_template_line_vals(bill),
            }
        )

        return {
            "name": _("Vendor Bill Template"),
            "type": "ir.actions.act_window",
            "res_model": "vendor.bill.template",
            "view_mode": "form",
            "res_id": template.id,
            "target": "current",
        }

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        bill_id = self.env.context.get("default_bill_id")
        if bill_id and "name" in fields_list:
            bill = self.env["account.move"].browse(bill_id)
            bill_label = bill.ref or bill.name or str(bill.id)
            values["name"] = _("Template from %s") % bill_label
        return values
