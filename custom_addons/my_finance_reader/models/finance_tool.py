from odoo import models, fields, api

class FinanceTool(models.Model):
    _name = 'finance.tool'
    _description = 'Finanz Reader Werkzeug'

    name = fields.Char("Bezeichnung", default="Mein Finanz-Check")

    # Die Firmenwährung (wird automatisch gesetzt)
    currency_id = fields.Many2one(
        'res.currency',
        string="Leitwährung",
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    # KPIs (Summen)
    kpi_liq_1 = fields.Float("Liquidität 1 (Cash)", readonly=True)
    kpi_liq_2 = fields.Float("Liquidität 2 (Quick)", readonly=True)
    kpi_liq_3 = fields.Float("Liquidität 3 (Current)", readonly=True)

    kpi_total_aktiva = fields.Float("Summe Aktiva", readonly=True)
    kpi_total_passiva = fields.Float("Summe Passiva", readonly=True)
    kpi_short_term_debt = fields.Float("Kurzfr. Fremdkapital", readonly=True)

    # Zeilen (One2many Verbindungen)
    aktiva_line_ids = fields.One2many('finance.tool.line', 'tool_aktiva_id', string="Aktiva Zeilen")
    passiva_line_ids = fields.One2many('finance.tool.line', 'tool_passiva_id', string="Passiva Zeilen")

    def action_calculate_balance(self):
        """
        Hauptfunktion: Löscht alte Zeilen, berechnet Salden neu,
        rechnet Fremdwährungen um und speichert das Ergebnis.
        """
        # 1. Alte Zeilen löschen
        self.aktiva_line_ids.unlink()
        self.passiva_line_ids.unlink()

        # Kontotypen-Definitionen
        type_liquidity = ['asset_cash']
        type_receivable = ['asset_receivable']
        type_current_assets = ['asset_current', 'asset_prepayments']
        type_fixed_assets = ['asset_fixed', 'asset_non_current']
        type_short_term_liabilities = ['liability_payable', 'liability_credit_card', 'liability_current']
        type_long_term_equity = ['liability_non_current', 'equity', 'equity_unaffected']

        # Variablen für Summen
        asset_val_liq_1 = 0.0
        asset_val_liq_2 = 0.0
        asset_val_liq_3 = 0.0
        sum_kurzfr_fk = 0.0
        sum_aktiva = 0.0
        sum_passiva = 0.0

        new_aktiva_lines = []
        new_passiva_lines = []

        company = self.env.company
        main_curr = company.currency_id
        today = fields.Date.context_today(self)

        # Alle Konten der Firma suchen
        all_accounts = self.env['account.account'].search([
            ('deprecated', '=', False),
            ('company_id', '=', company.id)
        ])

        for acc in all_accounts:
            # A. Währung des Kontos bestimmen
            if acc.currency_id:
                line_curr_id = acc.currency_id.id
                acc_currency_obj = acc.currency_id
            else:
                line_curr_id = main_curr.id
                acc_currency_obj = main_curr

            # B. Saldo ermitteln
            domain = [('account_id', '=', acc.id), ('parent_state', '=', 'posted')]
            original_val = 0.0

            if acc.currency_id and acc.currency_id != main_curr:
                # Fremdwährung
                data = self.env['account.move.line'].read_group(domain, ['amount_currency'], [])
                if data and data[0]['amount_currency']:
                    original_val = data[0]['amount_currency']
            else:
                # Leitwährung
                data = self.env['account.move.line'].read_group(domain, ['balance'], [])
                if data and data[0]['balance']:
                    original_val = data[0]['balance']

            # --- ÄNDERUNG: Wir überspringen 0-Salden NICHT mehr ---
            # if abs(original_val) < 0.01:
            #    continue

            # C. Umrechnung in Leitwährung
            converted_val = acc_currency_obj._convert(
                original_val,
                main_curr,
                company,
                today
            )

            atype = acc.account_type

            # Datensatz vorbereiten
            line_vals = {
                'account_id': acc.id,                   # WICHTIG: Verknüpfung
                'code': acc.code,
                'name': acc.name,
                'original_amount': original_val,
                'original_currency_id': line_curr_id,
                'converted_amount': converted_val,
                'currency_id': main_curr.id,
            }

            # === ZUORDNUNG AKTIVA ===
            if atype in type_liquidity + type_receivable + type_current_assets + type_fixed_assets:
                sum_aktiva += converted_val

                if atype in type_liquidity:
                    asset_val_liq_1 += converted_val
                    asset_val_liq_2 += converted_val
                    asset_val_liq_3 += converted_val
                elif atype in type_receivable:
                    asset_val_liq_2 += converted_val
                    asset_val_liq_3 += converted_val
                elif atype in type_current_assets:
                    asset_val_liq_3 += converted_val

                new_aktiva_lines.append(line_vals)

            # === ZUORDNUNG PASSIVA ===
            elif atype in type_short_term_liabilities + type_long_term_equity:
                # Vorzeichen drehen
                line_vals['original_amount'] = original_val * -1
                line_vals['converted_amount'] = converted_val * -1

                sum_passiva += line_vals['converted_amount']

                if atype in type_short_term_liabilities:
                    sum_kurzfr_fk += line_vals['converted_amount']

                new_passiva_lines.append(line_vals)

        # --- SPEICHERN ---
        self.write({
            'kpi_liq_1': asset_val_liq_1 - sum_kurzfr_fk,
            'kpi_liq_2': asset_val_liq_2 - sum_kurzfr_fk,
            'kpi_liq_3': asset_val_liq_3 - sum_kurzfr_fk,
            'kpi_total_aktiva': sum_aktiva,
            'kpi_total_passiva': sum_passiva,
            'kpi_short_term_debt': sum_kurzfr_fk,
            'aktiva_line_ids': [(0, 0, x) for x in new_aktiva_lines],
            'passiva_line_ids': [(0, 0, x) for x in new_passiva_lines],
        })


class FinanceToolLine(models.Model):
    _name = 'finance.tool.line'
    _description = 'Einzelne Kontozeile'
    _order = 'code asc'

    tool_aktiva_id = fields.Many2one('finance.tool', string="Parent Aktiva")
    tool_passiva_id = fields.Many2one('finance.tool', string="Parent Passiva")

    account_id = fields.Many2one('account.account', string="Konto-Objekt", required=True)

    code = fields.Char("Nr.")
    name = fields.Char("Konto")

    # Der Kontotyp wird direkt vom verknüpften Konto geholt
    account_type = fields.Selection(related='account_id.account_type', string="Typ", store=True)

    # Währungsfelder
    original_currency_id = fields.Many2one('res.currency', string="Währung Orig.")
    original_amount = fields.Monetary(string="Betrag (Original)", currency_field='original_currency_id')

    currency_id = fields.Many2one('res.currency', string="Leitwährung")
    converted_amount = fields.Monetary(string="In Leitwährung", currency_field='currency_id')

    def action_view_journal_items(self):
        """ Öffnet die Buchungszeilen für dieses spezifische Konto """
        self.ensure_one()
        return {
            'name': f"Buchungen: {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'tree,form',
            'domain': [
                ('account_id', '=', self.account_id.id),
                ('parent_state', '=', 'posted')
            ],
            'context': {'create': False, 'search_default_posted': 1},
        }