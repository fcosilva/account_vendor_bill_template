from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    vendor_bill_template_id = fields.Many2one(
        "vendor.bill.template",
        string="Vendor Bill Template",
        copy=False,
        readonly=True,
    )
    employee_contract_id = fields.Many2one(
        "hr.contract",
        string="Employee Contract",
        copy=False,
    )

    def action_open_template_from_bill_wizard(self):
        self.ensure_one()
        if self.move_type != "in_invoice":
            return False
        return {
            "name": _("Create Template from Vendor Bill"),
            "type": "ir.actions.act_window",
            "res_model": "vendor.bill.template.from.bill.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_bill_id": self.id,
            },
        }
