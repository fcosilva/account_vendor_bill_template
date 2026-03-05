from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestVendorBillTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Freelance QA",
                "supplier_rank": 1,
                "company_id": cls.company.id,
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.expense_account = cls.env["account.account"].search(
            [
                ("company_id", "=", cls.company.id),
                ("account_type", "like", "expense"),
                ("deprecated", "=", False),
            ],
            limit=1,
        )
        cls.assertTrue(cls.journal, "Missing purchase journal for tests")
        cls.assertTrue(cls.expense_account, "Missing expense account for tests")

    def _create_template(self):
        return self.env["vendor.bill.template"].create(
            {
                "name": "Monthly Freelancer",
                "company_id": self.company.id,
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
                "currency_id": self.company.currency_id.id,
                "bill_date_day": 5,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Freelance Services",
                            "account_id": self.expense_account.id,
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )

    def test_generate_vendor_bill_from_template(self):
        template = self._create_template()
        generation_date = fields.Date.from_string("2026-03-05")

        template.action_generate_bill(generation_date=generation_date)

        bill = self.env["account.move"].search(
            [
                ("vendor_bill_template_id", "=", template.id),
                ("move_type", "=", "in_invoice"),
            ],
            limit=1,
        )
        self.assertTrue(bill, "Vendor bill should be created from template")
        self.assertEqual(bill.partner_id, self.partner)
        self.assertEqual(bill.invoice_date, generation_date)
        self.assertTrue(bill.ref, "Reference should be set by sequence")

    def test_prevent_duplicate_generation_in_same_month(self):
        template = self._create_template()
        generation_date = fields.Date.from_string("2026-03-05")

        template.action_generate_bill(generation_date=generation_date)

        with self.assertRaises(UserError):
            template.action_generate_bill(generation_date=generation_date)

    def test_create_template_from_existing_bill_wizard(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
                "invoice_date": fields.Date.from_string("2026-03-05"),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Freelance Services",
                            "account_id": self.expense_account.id,
                            "quantity": 1,
                            "price_unit": 1200,
                        },
                    )
                ],
            }
        )

        wizard = self.env["vendor.bill.template.from.bill.wizard"].create(
            {
                "bill_id": bill.id,
                "name": "Template From Bill",
                "bill_date_day": 10,
            }
        )
        wizard.action_create_template()

        template = self.env["vendor.bill.template"].search(
            [("name", "=", "Template From Bill")], limit=1
        )
        self.assertTrue(template)
        self.assertEqual(template.partner_id, bill.partner_id)
        self.assertEqual(len(template.line_ids), 1)
