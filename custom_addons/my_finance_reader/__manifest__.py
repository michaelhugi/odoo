{
    'name': "Finanzübersicht",
    'summary': "Liest Finanzdaten aus",
    'version': '1.0',
    'depends': ['base', 'account'],

    # HIER DIE ÄNDERUNG:
    'data': [
        'security/ir.model.access.csv',
        'views/finance_tool_view.xml',
    ],

    'installable': True,
    'application': True,
}