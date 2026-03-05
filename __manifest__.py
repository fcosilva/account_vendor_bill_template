{
    "name": "Vendor Bill Templates",
    "version": "17.0.1.0.0",
    "summary": "Create recurring vendor bills from reusable templates",
    "author": "Openlab Ecuador",
    "license": "AGPL-3",
    "category": "Accounting",
    "depends": ["account", "hr_contract", "l10n_ec"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "wizard/vendor_bill_template_generate_wizard_views.xml",
        "wizard/vendor_bill_template_from_bill_wizard_views.xml",
        "wizard/vendor_bill_template_batch_from_bills_wizard_views.xml",
        "views/vendor_bill_template_views.xml",
        "views/account_move_views.xml"
    ],
    "installable": True,
    "application": False,
}
