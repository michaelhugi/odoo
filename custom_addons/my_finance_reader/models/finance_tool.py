from odoo import models, fields, api

# 1. DAS HAUPT-WERKZEUG
class FinanceTool(models.Model):
    _name = 'finance.tool'
    _description = 'Finanz Reader Werkzeug'

    name = fields.Char("Bezeichnung", default="Mein Finanz-Check")

    # KPIs (Summen)
    kpi_liq_1 = fields.Float("Liquidität 1 (Cash)", readonly=True)
    kpi_liq_2 = fields.Float("Liquidität 2 (Quick)", readonly=True)
    kpi_liq_3 = fields.Float("Liquidität 3 (Current)", readonly=True)

    kpi_total_aktiva = fields.Float("Summe Aktiva", readonly=True)
    kpi_total_passiva = fields.Float("Summe Passiva", readonly=True)
    kpi_short_term_debt = fields.Float("Kurzfr. Fremdkapital", readonly=True)

    # NEU: Verknüpfung zu den Zeilen (One2many)
    # Wir brauchen zwei Listen, damit wir sie links und rechts trennen können
    aktiva_line_ids = fields.One2many('finance.tool.line', 'tool_aktiva_id', string="Aktiva Zeilen", readonly=True)
    passiva_line_ids = fields.One2many('finance.tool.line', 'tool_passiva_id', string="Passiva Zeilen", readonly=True)

    def action_calculate_balance(self):
        # 1. Alte Zeilen löschen (damit wir nicht doppelt speichern bei erneutem Klick)
        self.aktiva_line_ids.unlink()
        self.passiva_line_ids.unlink()

        account_model = self.env['account.account']

        # Definitionen
        type_liquidity = ['asset_cash']
        type_receivable = ['asset_receivable']
        type_current_assets = ['asset_current', 'asset_prepayments']
        type_fixed_assets = ['asset_fixed', 'asset_non_current']

        type_short_term_liabilities = ['liability_payable', 'liability_credit_card', 'liability_current']
        type_long_term_equity = ['liability_non_current', 'equity', 'equity_unaffected']

        # Variablen
        asset_val_liq_1 = 0.0
        asset_val_liq_2 = 0.0
        asset_val_liq_3 = 0.0
        sum_kurzfr_fk = 0.0
        sum_aktiva = 0.0
        sum_passiva = 0.0

        # Wir sammeln die Zeilen jetzt in Listen, um sie am Ende zu speichern
        new_aktiva_lines = []
        new_passiva_lines = []

        # Konten suchen (Nur aktuelle Firma)
        all_accounts = account_model.search([
            ('deprecated', '=', False),
            ('company_id', '=', self.env.company.id)
        ])

        for acc in all_accounts:
            saldo = acc.current_balance
            if saldo == 0:
                continue

            atype = acc.account_type

            # === AKTIVA ===
            if atype in type_liquidity + type_receivable + type_current_assets + type_fixed_assets:
                # Summen rechnen
                sum_aktiva += saldo
                if atype in type_liquidity:
                    asset_val_liq_1 += saldo; asset_val_liq_2 += saldo; asset_val_liq_3 += saldo
                elif atype in type_receivable:
                    asset_val_liq_2 += saldo; asset_val_liq_3 += saldo
                elif atype in type_current_assets:
                    asset_val_liq_3 += saldo

                # Zeile vorbereiten
                new_aktiva_lines.append({
                    'code': acc.code,
                    'name': acc.name,
                    'amount': saldo,
                })

            # === PASSIVA ===
            elif atype in type_short_term_liabilities + type_long_term_equity:
                val_positive = saldo * -1
                sum_passiva += val_positive

                if atype in type_short_term_liabilities:
                    sum_kurzfr_fk += val_positive

                # Zeile vorbereiten
                new_passiva_lines.append({
                    'code': acc.code,
                    'name': acc.name,
                    'amount': val_positive,
                })

        # --- SPEICHERN ---
        self.write({
            'kpi_liq_1': asset_val_liq_1 - sum_kurzfr_fk,
            'kpi_liq_2': asset_val_liq_2 - sum_kurzfr_fk,
            'kpi_liq_3': asset_val_liq_3 - sum_kurzfr_fk,
            'kpi_total_aktiva': sum_aktiva,
            'kpi_total_passiva': sum_passiva,
            'kpi_short_term_debt': sum_kurzfr_fk,
            # Hier schreiben wir die Listen in die Datenbank (Magic Tuple 0,0)
            'aktiva_line_ids': [(0, 0, line) for line in new_aktiva_lines],
            'passiva_line_ids': [(0, 0, line) for line in new_passiva_lines],
        })

# 2. DAS NEUE MODELL FÜR DIE ZEILEN (Tabelle in DB)
class FinanceToolLine(models.Model):
    _name = 'finance.tool.line'
    _description = 'Einzelne Kontozeile'
    # Sortierung nach Kontonummer
    _order = 'code asc'

    # Verknüpfungen zurück zum Haupt-Tool
    tool_aktiva_id = fields.Many2one('finance.tool', string="Parent Tool Aktiva")
    tool_passiva_id = fields.Many2one('finance.tool', string="Parent Tool Passiva")

    code = fields.Char("Nr.")
    name = fields.Char("Konto")
    amount = fields.Float("Saldo")