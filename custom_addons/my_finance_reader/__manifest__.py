{
    'name': 'Simple Bilanz',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Schneller Liquiditäts-Check',
    'description': """
        Ein einfaches Tool zur Ansicht einer einfachen Bilanz mit Liquidität.
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