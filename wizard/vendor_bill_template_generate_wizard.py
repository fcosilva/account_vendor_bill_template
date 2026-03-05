from odoo import _, fields, models
from odoo.exceptions import UserError


class VendorBillTemplateGenerateWizard(models.TransientModel):
    _name = "vendor.bill.template.generate.wizard"
    _description = "Generate Vendor Bills from Templates"

    generation_date = fields.Date(required=True, default=fields.Date.context_today)
    template_ids = fields.Many2many(
        "vendor.bill.template",
        string="Templates",
        required=True,
        domain=[("active", "=", True)],
    )
    allow_duplicates = fields.Boolean(
        string="Allow duplicate generation in same period",
        default=False,
    )
    show_template_selector = fields.Boolean(default=lambda self: not bool(self.env.context.get("active_ids")))

    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            templates = self.env["vendor.bill.template"].browse(active_ids).filtered("active")
            if templates:
                values["template_ids"] = [(6, 0, templates.ids)]
        return values

    def action_generate(self):
        self.ensure_one()
        if not self.template_ids:
            raise UserError(_("Select at least one template."))
        return self.template_ids.action_generate_bill(
            generation_date=self.generation_date,
            allow_duplicates=self.allow_duplicates,
        )
