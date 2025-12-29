from odoo import models, fields, api

class FinanceTool(models.Model):
    _name = 'finance.tool'
    _description = 'Finanz Reader Werkzeug'

    name = fields.Char("Bezeichnung", default="Mein Finanz-Check")

    currency_id = fields.Many2one(
        'res.currency',
        string="Leitwährung",
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    kpi_liq_1 = fields.Float("Liquidität 1 (Cash)", readonly=True)
    kpi_liq_2 = fields.Float("Liquidität 2 (Quick)", readonly=True)
    kpi_liq_3 = fields.Float("Liquidität 3 (Current)", readonly=True)
    kpi_total_aktiva = fields.Float("Summe Aktiva", readonly=True)
    kpi_total_passiva = fields.Float("Summe Passiva", readonly=True)
    kpi_short_term_debt = fields.Float("Kurzfr. Fremdkapital", readonly=True)

    aktiva_line_ids = fields.One2many('finance.tool.line', 'tool_aktiva_id', string="Aktiva Zeilen")
    passiva_line_ids = fields.One2many('finance.tool.line', 'tool_passiva_id', string="Passiva Zeilen")

    def action_calculate_balance(self):
        self.aktiva_line_ids.unlink()
        self.passiva_line_ids.unlink()

        # Konfiguration
        PRIORITY_MAP = {
            'asset_cash': (10, "FLÜSSIGE MITTEL"),
            'asset_receivable': (20, "FORDERUNGEN"),
            'asset_current': (30, "UMLAUFVERMÖGEN"),
            'asset_prepayments': (35, "RECHNUNGSABGRENZUNG"),
            'asset_fixed': (40, "ANLAGEVERMÖGEN"),
            'asset_non_current': (45, "LANGFRISTIGES VERMÖGEN"),

            'liability_payable': (10, "VERBINDLICHKEITEN"),
            'liability_credit_card': (15, "KREDITKARTEN"),
            'liability_current': (20, "KURZFR. VERBINDLICHKEITEN"),
            'liability_non_current': (50, "LANGFR. VERBINDLICHKEITEN"),
            'equity': (60, "EIGENKAPITAL"),
            'equity_unaffected': (70, "JAHRESERGEBNIS"),
        }

        type_liquidity = ['asset_cash']
        type_receivable = ['asset_receivable']
        type_current_assets = ['asset_current', 'asset_prepayments']
        type_fixed_assets = ['asset_fixed', 'asset_non_current']
        type_short_term_liabilities = ['liability_payable', 'liability_credit_card', 'liability_current']
        type_long_term_equity = ['liability_non_current', 'equity', 'equity_unaffected']

        asset_val_liq_1 = 0.0; asset_val_liq_2 = 0.0; asset_val_liq_3 = 0.0
        sum_kurzfr_fk = 0.0; sum_aktiva = 0.0; sum_passiva = 0.0

        company = self.env.company
        main_curr = company.currency_id
        today = fields.Date.context_today(self)

        all_accounts = self.env['account.account'].search([
            ('deprecated', '=', False),
            ('company_id', '=', company.id)
        ])

        # 1. Summen berechnen
        group_totals = {}
        processed_accounts = []

        for acc in all_accounts:
            domain = [('account_id', '=', acc.id), ('parent_state', '=', 'posted')]
            original_val = 0.0

            if acc.currency_id and acc.currency_id != main_curr:
                data = self.env['account.move.line'].read_group(domain, ['amount_currency'], [])
                if data and data[0]['amount_currency']: original_val = data[0]['amount_currency']
            else:
                data = self.env['account.move.line'].read_group(domain, ['balance'], [])
                if data and data[0]['balance']: original_val = data[0]['balance']

            acc_curr = acc.currency_id if acc.currency_id else main_curr
            converted_val = acc_curr._convert(original_val, main_curr, company, today)

            if acc.account_type in type_short_term_liabilities + type_long_term_equity:
                val_for_sum = converted_val * -1
            else:
                val_for_sum = converted_val

            atype = acc.account_type
            if atype not in group_totals: group_totals[atype] = 0.0
            group_totals[atype] += val_for_sum

            processed_accounts.append({
                'acc': acc,
                'original_val': original_val,
                'converted_val': converted_val,
                'val_final': val_for_sum
            })

        # 2. Zeilen erstellen
        def get_sort_key(item):
            a = item['acc']
            atype = a.account_type if a.account_type else 'other'
            prio = PRIORITY_MAP.get(atype, (999, ""))[0]
            return (prio, a.code)

        sorted_items = sorted(processed_accounts, key=get_sort_key)

        last_type_aktiva = None
        last_type_passiva = None
        seq_aktiva = 1
        seq_passiva = 1

        new_aktiva_lines = []
        new_passiva_lines = []

        for item in sorted_items:
            acc = item['acc']
            atype = acc.account_type
            group_label = PRIORITY_MAP.get(atype, (999, "Sonstiges"))[1]
            val_final = item['val_final']
            converted_val_raw = item['converted_val']
            original_val_raw = item['original_val']

            # BLAU wenn Wert vorhanden
            make_highlight = abs(val_final) > 0.01
            line_curr_id = acc.currency_id.id if acc.currency_id else main_curr.id

            # === AKTIVA ===
            if atype in type_liquidity + type_receivable + type_current_assets + type_fixed_assets:
                if atype != last_type_aktiva:
                    total_grp = group_totals.get(atype, 0.0)
                    formatted_total = "{:,.2f}".format(total_grp).replace(",", "X").replace(".", ",").replace("X", ".")

                    # Header: "FLÜSSIGE MITTEL >>> 12'500.00 CHF"
                    header_title = f"{group_label}     {formatted_total} {main_curr.symbol}"

                    new_aktiva_lines.append({
                        'display_type': 'line_section',
                        'db_name': header_title,  # Speichern in DB_NAME
                        'sequence': seq_aktiva,
                    })
                    seq_aktiva += 1
                    last_type_aktiva = atype

                new_aktiva_lines.append({
                    'account_id': acc.id,
                    'code': acc.code,
                    'db_name': acc.name,  # Speichern in DB_NAME
                    'sequence': seq_aktiva,
                    'original_amount': original_val_raw,
                    'original_currency_id': line_curr_id,
                    'converted_amount': converted_val_raw,
                    'currency_id': main_curr.id,
                    'display_type': False,
                    'is_highlight': make_highlight,
                })
                seq_aktiva += 1

                sum_aktiva += val_final
                if atype in type_liquidity: asset_val_liq_1 += val_final; asset_val_liq_2 += val_final; asset_val_liq_3 += val_final
                elif atype in type_receivable: asset_val_liq_2 += val_final; asset_val_liq_3 += val_final
                elif atype in type_current_assets: asset_val_liq_3 += val_final

            # === PASSIVA ===
            elif atype in type_short_term_liabilities + type_long_term_equity:
                if atype != last_type_passiva:
                    total_grp = group_totals.get(atype, 0.0)
                    formatted_total = "{:,.2f}".format(total_grp).replace(",", "X").replace(".", ",").replace("X", ".")
                    header_title = f"{group_label}  >>>  {formatted_total} {main_curr.symbol}"

                    new_passiva_lines.append({
                        'display_type': 'line_section',
                        'db_name': header_title,
                        'sequence': seq_passiva,
                    })
                    seq_passiva += 1
                    last_type_passiva = atype

                val_orig = original_val_raw * -1
                val_conv = converted_val_raw * -1

                new_passiva_lines.append({
                    'account_id': acc.id,
                    'code': acc.code,
                    'db_name': acc.name,
                    'sequence': seq_passiva,
                    'original_amount': val_orig,
                    'original_currency_id': line_curr_id,
                    'converted_amount': val_conv,
                    'currency_id': main_curr.id,
                    'display_type': False,
                    'is_highlight': make_highlight,
                })
                seq_passiva += 1

                sum_passiva += val_final
                if atype in type_short_term_liabilities: sum_kurzfr_fk += val_final

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
    _order = 'sequence asc'

    tool_aktiva_id = fields.Many2one('finance.tool', string="Parent Aktiva")
    tool_passiva_id = fields.Many2one('finance.tool', string="Parent Passiva")

    display_type = fields.Selection([('line_section', "Section"), ('line_note', "Note")], default=False)

    account_id = fields.Many2one('account.account', string="Konto-Objekt")
    sequence = fields.Integer("Seq", default=10)
    code = fields.Char("Nr.")

    # NEU: Das echte Speicherfeld
    db_name = fields.Char("Konto DB")

    original_currency_id = fields.Many2one('res.currency', string="Währung Orig.")
    original_amount = fields.Monetary(string="Betrag (Original)", currency_field='original_currency_id')
    currency_id = fields.Many2one('res.currency', string="Leitwährung")
    converted_amount = fields.Monetary(string="In Leitwährung", currency_field='currency_id')

    is_highlight = fields.Boolean(default=False)

    # --- ANZEIGE FELDER (store=False = Keine Sortierung) ---

    # 1. Das wichtigste Feld: NAME (Wird vom Section Widget gesucht)
    # store=False -> Keine Sortierpfeile
    name = fields.Char("Konto / Gruppe", compute='_compute_view_vals', store=False)

    view_code = fields.Char("Nr.", compute='_compute_view_vals', store=False)
    view_account_type = fields.Char("Typ", compute='_compute_view_vals', store=False)
    view_converted_amount = fields.Monetary("In Leitwährung", compute='_compute_view_vals', store=False, currency_field='currency_id')
    view_original_amount = fields.Monetary("Betrag (Original)", compute='_compute_view_vals', store=False, currency_field='original_currency_id')
    view_currency_symbol = fields.Char("Währ.", compute='_compute_view_vals', store=False)

    @api.depends('code', 'db_name', 'converted_amount', 'account_id', 'original_amount', 'display_type')
    def _compute_view_vals(self):
        for rec in self:
            # WICHTIG: Das Feld 'name' wird für das Widget gefüllt
            rec.name = rec.db_name

            if rec.display_type == 'line_section':
                # Bei Sections bleiben die anderen leer
                rec.view_code = ""
                rec.view_account_type = ""
                rec.view_converted_amount = 0
                rec.view_original_amount = 0
                rec.view_currency_symbol = ""
            else:
                rec.view_code = rec.code
                rec.view_converted_amount = rec.converted_amount
                rec.view_original_amount = rec.original_amount

                if rec.original_currency_id:
                    rec.view_currency_symbol = rec.original_currency_id.symbol
                else:
                    rec.view_currency_symbol = ""

                if rec.account_id and rec.account_id.account_type:
                    rec.view_account_type = rec.account_id.account_type
                else:
                    rec.view_account_type = ""

    def action_view_journal_items(self):
        if not self.account_id: return
        self.ensure_one()
        return {
            'name': f"Buchungen: {self.db_name}",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.account_id.id), ('parent_state', '=', 'posted')],
            'context': {'create': False, 'search_default_posted': 1},
        }