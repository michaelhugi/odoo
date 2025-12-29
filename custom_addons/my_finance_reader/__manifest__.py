{
    'name': 'Mein Finanz Cockpit',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Schneller Liquiditäts-Check',
    'description': """
        Ein einfaches Tool zur Berechnung von Liquidität
        basierend auf Odoo Buchungszeilen.
    """,
    'author': 'Michael Hugi',
    'depends': ['base', 'account'],  # WICHTIG: Wir hängen vom Accounting Modul ab
    'data': [
        'security/ir.model.access.csv', # Zugriffsrechte zuerst laden!
        'views/finance_tool_view.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}