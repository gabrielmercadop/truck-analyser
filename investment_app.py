import math
import io
from datetime import datetime
import streamlit as st
import pandas as pd
from fpdf import FPDF
import plotly.graph_objects as go
import db

# -----------------------
# Helper functions
# -----------------------
def loan_payment(principal: float, annual_rate: float, years: float, payments_per_year: int = 12) -> float:
    """
    Fixed payment loan formula.
    principal : monto financiado
    annual_rate : tasa anual (e.g. 0.12 para 12%)
    years : plazo en años
    payments_per_year : normalmente 12
    """
    r = annual_rate / payments_per_year
    n = int(years * payments_per_year)
    if r == 0:
        return principal / n
    return r * principal / (1 - (1 + r) ** -n)

def amortization_schedule(principal: float, annual_rate: float, years: float, payments_per_year: int = 12):
    """
    Build a full amortization schedule for the loan.
    Returns a list of dicts with:
    Mes, Saldo inicial, Interés, Amortización, Cuota, Saldo final
    """
    schedule = []
    if principal <= 0 or years <= 0 or annual_rate < 0:
        return schedule

    r = annual_rate / payments_per_year
    n = int(years * payments_per_year)
    payment = loan_payment(principal, annual_rate, years, payments_per_year)

    balance = principal
    for i in range(1, n + 1):
        saldo_inicial = balance
        interes = saldo_inicial * r
        amortizacion = payment - interes
        saldo_final = saldo_inicial - amortizacion
        if saldo_final < 0:
            saldo_final = 0.0
        schedule.append(
            {
                "Mes": i,
                "Saldo inicial": round(saldo_inicial, 2),
                "Interés": round(interes, 2),
                "Amortización": round(amortizacion, 2),
                "Cuota": round(payment, 2),
                "Saldo final": round(saldo_final, 2),
            }
        )
        balance = saldo_final

    return schedule


def analyze_investment(results, financed_amount, years, investment_total):
    """
    Analyze the investment and return a comprehensive assessment.
    Returns a dict with scores, ratings, and recommendations.
    """
    analysis = {
        "metrics": [],
        "overall_score": 0,
        "recommendation": "",
        "warnings": [],
        "strengths": [],
    }
    
    total_score = 0
    max_score = 0
    
    # 1. Profit After Debt Analysis (Weight: 25 points)
    max_score += 25
    profit_after_debt = results["profit_after_debt"]
    if profit_after_debt > 0:
        # Score based on profit margin relative to revenue
        profit_ratio = profit_after_debt / results["monthly_revenue"] if results["monthly_revenue"] > 0 else 0
        if profit_ratio >= 0.30:
            score = 25
            status = "excellent"
            msg = f"Excelente margen de ganancia ({profit_ratio*100:.1f}%)"
            analysis["strengths"].append("Alto margen de ganancia neta")
        elif profit_ratio >= 0.20:
            score = 20
            status = "good"
            msg = f"Buen margen de ganancia ({profit_ratio*100:.1f}%)"
            analysis["strengths"].append("Margen de ganancia saludable")
        elif profit_ratio >= 0.10:
            score = 15
            status = "fair"
            msg = f"Margen de ganancia aceptable ({profit_ratio*100:.1f}%)"
        else:
            score = 8
            status = "warning"
            msg = f"Margen de ganancia bajo ({profit_ratio*100:.1f}%)"
            analysis["warnings"].append("El margen de ganancia es muy ajustado")
        total_score += score
    else:
        score = 0
        status = "critical"
        msg = "La inversión genera pérdidas mensuales"
        analysis["warnings"].append("⚠️ CRÍTICO: La inversión no es rentable")
    
    analysis["metrics"].append({
        "name": "Rentabilidad Mensual",
        "value": f"{profit_after_debt:,.0f} Bs",
        "score": score,
        "max_score": 25,
        "status": status,
        "description": msg
    })
    
    # 2. Payback Period Analysis (Weight: 20 points)
    max_score += 20
    payback = results["payback_years"]
    if payback is not None and payback > 0:
        if payback <= 2:
            score = 20
            status = "excellent"
            msg = f"Recuperación muy rápida ({payback:.1f} años)"
            analysis["strengths"].append("Período de recuperación excelente")
        elif payback <= 3:
            score = 17
            status = "good"
            msg = f"Buena recuperación ({payback:.1f} años)"
            analysis["strengths"].append("Período de recuperación favorable")
        elif payback <= 5:
            score = 12
            status = "fair"
            msg = f"Recuperación aceptable ({payback:.1f} años)"
        elif payback <= 7:
            score = 7
            status = "warning"
            msg = f"Recuperación lenta ({payback:.1f} años)"
            analysis["warnings"].append("El período de recuperación es largo")
        else:
            score = 3
            status = "critical"
            msg = f"Recuperación muy lenta ({payback:.1f} años)"
            analysis["warnings"].append("Período de recuperación excesivamente largo")
        total_score += score
    else:
        score = 0
        status = "critical"
        msg = "No hay recuperación (pérdidas)"
    
    analysis["metrics"].append({
        "name": "Período de Recuperación",
        "value": f"{payback:.1f} años" if payback else "N/A",
        "score": score,
        "max_score": 20,
        "status": status,
        "description": msg
    })
    
    # 3. Debt Service Coverage Ratio (DSCR) (Weight: 20 points)
    max_score += 20
    monthly_payment = results["monthly_payment"]
    profit_before_debt = results["profit_before_debt"]
    
    if monthly_payment > 0:
        dscr = profit_before_debt / monthly_payment
        if dscr >= 2.0:
            score = 20
            status = "excellent"
            msg = f"Excelente cobertura de deuda (DSCR: {dscr:.2f}x)"
            analysis["strengths"].append("Muy buena capacidad para cubrir la deuda")
        elif dscr >= 1.5:
            score = 16
            status = "good"
            msg = f"Buena cobertura de deuda (DSCR: {dscr:.2f}x)"
            analysis["strengths"].append("Capacidad sólida para cubrir pagos")
        elif dscr >= 1.25:
            score = 12
            status = "fair"
            msg = f"Cobertura aceptable (DSCR: {dscr:.2f}x)"
        elif dscr >= 1.0:
            score = 6
            status = "warning"
            msg = f"Cobertura ajustada (DSCR: {dscr:.2f}x)"
            analysis["warnings"].append("Margen muy limitado para imprevistos")
        else:
            score = 0
            status = "critical"
            msg = f"Cobertura insuficiente (DSCR: {dscr:.2f}x)"
            analysis["warnings"].append("⚠️ No puede cubrir los pagos del crédito")
        total_score += score
    else:
        score = 20  # No debt is good
        status = "excellent"
        msg = "Sin deuda - No hay riesgo de financiamiento"
        total_score += score
    
    analysis["metrics"].append({
        "name": "Cobertura de Deuda (DSCR)",
        "value": f"{dscr:.2f}x" if monthly_payment > 0 else "N/A",
        "score": score,
        "max_score": 20,
        "status": status,
        "description": msg
    })
    
    # 4. Return on Investment (ROI) Annual (Weight: 20 points)
    max_score += 20
    annual_profit = profit_after_debt * 12
    if investment_total > 0:
        roi = (annual_profit / investment_total) * 100
        if roi >= 20:
            score = 20
            status = "excellent"
            msg = f"ROI excelente ({roi:.1f}% anual)"
            analysis["strengths"].append("Retorno sobre inversión muy atractivo")
        elif roi >= 12:
            score = 16
            status = "good"
            msg = f"Buen ROI ({roi:.1f}% anual)"
            analysis["strengths"].append("Retorno competitivo")
        elif roi >= 6:
            score = 10
            status = "fair"
            msg = f"ROI aceptable ({roi:.1f}% anual)"
        elif roi > 0:
            score = 5
            status = "warning"
            msg = f"ROI bajo ({roi:.1f}% anual)"
            analysis["warnings"].append("El retorno no justifica el riesgo")
        else:
            score = 0
            status = "critical"
            msg = f"ROI negativo ({roi:.1f}% anual)"
        total_score += score
    else:
        score = 0
        status = "critical"
        msg = "No se puede calcular ROI"
    
    analysis["metrics"].append({
        "name": "Retorno Anual (ROI)",
        "value": f"{roi:.1f}%" if investment_total > 0 else "N/A",
        "score": score,
        "max_score": 20,
        "status": status,
        "description": msg
    })
    
    # 5. Funding Gap Analysis (Weight: 15 points)
    max_score += 15
    funding_gap = results["funding_gap"]
    if funding_gap <= 0:
        score = 15
        status = "excellent"
        msg = "Financiamiento completo asegurado"
        analysis["strengths"].append("Capital suficiente para la inversión")
        total_score += score
    elif funding_gap <= investment_total * 0.05:
        score = 10
        status = "fair"
        msg = f"Pequeña brecha de financiamiento ({funding_gap:,.0f} Bs)"
        total_score += score
    else:
        score = 0
        status = "critical"
        msg = f"Falta financiamiento ({funding_gap:,.0f} Bs)"
        analysis["warnings"].append("No hay suficiente capital para la inversión")
    
    analysis["metrics"].append({
        "name": "Financiamiento",
        "value": "Completo" if funding_gap <= 0 else f"Faltan {funding_gap:,.0f} Bs",
        "score": score,
        "max_score": 15,
        "status": status,
        "description": msg
    })
    
    # Calculate overall score
    overall_percentage = (total_score / max_score) * 100 if max_score > 0 else 0
    analysis["overall_score"] = overall_percentage
    analysis["total_points"] = total_score
    analysis["max_points"] = max_score
    
    # Overall recommendation
    if overall_percentage >= 85:
        analysis["recommendation"] = "ALTAMENTE RECOMENDADA"
        analysis["recommendation_color"] = "green"
        analysis["recommendation_icon"] = "✅"
        analysis["summary"] = "Esta inversión muestra excelentes indicadores financieros. Todos los métricas clave están en niveles óptimos."
    elif overall_percentage >= 70:
        analysis["recommendation"] = "RECOMENDADA"
        analysis["recommendation_color"] = "green"
        analysis["recommendation_icon"] = "👍"
        analysis["summary"] = "La inversión es sólida con buenos fundamentales. Considere optimizar las áreas con calificación más baja."
    elif overall_percentage >= 55:
        analysis["recommendation"] = "ACEPTABLE CON RESERVAS"
        analysis["recommendation_color"] = "orange"
        analysis["recommendation_icon"] = "⚠️"
        analysis["summary"] = "La inversión es viable pero presenta riesgos. Revise cuidadosamente las advertencias antes de proceder."
    elif overall_percentage >= 40:
        analysis["recommendation"] = "RIESGOSA"
        analysis["recommendation_color"] = "orange"
        analysis["recommendation_icon"] = "⚠️"
        analysis["summary"] = "La inversión presenta múltiples riesgos. Se recomienda reevaluar los parámetros o buscar mejores condiciones."
    else:
        analysis["recommendation"] = "NO RECOMENDADA"
        analysis["recommendation_color"] = "red"
        analysis["recommendation_icon"] = "❌"
        analysis["summary"] = "Esta inversión no es viable en las condiciones actuales. Necesita cambios significativos para ser rentable."
    
    return analysis


class InvestmentPDF(FPDF):
    """Custom PDF class for investment analysis reports."""
    
    def __init__(self, truck_name="Truck"):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.truck_name = truck_name
        self.report_currency = "Bs"
    
    def add_header(self):
        """Add report header - call manually after add_page"""
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(30, 136, 229)
        self.cell(0, 12, f'Análisis de inversión: {self.truck_name}', 0, 1, 'C')
        self.set_font('Helvetica', '', 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 6, f'Generado: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'C')
        self.ln(8)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
    
    def section_title(self, title):
        self.ln(3)
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(30, 136, 229)
        self.cell(0, 8, title, 0, 1, 'L')
        self.set_draw_color(30, 136, 229)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)
    
    def add_metric(self, label, value):
        self.set_x(15)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(80, 80, 80)
        self.cell(85, 7, label, 0, 0, 'L')
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(40, 40, 40)
        self.cell(0, 7, str(value), 0, 1, 'L')
    
    def add_score_box(self, score, recommendation, summary):
        # Determine color based on score
        if score >= 70:
            r, g, b = 40, 167, 69
        elif score >= 50:
            r, g, b = 255, 193, 7
        else:
            r, g, b = 220, 53, 69
        
        start_y = self.get_y()
        
        # Draw score circle
        self.set_fill_color(r, g, b)
        circle_x = 30
        circle_y = start_y + 12
        self.ellipse(circle_x - 12, circle_y - 12, 24, 24, 'F')
        
        # Score number in circle
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(255, 255, 255)
        self.set_xy(circle_x - 12, circle_y - 6)
        self.cell(24, 12, f'{score:.0f}', 0, 0, 'C')
        
        # Recommendation text
        self.set_xy(55, start_y + 2)
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(r, g, b)
        self.cell(0, 8, recommendation, 0, 1, 'L')
        
        # Summary text
        self.set_x(55)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(80, 80, 80)
        self.multi_cell(140, 5, summary)
        
        self.set_y(max(self.get_y(), start_y + 30))
        self.ln(5)
    
    def add_table(self, headers, data, col_widths=None):
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)
        
        self.set_x(10)
        # Header
        self.set_font('Helvetica', 'B', 8)
        self.set_fill_color(230, 230, 230)
        self.set_text_color(40, 40, 40)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, 1, 0, 'C', True)
        self.ln()
        
        # Data
        self.set_font('Helvetica', '', 8)
        for row in data:
            self.set_x(10)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 6, str(cell), 1, 0, 'C')
            self.ln()
    
    def add_list(self, items, bullet='-', color=(80, 80, 80)):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*color)
        for item in items:
            self.set_x(15)
            self.cell(0, 6, f"{bullet}  {item}", 0, 1, 'L')

    def add_paragraph(self, text, font_size=9, color=(80, 80, 80), left_margin=15, line_height=5):
        self.set_font('Helvetica', '', font_size)
        self.set_text_color(*color)
        self.set_x(left_margin)
        self.multi_cell(0, line_height, text)

    def add_note_box(self, title, body, fill_color=(245, 248, 255), border_color=(30, 136, 229)):
        start_x = 12
        start_y = self.get_y()
        box_w = 186
        # Title
        self.set_xy(start_x, start_y + 2)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(border_color[0], border_color[1], border_color[2])
        self.cell(0, 5, title, 0, 1, 'L')
        # Body
        self.set_x(start_x)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(60, 60, 60)
        before_y = self.get_y()
        self.multi_cell(box_w - 4, 4, body)
        after_y = self.get_y()
        box_h = (after_y - start_y) + 4
        # Background + border (draw last so height is known)
        self.set_draw_color(border_color[0], border_color[1], border_color[2])
        self.set_fill_color(fill_color[0], fill_color[1], fill_color[2])
        self.rect(start_x, start_y, box_w, box_h, 'DF')
        # Repaint text on top (FPDF draws rect over content)
        self.set_xy(start_x, start_y + 2)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(border_color[0], border_color[1], border_color[2])
        self.cell(0, 5, title, 0, 1, 'L')
        self.set_x(start_x)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(60, 60, 60)
        self.multi_cell(box_w - 4, 4, body)
        self.ln(3)


def generate_pdf_report(results, analysis, inputs, sensitivity_data=None):
    """Generate a PDF report of the investment analysis."""
    pdf = InvestmentPDF(inputs.get('truck_name', 'Truck'))
    pdf.add_page()
    pdf.add_header()

    # Executive summary
    scenario_label = str(inputs.get("analysis_context", "Escenario actual"))
    monthly_payment = float(results.get("monthly_payment", 0.0) or 0.0)
    profit_before_debt = float(results.get("profit_before_debt", 0.0) or 0.0)
    profit_after_debt = float(results.get("profit_after_debt", 0.0) or 0.0)
    monthly_revenue = float(results.get("monthly_revenue", 0.0) or 0.0)
    operating_costs = float(results.get("operating_costs", 0.0) or 0.0)
    total_taxes = float(results.get("total_taxes", 0.0) or 0.0)
    net_margin_pct = (profit_after_debt / monthly_revenue * 100.0) if monthly_revenue > 0 else 0.0
    dscr = (profit_before_debt / monthly_payment) if monthly_payment > 0 else None

    breakeven_trips = None
    best_trips = None
    best_profit = None
    if sensitivity_data:
        for row in sensitivity_data:
            if row.get("Utilidad Neta (Bs)", -1) >= 0:
                breakeven_trips = row.get("Viajes/Mes")
                break
        for row in sensitivity_data:
            p = row.get("Utilidad Neta (Bs)")
            if p is None:
                continue
            if best_profit is None or p > best_profit:
                best_profit = p
                best_trips = row.get("Viajes/Mes")

    pdf.section_title('Resumen ejecutivo')
    pdf.add_metric('Escenario evaluado', scenario_label)
    pdf.add_metric('Score de viabilidad', f"{analysis.get('overall_score', 0):.0f}/100")
    pdf.add_metric('Recomendación', analysis.get('recommendation', '').replace('✅', '').replace('👍', '').replace('⚠️', '').replace('❌', '').strip())
    pdf.ln(2)

    headers = ['Indicador', 'Valor']
    kpi_rows = [
        ['Ingresos mensuales', f"{monthly_revenue:,.0f} Bs"],
        ['Costos operativos', f"{operating_costs:,.0f} Bs"],
        ['Impuestos (IVA + IT)', f"{total_taxes:,.0f} Bs"],
        ['Cuota del crédito', f"{monthly_payment:,.0f} Bs"],
        ['Utilidad neta (después de deuda)', f"{profit_after_debt:,.0f} Bs"],
        ['Margen neto', f"{net_margin_pct:.1f}%"],
        ['Utilidad anual estimada', f"{profit_after_debt * 12:,.0f} Bs"],
    ]
    if dscr is not None:
        kpi_rows.append(['Cobertura de deuda (DSCR)', f"{dscr:.2f}x"])
    if breakeven_trips is not None:
        kpi_rows.append(['Punto de equilibrio (viajes/mes)', str(breakeven_trips)])
    if best_trips is not None and best_profit is not None:
        kpi_rows.append(['Mejor escenario (en rango)', f"{best_trips} viajes -> {best_profit:,.0f} Bs/mes"])

    pdf.add_table(headers, kpi_rows, [80, 110])
    pdf.ln(3)
    pdf.add_note_box(
        "Cómo interpretar",
        "La utilidad neta se calcula con ingresos menos costos operativos, impuestos (IVA e IT) y la cuota del crédito. "
        "El punto de equilibrio usa el análisis de sensibilidad (si está disponible) y representa el mínimo de viajes/mes para no tener pérdidas."
    )

    # Better client impact (comparison vs current scenario)
    if inputs.get("better_client_enabled") and inputs.get("better_client_results"):
        bc = inputs["better_client_results"]
        base_results = inputs.get("baseline_results") or results

        # Build a full "better client" results dict from baseline + overrides
        better_full = dict(base_results)
        better_full.update(
            {
                "monthly_revenue": float(bc.get("monthly_revenue", better_full.get("monthly_revenue", 0.0)) or 0.0),
                "operating_costs": float(bc.get("operating_costs", better_full.get("operating_costs", 0.0)) or 0.0),
                "iva_tax": float(bc.get("iva_tax", better_full.get("iva_tax", 0.0)) or 0.0),
                "it_tax": float(bc.get("it_tax", better_full.get("it_tax", 0.0)) or 0.0),
                "total_taxes": float(bc.get("total_taxes", better_full.get("total_taxes", 0.0)) or 0.0),
                "profit_before_debt": float(bc.get("profit_before_debt", better_full.get("profit_before_debt", 0.0)) or 0.0),
                "profit_after_debt": float(bc.get("profit_after_debt", better_full.get("profit_after_debt", 0.0)) or 0.0),
                "payback_years": bc.get("payback_years", better_full.get("payback_years")),
            }
        )
        better_full["total_costs"] = float(better_full.get("operating_costs", 0.0) or 0.0) + float(
            better_full.get("total_taxes", 0.0) or 0.0
        )

        # Compute deltas
        base_rev = float(base_results.get("monthly_revenue", 0.0) or 0.0)
        base_taxes = float(base_results.get("total_taxes", 0.0) or 0.0)
        base_profit = float(base_results.get("profit_after_debt", 0.0) or 0.0)
        base_payback = base_results.get("payback_years")

        better_rev = float(better_full.get("monthly_revenue", 0.0) or 0.0)
        better_taxes = float(better_full.get("total_taxes", 0.0) or 0.0)
        better_profit = float(better_full.get("profit_after_debt", 0.0) or 0.0)
        better_payback = better_full.get("payback_years")

        delta_rev = better_rev - base_rev
        delta_taxes = better_taxes - base_taxes
        delta_profit = better_profit - base_profit

        # Rate + trip explanation
        base_rate = float(inputs.get("base_price_per_m3", inputs.get("price_per_m3", 0.0)) or 0.0)
        better_rate = float(inputs.get("better_rate", 0.0) or 0.0)
        better_trips = float(inputs.get("better_rate_trips", bc.get("trips_better_rate", 0.0)) or 0.0)
        m3_trip = float(inputs.get("m3_per_trip", 0.0) or 0.0)
        delta_gross_per_trip = m3_trip * (better_rate - base_rate)
        delta_net_per_trip = (delta_profit / better_trips) if better_trips > 0 else 0.0
        rate_pct = ((better_rate - base_rate) / base_rate * 100.0) if base_rate > 0 else 0.0

        # Scores for comparison
        financed_amount = float(inputs.get("financed_amount", 0.0) or 0.0)
        years = float(inputs.get("years", 0.0) or 0.0)
        investment_total = float(base_results.get("investment_total", 0.0) or 0.0)
        base_analysis = analyze_investment(base_results, financed_amount, years, investment_total)
        better_analysis = analyze_investment(better_full, financed_amount, years, investment_total)
        delta_score = float(better_analysis.get("overall_score", 0.0) or 0.0) - float(base_analysis.get("overall_score", 0.0) or 0.0)

        pdf.section_title('Impacto del mejor cliente')
        pdf.add_paragraph(
            f"Este escenario reasigna {better_trips:.0f} viajes/mes a una tarifa de {better_rate:,.0f} Bs/m³ "
            f"(vs {base_rate:,.0f} Bs/m³, {rate_pct:.0f}% más), manteniendo constante el total de viajes. "
            "Como el número total de viajes no cambia, los costos por viaje (diesel/peajes) se mantienen; lo que cambia son los ingresos y, por consecuencia, los impuestos y la utilidad.",
            font_size=9,
        )
        if better_trips > 0 and (better_rate - base_rate) != 0:
            pdf.add_note_box(
                "Efecto por viaje reasignado",
                f"Incremento bruto estimado: {delta_gross_per_trip:,.0f} Bs por viaje (antes de impuestos). "
                f"Incremento neto observado (después de impuestos y deuda): {delta_net_per_trip:,.0f} Bs por viaje.",
                fill_color=(240, 255, 245),
                border_color=(40, 167, 69),
            )

        headers = ['Métrica', 'Escenario actual', 'Mejor cliente', 'Cambio']
        rows = [
            ['Ingresos mensuales', f"{base_rev:,.0f} Bs", f"{better_rev:,.0f} Bs", f"{delta_rev:,.0f} Bs"],
            ['Impuestos (IVA+IT)', f"{base_taxes:,.0f} Bs", f"{better_taxes:,.0f} Bs", f"{delta_taxes:,.0f} Bs"],
            ['Utilidad neta (después de deuda)', f"{base_profit:,.0f} Bs", f"{better_profit:,.0f} Bs", f"{delta_profit:,.0f} Bs"],
            ['Utilidad anual estimada', f"{base_profit * 12:,.0f} Bs", f"{better_profit * 12:,.0f} Bs", f"{delta_profit * 12:,.0f} Bs"],
            ['Score', f"{base_analysis.get('overall_score', 0):.0f}", f"{better_analysis.get('overall_score', 0):.0f}", f"{delta_score:+.0f}"],
        ]
        if base_payback and better_payback:
            rows.append(['Payback', f"{float(base_payback):.1f} años", f"{float(better_payback):.1f} años", f"{(float(better_payback) - float(base_payback)):+.1f} años"])

        pdf.add_table(headers, rows, [60, 45, 45, 40])
        pdf.ln(2)
        pdf.add_paragraph(
            "Nota: este comparativo usa el mismo crédito fiscal (si aplica) y el mismo plan de financiamiento. "
            "Si cambian el mix de viajes, condiciones de cobro o costos por ruta, los resultados pueden variar.",
            font_size=8,
            color=(110, 110, 110),
        )
    
    # Investment Summary Section
    pdf.section_title('Resumen de la inversión')
    truck_price = inputs.get("truck_price")
    trailer_price = inputs.get("trailer_price")
    if truck_price is not None or trailer_price is not None:
        if truck_price is not None:
            pdf.add_metric('Precio camión', f"{float(truck_price):,.0f} Bs")
        if trailer_price is not None:
            pdf.add_metric('Precio tolva / acople', f"{float(trailer_price):,.0f} Bs")
    pdf.add_metric('Inversión total (camión + acople)', f"{results['investment_total']:,.0f} Bs")
    if inputs.get("capital") is not None:
        pdf.add_metric('Capital disponible', f"{float(inputs['capital']):,.0f} Bs")
    pdf.add_metric('Capital propio invertido', f"{results['equity_used']:,.0f} Bs")
    pdf.add_metric('Reserva de caja', f"{results['reserve']:,.0f} Bs")
    pdf.add_metric('Aporte total (capital + crédito)', f"{results['total_funded']:,.0f} Bs")
    
    if results['funding_gap'] > 0:
        pdf.set_text_color(220, 53, 69)
        pdf.add_metric('Brecha de financiamiento', f"{results['funding_gap']:,.0f} Bs")
    elif results['funding_gap'] < 0:
        pdf.set_text_color(40, 167, 69)
        pdf.add_metric('Exceso de financiamiento', f"{-results['funding_gap']:,.0f} Bs")
    pdf.ln(5)
    
    # Credit Details Section
    pdf.section_title('Detalles del crédito')
    pdf.add_metric('Monto financiado', f"{inputs['financed_amount']:,.0f} Bs")
    pdf.add_metric('Tasa de interés anual', f"{inputs['annual_rate']*100:.1f}%")
    pdf.add_metric('Plazo', f"{inputs['years']} años")
    pdf.add_metric('Cuota mensual', f"{results['monthly_payment']:,.0f} Bs")
    if monthly_payment > 0:
        deuda_anual = monthly_payment * 12
        pdf.add_metric('Servicio de deuda anual', f"{deuda_anual:,.0f} Bs")
    pdf.ln(5)
    
    # Monthly Cash Flow Section
    pdf.section_title('Flujo de caja mensual')
    pdf.add_metric('Ingresos mensuales', f"{results['monthly_revenue']:,.0f} Bs")
    pdf.add_metric('Costos operativos', f"{results['operating_costs']:,.0f} Bs")
    iva_label = f"IVA ({inputs.get('iva_rate', 0.0) * 100:.1f}%)"
    it_label = f"IT ({inputs.get('it_rate', 0.0) * 100:.1f}%)"
    pdf.add_metric(iva_label, f"{results['iva_tax']:,.0f} Bs")
    pdf.add_metric(it_label, f"{results['it_tax']:,.0f} Bs")
    pdf.add_metric('Total impuestos', f"{results['total_taxes']:,.0f} Bs")
    pdf.add_metric('Utilidad antes de deuda', f"{results['profit_before_debt']:,.0f} Bs")
    pdf.add_metric('Utilidad después de deuda', f"{results['profit_after_debt']:,.0f} Bs")
    if results['payback_years']:
        pdf.add_metric('Período de recuperación', f"{results['payback_years']:.1f} años")
    pdf.add_metric('Utilidad anual estimada', f"{results['profit_after_debt'] * 12:,.0f} Bs")
    pdf.ln(5)
    
    # Investment Analysis Section
    pdf.section_title('Análisis de viabilidad de la inversión')
    # Clean recommendation of Unicode characters
    clean_recommendation = analysis['recommendation'].replace('✅', '').replace('👍', '').replace('⚠️', '').replace('❌', '').strip()
    pdf.add_score_box(
        analysis['overall_score'],
        clean_recommendation,
        analysis['summary']
    )
    
    # Detailed Metrics Table
    pdf.section_title('Métricas detalladas')
    headers = ['Métrica', 'Valor', 'Puntaje', 'Estado']
    data = []
    for metric in analysis['metrics']:
        data.append([
            metric['name'],
            metric['value'],
            f"{metric['score']}/{metric['max_score']}",
            metric['status'].upper()
        ])
    pdf.add_table(headers, data, [60, 50, 30, 50])
    pdf.ln(5)
    
    # Strengths
    if analysis['strengths']:
        pdf.section_title('Fortalezas')
        pdf.add_list(analysis['strengths'], '+', (40, 167, 69))
        pdf.ln(3)
    
    # Warnings
    if analysis['warnings']:
        pdf.section_title('Advertencias')
        # Clean warning text of Unicode characters
        clean_warnings = [w.replace('⚠️', '').replace('⚠', '').strip() for w in analysis['warnings']]
        pdf.add_list(clean_warnings, '!', (220, 53, 69))
        pdf.ln(3)
    
    # Operating Parameters
    pdf.add_page()
    pdf.section_title('Parámetros operativos')
    pdf.add_metric('Metros cúbicos por viaje', f"{inputs['m3_per_trip']:.0f} m³")
    pdf.add_metric('Tarifa por metro cúbico', f"{inputs['price_per_m3']:.0f} Bs/m³")
    pdf.add_metric('Viajes por mes', f"{inputs['trips_per_month']:.0f}")
    pdf.add_metric('Ingresos por viaje', f"{inputs['m3_per_trip'] * inputs['price_per_m3']:,.0f} Bs")
    pdf.ln(3)
    
    pdf.section_title('Detalle de costos mensuales')
    pdf.add_metric('Diesel por viaje', f"{inputs['diesel_cost_per_trip']:,.0f} Bs")
    pdf.add_metric('Diesel mensual', f"{inputs['diesel_cost']:,.0f} Bs ({inputs['trips_per_month']:.0f} viajes)")
    pdf.add_metric('Peaje por viaje', f"{inputs['toll_cost_per_trip']:,.0f} Bs")
    pdf.add_metric('Peajes mensual', f"{inputs['toll_cost']:,.0f} Bs ({inputs['trips_per_month']:.0f} viajes)")
    pdf.add_metric('Sueldo del chofer', f"{inputs['driver_salary']:,.0f} Bs")
    pdf.add_metric('Mantenimiento', f"{inputs['maintenance_cost']:,.0f} Bs")
    pdf.add_metric('Otros costos', f"{inputs['other_costs']:,.0f} Bs")
    pdf.add_metric('Total costos operativos', f"{results['operating_costs']:,.0f} Bs")
    pdf.ln(3)
    
    pdf.section_title('Impuestos')
    pdf.add_metric('IVA', f"{inputs['iva_rate']*100:.1f}% = {results['iva_tax']:,.0f} Bs")
    pdf.add_metric('IT', f"{inputs['it_rate']*100:.1f}% = {results['it_tax']:,.0f} Bs")
    pdf.add_metric('Total impuestos', f"{results['total_taxes']:,.0f} Bs")
    pdf.ln(3)
    
    # Crédito Fiscal Section
    if inputs.get('iva_rate', 0.0) > 0:
        pdf.section_title('Credito Fiscal por Compra de Activos')
        compra_iva_label = "camion + tolva/acople" if inputs.get('tolva_con_iva', True) else "solo camion"
        credito_fiscal_base = float(inputs.get('credito_fiscal_base', 0.0))
        pdf.add_metric('Base con IVA', f"{credito_fiscal_base:,.0f} Bs ({compra_iva_label})")
        pdf.add_metric('Credito fiscal total', f"{inputs['credito_fiscal_total']:,.0f} Bs")
        pdf.add_metric('IVA mensual (sin credito)', f"{inputs['results_without_credit']['iva_before_credit']:,.0f} Bs")
        pdf.add_metric('Meses de cobertura', f"{inputs['months_credit_coverage']:.1f} meses")
        pdf.add_metric('Ahorro mensual (con credito)', f"{inputs['monthly_iva_savings']:,.0f} Bs")
        pdf.ln(2)
        
        # Comparison table
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 6, 'Comparacion: Con vs Sin Credito Fiscal', 0, 1, 'L')
        pdf.ln(2)
        
        headers = ['Escenario', 'IVA Efectivo', 'Total Impuestos', 'Utilidad Mensual']
        results_no_credit = inputs['results_without_credit']
        data = [
            ['Con Credito Fiscal', f"{results['iva_tax']:,.0f} Bs", f"{results['total_taxes']:,.0f} Bs", f"{results['profit_after_debt']:,.0f} Bs"],
            ['Sin Credito Fiscal', f"{results_no_credit['iva_tax']:,.0f} Bs", f"{results_no_credit['total_taxes']:,.0f} Bs", f"{results_no_credit['profit_after_debt']:,.0f} Bs"],
        ]
        pdf.add_table(headers, data, [50, 45, 45, 50])
        pdf.ln(5)
    
    # Sensitivity Analysis
    if sensitivity_data:
        pdf.section_title('Análisis de sensibilidad: viajes por mes')
        headers = ['Viajes/mes', 'Utilidad neta (Bs)', 'Utilidad anual (Bs)', 'Puntaje', 'Recomendación']
        data = []
        for row in sensitivity_data[:10]:  # Limit to 10 rows
            payback = row['Payback (años)']
            # Clean recommendation of Unicode characters
            clean_rec = row['Recomendación'].replace('✅', '').replace('👍', '').replace('⚠️', '').replace('❌', '').strip()
            marker = "*" if row.get("Es actual") else ""
            data.append([
                f"{row['Viajes/Mes']}{marker}",
                f"{row['Utilidad Neta (Bs)']:,.0f}",
                f"{row['Utilidad Anual (Bs)']:,.0f}",
                f"{row['Score']:.0f}",
                clean_rec[:20]
            ])
        pdf.add_table(headers, data, [25, 40, 40, 25, 60])
        pdf.ln(2)
        pdf.add_paragraph("* = escenario actual en la tabla", font_size=8, color=(110, 110, 110))

    # Amortization schedule
    financed_amount = float(inputs.get("financed_amount", 0.0) or 0.0)
    years = float(inputs.get("years", 0.0) or 0.0)
    annual_rate = float(inputs.get("annual_rate", 0.0) or 0.0)
    if financed_amount > 0 and years > 0:
        schedule = amortization_schedule(financed_amount, annual_rate, years)
        if schedule:
            pdf.add_page()
            pdf.section_title('Amortización del crédito')

            total_paid = sum(r.get("Cuota", 0.0) for r in schedule)
            total_interest = sum(r.get("Interés", 0.0) for r in schedule)
            total_principal = sum(r.get("Amortización", 0.0) for r in schedule)

            pdf.add_metric('Cuota mensual', f"{loan_payment(financed_amount, annual_rate, years):,.0f} Bs")
            pdf.add_metric('Total pagado', f"{total_paid:,.0f} Bs")
            pdf.add_metric('Interés total', f"{total_interest:,.0f} Bs")
            pdf.add_metric('Capital amortizado', f"{total_principal:,.0f} Bs")
            pdf.ln(3)

            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(110, 110, 110)
            pdf.multi_cell(0, 4, "Detalle (primeros 12 meses). Para ver el detalle completo, usa la tabla de amortización en la app.")
            pdf.ln(2)

            headers = ['Mes', 'Saldo ini.', 'Interés', 'Amort.', 'Cuota', 'Saldo fin.']
            rows = []
            for r in schedule[:12]:
                rows.append([
                    str(r.get("Mes", "")),
                    f"{float(r.get('Saldo inicial', 0.0)):,.0f}",
                    f"{float(r.get('Interés', 0.0)):,.0f}",
                    f"{float(r.get('Amortización', 0.0)):,.0f}",
                    f"{float(r.get('Cuota', 0.0)):,.0f}",
                    f"{float(r.get('Saldo final', 0.0)):,.0f}",
                ])
            pdf.add_table(headers, rows, [12, 36, 26, 26, 26, 36])
    
    # Generate the PDF bytes
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output.getvalue()


def monthly_cashflow(
    truck_price,
    trailer_price,
    capital,
    reserve_min,
    financed_amount,
    annual_rate,
    years,
    m3_per_trip,
    price_per_m3,
    trips_per_month,
    diesel_cost,
    toll_cost,
    driver_salary,
    maintenance_cost,
    other_costs,
    iva_rate=0.13,
    it_rate=0.03,
    credito_fiscal_available=0.0,
):
    investment_total = truck_price + trailer_price
    reserve = min(reserve_min, capital)  # just to be safe
    own_equity_used = min(capital - reserve, investment_total)
    # If user puts financed_amount, we trust it, but keep an eye:
    financed_amount = max(0.0, financed_amount)

    # Loan payment
    monthly_payment = loan_payment(financed_amount, annual_rate, years)

    # Revenue
    revenue_per_trip = m3_per_trip * price_per_m3
    monthly_revenue = revenue_per_trip * trips_per_month

    # Taxes (calculated on gross revenue)
    iva_before_credit = monthly_revenue * iva_rate
    it_tax = monthly_revenue * it_rate
    
    # Apply crédito fiscal to IVA (offset available credit against IVA owed)
    credito_fiscal_used = min(credito_fiscal_available, iva_before_credit)
    iva_tax = iva_before_credit - credito_fiscal_used
    total_taxes = iva_tax + it_tax

    # Costs (including taxes)
    operating_costs = diesel_cost + toll_cost + driver_salary + maintenance_cost + other_costs
    total_costs = operating_costs + total_taxes
    profit_before_debt = monthly_revenue - total_costs
    profit_after_debt = profit_before_debt - monthly_payment

    # Simple payback on your equity
    equity_invested = own_equity_used
    total_funded = equity_invested + financed_amount
    funding_gap = investment_total - total_funded
    payback_years = None
    if profit_after_debt > 0 and equity_invested > 0:
        payback_years = equity_invested / (profit_after_debt * 12)

    return {
        "investment_total": investment_total,
        "reserve": reserve,
        "equity_used": equity_invested,
        "monthly_payment": monthly_payment,
        "monthly_revenue": monthly_revenue,
        "operating_costs": operating_costs,
        "iva_before_credit": iva_before_credit,
        "credito_fiscal_used": credito_fiscal_used,
        "iva_tax": iva_tax,
        "it_tax": it_tax,
        "total_taxes": total_taxes,
        "total_costs": total_costs,
        "profit_before_debt": profit_before_debt,
        "profit_after_debt": profit_after_debt,
        "payback_years": payback_years,
        "total_funded": total_funded,
        "funding_gap": funding_gap,
    }


# -----------------------
# Streamlit UI
# -----------------------
st.set_page_config(page_title="Truck Investment Analyzer", layout="wide")

st.title("🚛 Truck + Trailer Investment Analyzer")

st.markdown(
    """
Adjust the sliders/inputs on the left and see the monthly cashflow and payback on the right.

Defaults are based on your case:
- **SITRAK ZZ3257** ≈ 1,705,200 Bs  
- **Tolva/acople 18 m³** ≈ 468,500 Bs  
- **Capital disponible**: 1,100,000 Bs  
- **Flete**: 90 Bs/m³  
- **35 m³ por viaje, 22 viajes al mes**  
- **Crédito**: 700,000 Bs a 12% anual, 5 años
"""
)

# ------------- Sidebar inputs -------------
st.sidebar.header("🔧 Investment Inputs")
truck_name = st.sidebar.text_input("Nombre del camión", value="SITRAK ZZ3257")

# Truck & trailer prices
truck_price = st.sidebar.number_input(
    "Precio camión (Bs)", min_value=0.0, value=1_705_200.0, step=10_000.0, format="%.0f"
)
trailer_price = st.sidebar.number_input(
    "Precio tolva / acople (Bs)", min_value=0.0, value=468_500.0, step=10_000.0, format="%.0f"
)

capital = st.sidebar.number_input(
    "Capital disponible (Bs)", min_value=0.0, value=1_100_000.0, step=50_000.0, format="%.0f"
)
reserve_min = st.sidebar.number_input(
    "Reserva mínima de caja (Bs)", min_value=0.0, value=300_000.0, step=10_000.0, format="%.0f"
)

st.sidebar.markdown("---")
st.sidebar.subheader("💳 Crédito")

financed_amount = st.sidebar.number_input(
    "Monto financiado (Bs)", min_value=0.0, value=700_000.0, step=50_000.0, format="%.0f"
)
annual_rate = st.sidebar.number_input(
    "Tasa interés anual (%)", min_value=0.0, max_value=50.0, value=12.0, step=0.5, format="%.1f"
) / 100.0
years = st.sidebar.slider("Plazo del crédito (años)", min_value=1, max_value=8, value=5, step=1)

st.sidebar.markdown("---")
st.sidebar.subheader("🚚 Operación")

m3_per_trip = st.sidebar.number_input(
    "m³ por viaje (camión + acople)", min_value=0.0, value=35.0, step=1.0
)
price_per_m3 = st.sidebar.number_input(
    "Tarifa (Bs por m³)", min_value=0.0, value=90.0, step=1.0
)
trips_per_month = st.sidebar.number_input(
    "Viajes por mes", min_value=0.0, value=22.0, step=1.0
)
trips_per_month_int = int(trips_per_month)

st.sidebar.markdown("---")
st.sidebar.subheader("🤝 Mejor Cliente (Opcional)")

enable_better_client = st.sidebar.checkbox(
    "Analizar escenario con mejor tarifa",
    value=False,
    help="Activa para modelar un escenario donde consigues viajes a mejor tarifa"
)

better_rate = st.sidebar.number_input(
    "Tarifa del mejor cliente (Bs/m³)",
    min_value=0.0,
    value=120.0,
    step=5.0,
    disabled=not enable_better_client,
    help="La tarifa que podrías conseguir con un mejor cliente"
)

better_rate_trips = st.sidebar.number_input(
    "Viajes reasignados a mejor tarifa (por mes)",
    min_value=0,
    max_value=max(0, trips_per_month_int),
    value=min(5, max(0, trips_per_month_int)),
    step=1,
    disabled=not enable_better_client,
    help="Cantidad de viajes que cambias del cliente actual al mejor cliente (no suma viajes)."
)

st.sidebar.markdown("---")
st.sidebar.subheader("⛽ Costos mensuales")

diesel_cost_per_trip = st.sidebar.number_input(
    "Gasto en diesel por viaje (Bs)", min_value=0.0, value=800.0, step=50.0, format="%.0f"
)
diesel_cost = diesel_cost_per_trip * trips_per_month

toll_cost_per_trip = st.sidebar.number_input(
    "Peaje por viaje (Bs)", min_value=0.0, value=74.0, step=5.0, format="%.0f"
)
toll_cost = toll_cost_per_trip * trips_per_month
driver_salary = st.sidebar.number_input(
    "Sueldo chofer (Bs/mes)", min_value=0.0, value=4_500.0, step=500.0, format="%.0f"
)
maintenance_cost = st.sidebar.number_input(
    "Mantenimiento (Bs/mes)", min_value=0.0, value=6_000.0, step=500.0, format="%.0f"
)
other_costs = st.sidebar.number_input(
    "Otros costos (peajes, seguros, etc.) (Bs/mes)",
    min_value=0.0,
    value=1_500.0,
    step=500.0,
    format="%.0f",
)

st.sidebar.markdown("---")
st.sidebar.subheader("🧾 Impuestos")

aplica_iva = st.sidebar.checkbox(
    "Aplicar IVA",
    value=True,
    help="Desactiva si tu operación no paga/cobra IVA (no hay IVA ni crédito fiscal).",
)

iva_rate_input = st.sidebar.number_input(
    "IVA (%)",
    min_value=0.0,
    max_value=100.0,
    value=13.0,
    step=0.5,
    format="%.1f",
    disabled=not aplica_iva,
) / 100.0

iva_rate = iva_rate_input if aplica_iva else 0.0

tolva_con_iva = st.sidebar.checkbox(
    "Tolva / acople con IVA (para crédito fiscal)",
    value=True,
    disabled=not aplica_iva,
    help="Si la tolva/acople no tiene factura con IVA, desactívalo para que el crédito fiscal venga solo del camión.",
)
it_rate = st.sidebar.number_input(
    "IT (%)", min_value=0.0, max_value=100.0, value=3.0, step=0.5, format="%.1f"
) / 100.0

# ------------- Saved Analyses Section -------------
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Análisis Guardados")

# Initialize session state for analysis name
if "analysis_save_name" not in st.session_state:
    st.session_state.analysis_save_name = ""

# Load saved analyses
saved_analyses = db.get_investment_analyses()

# Display saved analyses list
if saved_analyses:
    st.sidebar.caption(f"{len(saved_analyses)} análisis guardados")
    
    for saved in saved_analyses:
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            created = saved["created_at"][:10] if saved["created_at"] else ""
            st.sidebar.text(f"📊 {saved['name']}\n   {created}")
        with col2:
            if st.sidebar.button("🗑️", key=f"del_{saved['id']}", help="Eliminar"):
                db.delete_investment_analysis(saved['id'])
                st.rerun()
    
    # Load analysis selector
    analysis_options = [(s["id"], s["name"]) for s in saved_analyses]
    selected_analysis = st.sidebar.selectbox(
        "Cargar análisis",
        options=analysis_options,
        format_func=lambda x: x[1],
        key="load_analysis_select"
    )
    
    if st.sidebar.button("📂 Cargar Análisis", use_container_width=True):
        loaded = db.get_investment_analysis(selected_analysis[0])
        if loaded and loaded["inputs"]:
            # Store loaded inputs in session state for next rerun
            st.session_state.loaded_analysis = loaded["inputs"]
            st.sidebar.success(f"✅ Análisis '{loaded['name']}' cargado")
            st.rerun()
else:
    st.sidebar.caption("No hay análisis guardados")

# Apply loaded analysis values (if any)
if "loaded_analysis" in st.session_state:
    st.sidebar.info("ℹ️ Valores cargados del análisis guardado. Modifique los inputs en la barra lateral para aplicar.")
    # Clear the loaded state after displaying
    del st.session_state.loaded_analysis

# ------------- Compute -------------
# Calculate crédito fiscal from asset purchase (IVA paid on billed assets)
credito_fiscal_base = truck_price + (trailer_price if tolva_con_iva else 0.0)
credito_fiscal_total = credito_fiscal_base * iva_rate

# First compute results WITHOUT crédito fiscal (baseline / after credit exhausted)
results_without_credit = monthly_cashflow(
    truck_price=truck_price,
    trailer_price=trailer_price,
    capital=capital,
    reserve_min=reserve_min,
    financed_amount=financed_amount,
    annual_rate=annual_rate,
    years=years,
    m3_per_trip=m3_per_trip,
    price_per_m3=price_per_m3,
    trips_per_month=trips_per_month,
    diesel_cost=diesel_cost,
    toll_cost=toll_cost,
    driver_salary=driver_salary,
    maintenance_cost=maintenance_cost,
    other_costs=other_costs,
    iva_rate=iva_rate,
    it_rate=it_rate,
    credito_fiscal_available=0.0,
)

# Calculate monthly IVA without credit to determine how many months credit lasts
monthly_iva_full = results_without_credit["iva_before_credit"]
if monthly_iva_full > 0:
    months_credit_coverage = credito_fiscal_total / monthly_iva_full
else:
    months_credit_coverage = 0

# Compute results WITH full crédito fiscal (for months while credit lasts)
results_with_credit = monthly_cashflow(
    truck_price=truck_price,
    trailer_price=trailer_price,
    capital=capital,
    reserve_min=reserve_min,
    financed_amount=financed_amount,
    annual_rate=annual_rate,
    years=years,
    m3_per_trip=m3_per_trip,
    price_per_m3=price_per_m3,
    trips_per_month=trips_per_month,
    diesel_cost=diesel_cost,
    toll_cost=toll_cost,
    driver_salary=driver_salary,
    maintenance_cost=maintenance_cost,
    other_costs=other_costs,
    iva_rate=iva_rate,
    it_rate=it_rate,
    credito_fiscal_available=monthly_iva_full,  # Full offset while credit lasts
)

# Use results with credit for main display (represents first months)
results = results_with_credit

# Calculate monthly savings from crédito fiscal
monthly_iva_savings = results_with_credit["credito_fiscal_used"]
profit_difference = results_with_credit["profit_after_debt"] - results_without_credit["profit_after_debt"]

# ------------- Better Client Scenario Calculations -------------
better_client_results = None
if enable_better_client and better_rate_trips > 0 and trips_per_month > 0:
    # Reallocate trips: keep total trips constant, switch some trips to better rate
    total_trips_mixed = trips_per_month
    trips_current_rate = max(0.0, trips_per_month - float(better_rate_trips))
    
    # Calculate mixed revenue
    revenue_current_rate = trips_current_rate * m3_per_trip * price_per_m3
    revenue_better_rate = float(better_rate_trips) * m3_per_trip * better_rate
    mixed_monthly_revenue = revenue_current_rate + revenue_better_rate
    
    # Costs: total trips unchanged
    mixed_diesel_cost = diesel_cost_per_trip * total_trips_mixed
    mixed_toll_cost = toll_cost_per_trip * total_trips_mixed
    
    # Calculate mixed scenario using adjusted values
    # We need to compute this manually since monthly_cashflow expects uniform pricing
    mixed_operating_costs = mixed_diesel_cost + mixed_toll_cost + driver_salary + maintenance_cost + other_costs
    
    # Taxes on mixed revenue
    mixed_iva_before_credit = mixed_monthly_revenue * iva_rate
    mixed_it_tax = mixed_monthly_revenue * it_rate
    
    # Apply crédito fiscal (same as current scenario for comparison)
    mixed_credito_used = min(monthly_iva_full, mixed_iva_before_credit) if iva_rate > 0 else 0.0
    mixed_iva_tax = mixed_iva_before_credit - mixed_credito_used
    mixed_total_taxes = mixed_iva_tax + mixed_it_tax
    
    # Calculate profits
    mixed_total_costs = mixed_operating_costs + mixed_total_taxes
    mixed_profit_before_debt = mixed_monthly_revenue - mixed_total_costs
    mixed_profit_after_debt = mixed_profit_before_debt - results["monthly_payment"]
    
    # Calculate payback for mixed scenario
    mixed_payback_years = None
    if mixed_profit_after_debt > 0 and results["equity_used"] > 0:
        mixed_payback_years = results["equity_used"] / (mixed_profit_after_debt * 12)
    
    better_client_results = {
        "total_trips": total_trips_mixed,
        "trips_current_rate": trips_current_rate,
        "trips_better_rate": float(better_rate_trips),
        "revenue_current_rate": revenue_current_rate,
        "revenue_better_rate": revenue_better_rate,
        "monthly_revenue": mixed_monthly_revenue,
        "diesel_cost": mixed_diesel_cost,
        "operating_costs": mixed_operating_costs,
        "iva_tax": mixed_iva_tax,
        "it_tax": mixed_it_tax,
        "total_taxes": mixed_total_taxes,
        "profit_before_debt": mixed_profit_before_debt,
        "profit_after_debt": mixed_profit_after_debt,
        "payback_years": mixed_payback_years,
        "revenue_increase": mixed_monthly_revenue - results["monthly_revenue"],
        "profit_increase": mixed_profit_after_debt - results["profit_after_debt"],
    }

# ------------- Layout -------------
col1, col2 = st.columns(2)

with col1:
    st.header("📊 Resumen de la inversión")

    st.metric("Nombre del camión", truck_name)
    st.metric("Inversión total (camión + acople)", f"{results['investment_total']:,.0f} Bs")
    st.metric("Capital propio invertido", f"{results['equity_used']:,.0f} Bs")
    st.metric("Reserva de caja", f"{results['reserve']:,.0f} Bs")
    st.metric("Aporte propio + crédito", f"{results['total_funded']:,.0f} Bs")

    st.markdown("### 💳 Crédito")
    st.write(f"**Monto financiado:** {financed_amount:,.0f} Bs")
    st.write(f"**Tasa anual:** {annual_rate*100:.1f} %")
    st.write(f"**Plazo:** {years} años")
    st.metric("Cuota mensual", f"{results['monthly_payment']:,.0f} Bs")

    gap = results["funding_gap"]
    if gap > 0:
        st.warning(f"Faltan {gap:,.0f} Bs para cubrir toda la inversión.")
    elif gap < 0:
        st.info(f"Sobran {-gap:,.0f} Bs respecto al costo de la inversión.")
    else:
        st.success("El aporte propio + crédito cubren exactamente la inversión total.")

with col2:
    st.header("💰 Flujo mensual")

    st.metric("Ingresos mensuales", f"{results['monthly_revenue']:,.0f} Bs")
    st.metric("Costos operativos", f"{results['operating_costs']:,.0f} Bs")
    
    # Show taxes breakdown
    st.markdown("**🧾 Impuestos:**")
    if iva_rate > 0:
        tax_col1, tax_col2 = st.columns(2)
        with tax_col1:
            st.write(f"IVA ({iva_rate*100:.1f}%): {results['iva_tax']:,.0f} Bs")
        with tax_col2:
            st.write(f"IT ({it_rate*100:.1f}%): {results['it_tax']:,.0f} Bs")
    else:
        st.write(f"IT ({it_rate*100:.1f}%): {results['it_tax']:,.0f} Bs")
    st.metric("Total impuestos", f"{results['total_taxes']:,.0f} Bs")
    
    st.metric("Utilidad antes de deuda", f"{results['profit_before_debt']:,.0f} Bs")
    st.metric("Utilidad después de deuda", f"{results['profit_after_debt']:,.0f} Bs")

    if results["payback_years"] is not None:
        st.metric(
            "Payback sobre tu capital (años)",
            f"{results['payback_years']:.1f} años",
        )
    else:
        st.error("La utilidad después de deuda es negativa: así el camión no se paga solo.")

st.markdown("---")

st.subheader("📅 Escenario anual (aproximado)")
annual_profit = results["profit_after_debt"] * 12
st.write(f"**Utilidad neta anual estimada:** {annual_profit:,.0f} Bs")

# ------------- Crédito Fiscal Section -------------
st.markdown("---")
if iva_rate > 0:
    st.header("🧾 Crédito Fiscal por Compra de Activos")
    compra_iva_label = "camión + tolva/acople" if tolva_con_iva else "solo camión"

    st.markdown(f"""
    Al comprar el camión (y la tolva/acople si tiene factura), pagas **{iva_rate*100:.1f}% IVA** sobre el valor facturado con IVA (**{compra_iva_label}**). 
    Este IVA pagado se convierte en **crédito fiscal** que puedes usar para compensar 
    el IVA que debes pagar por tus ingresos mensuales.
    """)

    cf_col1, cf_col2, cf_col3 = st.columns(3)

    with cf_col1:
        st.metric(
            "Crédito Fiscal Total",
            f"{credito_fiscal_total:,.0f} Bs",
            help=f"{iva_rate*100:.1f}% de {credito_fiscal_base:,.0f} Bs (base con IVA: {compra_iva_label})",
        )
        st.caption(f"Base con IVA: {credito_fiscal_base:,.0f} Bs ({compra_iva_label})")

    with cf_col2:
        st.metric(
            "IVA Mensual (sin crédito)",
            f"{monthly_iva_full:,.0f} Bs",
            help="IVA que pagarías normalmente sobre tus ingresos",
        )

    with cf_col3:
        st.metric(
            "Meses de Cobertura",
            f"{months_credit_coverage:.1f} meses",
            help="Tiempo que el crédito fiscal cubre tu IVA mensual",
        )

    # Comparison table
    st.markdown("### 📊 Comparación: Con vs Sin Crédito Fiscal")

    comparison_col1, comparison_col2 = st.columns(2)

    with comparison_col1:
        st.markdown(f"""
        <div style="padding: 15px; background: rgba(40, 167, 69, 0.1); border-radius: 10px; border: 1px solid #28a745;">
            <h4 style="color: #28a745; margin: 0 0 10px 0;">✅ Con Crédito Fiscal</h4>
            <p style="color: #888; margin: 5px 0; font-size: 0.9em;">Primeros {months_credit_coverage:.0f} meses</p>
            <p style="color: #ccc; margin: 5px 0;">IVA efectivo: <strong style="color: #28a745;">{results_with_credit['iva_tax']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Total impuestos: <strong>{results_with_credit['total_taxes']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Utilidad mensual: <strong style="color: #28a745;">{results_with_credit['profit_after_debt']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Utilidad anual: <strong>{results_with_credit['profit_after_debt'] * 12:,.0f} Bs</strong></p>
        </div>
        """, unsafe_allow_html=True)

    with comparison_col2:
        st.markdown(f"""
        <div style="padding: 15px; background: rgba(255, 193, 7, 0.1); border-radius: 10px; border: 1px solid #ffc107;">
            <h4 style="color: #ffc107; margin: 0 0 10px 0;">⚠️ Sin Crédito Fiscal</h4>
            <p style="color: #888; margin: 5px 0; font-size: 0.9em;">Después de agotar el crédito</p>
            <p style="color: #ccc; margin: 5px 0;">IVA efectivo: <strong style="color: #ffc107;">{results_without_credit['iva_tax']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Total impuestos: <strong>{results_without_credit['total_taxes']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Utilidad mensual: <strong style="color: #ffc107;">{results_without_credit['profit_after_debt']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Utilidad anual: <strong>{results_without_credit['profit_after_debt'] * 12:,.0f} Bs</strong></p>
        </div>
        """, unsafe_allow_html=True)

    # Monthly savings highlight
    st.info(f"""
    💰 **Ahorro mensual con crédito fiscal:** {monthly_iva_savings:,.0f} Bs  
    📈 **Ganancia adicional durante {months_credit_coverage:.0f} meses:** {credito_fiscal_total:,.0f} Bs (el total del crédito fiscal)
    """)
else:
    st.header("🧾 IVA / Crédito Fiscal")
    st.info("IVA desactivado: no se calcula IVA ni aplica crédito fiscal por compra de activos.")

# ------------- Better Client Opportunity Section -------------
if enable_better_client and better_client_results:
    st.markdown("---")
    st.header("🤝 Oportunidad: Mejor Cliente")
    
    st.markdown(f"""
    Este análisis muestra el impacto de **reasignar {better_rate_trips:.0f} de tus {trips_per_month:.0f} viajes/mes**
    a una tarifa de **{better_rate:.0f} Bs/m³** (vs tu tarifa actual de {price_per_m3:.0f} Bs/m³).
    """)
    
    # Key metrics row
    bc_col1, bc_col2, bc_col3, bc_col4 = st.columns(4)
    
    with bc_col1:
        st.metric(
            "Viajes a mejor tarifa",
            f"{better_client_results['trips_better_rate']:.0f}",
            help=f"De {trips_per_month:.0f} viajes/mes, {better_client_results['trips_current_rate']:.0f} quedan a tarifa actual."
        )
    
    with bc_col2:
        revenue_delta = better_client_results['revenue_increase']
        st.metric(
            "Ingresos mensuales",
            f"{better_client_results['monthly_revenue']:,.0f} Bs",
            delta=f"+{revenue_delta:,.0f} Bs"
        )
    
    with bc_col3:
        profit_delta = better_client_results['profit_increase']
        st.metric(
            "Utilidad mensual",
            f"{better_client_results['profit_after_debt']:,.0f} Bs",
            delta=f"+{profit_delta:,.0f} Bs"
        )
    
    with bc_col4:
        if better_client_results['payback_years']:
            payback_delta = results['payback_years'] - better_client_results['payback_years'] if results['payback_years'] else 0
            st.metric(
                "Payback",
                f"{better_client_results['payback_years']:.1f} años",
                delta=f"-{payback_delta:.1f} años" if payback_delta > 0 else None,
                delta_color="inverse"
            )
        else:
            st.metric("Payback", "N/A")
    
    # Comparison cards
    st.markdown("### 📊 Comparación: Escenario Actual vs Mejor Cliente")
    
    bc_compare_col1, bc_compare_col2 = st.columns(2)
    
    with bc_compare_col1:
        st.markdown(f"""
        <div style="padding: 15px; background: rgba(108, 117, 125, 0.1); border-radius: 10px; border: 1px solid #6c757d;">
            <h4 style="color: #6c757d; margin: 0 0 10px 0;">📍 Escenario Actual</h4>
            <p style="color: #888; margin: 5px 0; font-size: 0.9em;">{trips_per_month:.0f} viajes a {price_per_m3:.0f} Bs/m³</p>
            <p style="color: #ccc; margin: 5px 0;">Ingresos: <strong>{results['monthly_revenue']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Costos operativos: <strong>{results['operating_costs']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Utilidad mensual: <strong>{results['profit_after_debt']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Utilidad anual: <strong>{results['profit_after_debt'] * 12:,.0f} Bs</strong></p>
        </div>
        """, unsafe_allow_html=True)
    
    with bc_compare_col2:
        st.markdown(f"""
        <div style="padding: 15px; background: rgba(40, 167, 69, 0.1); border-radius: 10px; border: 1px solid #28a745;">
            <h4 style="color: #28a745; margin: 0 0 10px 0;">🚀 Con Mejor Cliente</h4>
            <p style="color: #888; margin: 5px 0; font-size: 0.9em;">{better_client_results['trips_current_rate']:.0f} viajes a {price_per_m3:.0f} Bs/m³ + {better_client_results['trips_better_rate']:.0f} viajes a {better_rate:.0f} Bs/m³</p>
            <p style="color: #ccc; margin: 5px 0;">Ingresos: <strong style="color: #28a745;">{better_client_results['monthly_revenue']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Costos operativos: <strong>{better_client_results['operating_costs']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Utilidad mensual: <strong style="color: #28a745;">{better_client_results['profit_after_debt']:,.0f} Bs</strong></p>
            <p style="color: #ccc; margin: 5px 0;">Utilidad anual: <strong>{better_client_results['profit_after_debt'] * 12:,.0f} Bs</strong></p>
        </div>
        """, unsafe_allow_html=True)
    
    # Revenue breakdown visualization
    st.markdown("### 💰 Desglose de Ingresos con Mejor Cliente")
    
    breakdown_col1, breakdown_col2 = st.columns([2, 1])
    
    with breakdown_col1:
        # Visual breakdown of revenue sources
        pct_current = (better_client_results['revenue_current_rate'] / better_client_results['monthly_revenue']) * 100
        pct_better = (better_client_results['revenue_better_rate'] / better_client_results['monthly_revenue']) * 100
        
        st.markdown(f"""
        <div style="padding: 15px; background: #0e1117; border-radius: 10px;">
            <p style="color: #ccc; margin: 0 0 10px 0;"><strong>Composición de ingresos mensuales:</strong></p>
            <div style="display: flex; height: 30px; border-radius: 5px; overflow: hidden; margin-bottom: 10px;">
                <div style="width: {pct_current}%; background: #6c757d; display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-size: 0.8em;">{pct_current:.0f}%</span>
                </div>
                <div style="width: {pct_better}%; background: #28a745; display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-size: 0.8em;">{pct_better:.0f}%</span>
                </div>
            </div>
            <p style="color: #888; margin: 5px 0; font-size: 0.85em;">
                <span style="color: #6c757d;">■</span> Tarifa actual ({price_per_m3:.0f} Bs/m³): {better_client_results['revenue_current_rate']:,.0f} Bs
            </p>
            <p style="color: #888; margin: 5px 0; font-size: 0.85em;">
                <span style="color: #28a745;">■</span> Mejor tarifa ({better_rate:.0f} Bs/m³): {better_client_results['revenue_better_rate']:,.0f} Bs
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with breakdown_col2:
        annual_profit_increase = better_client_results['profit_increase'] * 12
        st.markdown(f"""
        <div style="padding: 15px; background: rgba(40, 167, 69, 0.15); border-radius: 10px; text-align: center;">
            <p style="color: #888; margin: 0; font-size: 0.85em;">Ganancia adicional anual</p>
            <h2 style="color: #28a745; margin: 5px 0;">{annual_profit_increase:,.0f} Bs</h2>
            <p style="color: #aaa; margin: 0; font-size: 0.8em;">+{better_client_results['profit_increase']:,.0f} Bs/mes</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Line chart: Profit improvement as better-rate trips increase
    st.markdown("### 📈 Impacto de Viajes a Mejor Tarifa")
    
    # Generate data for 0..total trips (reallocation within same monthly trips)
    max_better_trips_chart = max(0, trips_per_month_int)
    better_trips_range = list(range(0, max_better_trips_chart + 1))
    profit_by_better_trips = []
    
    for bt in better_trips_range:
        # Scenario: bt trips at better rate, remaining trips at current rate (total trips constant)
        scenario_total_trips = trips_per_month
        scenario_trips_current = max(0.0, trips_per_month - float(bt))
        scenario_revenue_current = scenario_trips_current * m3_per_trip * price_per_m3
        scenario_revenue_better = float(bt) * m3_per_trip * better_rate
        scenario_total_revenue = scenario_revenue_current + scenario_revenue_better
        
        # Costs (total trips unchanged)
        scenario_diesel = diesel_cost_per_trip * scenario_total_trips
        scenario_toll = toll_cost_per_trip * scenario_total_trips
        scenario_operating = scenario_diesel + scenario_toll + driver_salary + maintenance_cost + other_costs
        
        # Taxes (match the same crédito fiscal logic used above)
        scenario_iva_before_credit = scenario_total_revenue * iva_rate
        scenario_credito_used = min(monthly_iva_full, scenario_iva_before_credit) if iva_rate > 0 else 0.0
        scenario_iva = scenario_iva_before_credit - scenario_credito_used
        scenario_it = scenario_total_revenue * it_rate
        scenario_taxes = scenario_iva + scenario_it
        
        # Profit
        scenario_profit_before = scenario_total_revenue - scenario_operating - scenario_taxes
        scenario_profit_after = scenario_profit_before - results["monthly_payment"]
        
        profit_by_better_trips.append(scenario_profit_after)
    
    # Create the line chart with Plotly
    fig_better_trips = go.Figure()
    
    # Main line - profit progression
    fig_better_trips.add_trace(go.Scatter(
        x=better_trips_range,
        y=profit_by_better_trips,
        mode='lines+markers',
        name='Utilidad Mensual',
        line=dict(color='#28a745', width=3),
        marker=dict(size=6),
        fill='tozeroy',
        fillcolor='rgba(40, 167, 69, 0.1)',
    ))
    
    # Horizontal line for current scenario (0 better trips)
    fig_better_trips.add_hline(
        y=results["profit_after_debt"],
        line_dash="dash",
        line_color="#6c757d",
        annotation_text=f"Escenario actual: {results['profit_after_debt']:,.0f} Bs",
        annotation_position="top right",
        annotation_font_color="#888",
    )
    
    # Vertical line marking selected better trips
    if better_rate_trips > 0:
        selected_idx = int(better_rate_trips)
        if selected_idx < len(profit_by_better_trips):
            fig_better_trips.add_vline(
                x=selected_idx,
                line_dash="dot",
                line_color="#ffc107",
                annotation_text=f"{selected_idx} viajes seleccionados",
                annotation_position="top",
                annotation_font_color="#ffc107",
            )
    
    fig_better_trips.update_layout(
        xaxis_title="Viajes reasignados a mejor tarifa",
        yaxis_title="Utilidad Mensual (Bs)",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#ccc'),
        xaxis=dict(
            gridcolor='rgba(255,255,255,0.1)',
            tickfont=dict(color='#888'),
        ),
        yaxis=dict(
            gridcolor='rgba(255,255,255,0.1)',
            tickfont=dict(color='#888'),
            tickformat=',',
        ),
        margin=dict(l=60, r=40, t=40, b=60),
        height=350,
        showlegend=False,
    )
    
    st.plotly_chart(fig_better_trips, use_container_width=True)
    
    delta_ingreso_por_viaje = m3_per_trip * (better_rate - price_per_m3)
    st.caption(f"Cada viaje reasignado de {price_per_m3:.0f} → {better_rate:.0f} Bs/m³ cambia ingresos en {delta_ingreso_por_viaje:,.0f} Bs (antes de impuestos).")
    
    # Analysis insight
    rate_difference = better_rate - price_per_m3
    rate_pct_increase = (rate_difference / price_per_m3) * 100 if price_per_m3 > 0 else 0
    
    if better_client_results['profit_increase'] > 0:
        st.success(f"""
        💡 **Resumen:** Reasignar {better_rate_trips:.0f} viajes a {better_rate:.0f} Bs/m³ (un {rate_pct_increase:.0f}% más que tu tarifa actual) 
        aumentaría tu utilidad en **{better_client_results['profit_increase']:,.0f} Bs/mes** ({annual_profit_increase:,.0f} Bs/año).
        """)
    else:
        st.warning(f"""
        ⚠️ **Atención:** Esta reasignación no mejora tu utilidad (la tarifa del "mejor cliente" no es suficientemente alta vs tu tarifa actual, considerando impuestos).
        Considera negociar una tarifa más alta o ajustar la mezcla de viajes.
        """)

# ------------- Investment Analysis Section -------------
st.markdown("---")
st.header("🔍 Análisis de Viabilidad de la Inversión")

# If "Mejor Cliente" is enabled, run viability analysis on that scenario's cashflow
analysis_results = results
analysis_context = "Escenario actual"
if enable_better_client and better_client_results:
    analysis_context = "Escenario con mejor cliente"
    analysis_results = dict(results)
    analysis_results.update(
        {
            "monthly_revenue": better_client_results["monthly_revenue"],
            "operating_costs": better_client_results["operating_costs"],
            "iva_tax": better_client_results.get("iva_tax", analysis_results.get("iva_tax", 0.0)),
            "it_tax": better_client_results.get("it_tax", analysis_results.get("it_tax", 0.0)),
            "total_taxes": better_client_results.get("total_taxes", analysis_results.get("total_taxes", 0.0)),
            "total_costs": better_client_results["operating_costs"]
            + better_client_results.get("total_taxes", analysis_results.get("total_taxes", 0.0)),
            "profit_before_debt": better_client_results["profit_before_debt"],
            "profit_after_debt": better_client_results["profit_after_debt"],
            "payback_years": better_client_results["payback_years"],
        }
    )

st.caption(f"Evaluado sobre: **{analysis_context}**")
analysis = analyze_investment(analysis_results, financed_amount, years, results["investment_total"])

# Prepare inputs for PDF
pdf_inputs = {
    'truck_name': truck_name,
    'analysis_context': analysis_context,
    'truck_price': truck_price,
    'trailer_price': trailer_price,
    'capital': capital,
    'reserve_min': reserve_min,
    'better_client_enabled': bool(enable_better_client and better_client_results),
    'better_rate': float(better_rate) if enable_better_client else 0.0,
    'better_rate_trips': float(better_rate_trips) if enable_better_client else 0.0,
    'base_price_per_m3': float(price_per_m3),
    'baseline_results': results,
    'better_client_results': better_client_results,
    'financed_amount': financed_amount,
    'annual_rate': annual_rate,
    'years': years,
    'm3_per_trip': m3_per_trip,
    'price_per_m3': price_per_m3,
    'trips_per_month': trips_per_month,
    'diesel_cost': diesel_cost,
    'diesel_cost_per_trip': diesel_cost_per_trip,
    'toll_cost': toll_cost,
    'toll_cost_per_trip': toll_cost_per_trip,
    'driver_salary': driver_salary,
    'maintenance_cost': maintenance_cost,
    'other_costs': other_costs,
    'iva_rate': iva_rate,
    'it_rate': it_rate,
    'tolva_con_iva': tolva_con_iva,
    'credito_fiscal_base': credito_fiscal_base,
    'credito_fiscal_total': credito_fiscal_total,
    'months_credit_coverage': months_credit_coverage,
    'monthly_iva_savings': monthly_iva_savings,
    'results_without_credit': results_without_credit,
}

# Overall Score Display
score_col1, score_col2 = st.columns([1, 2])

with score_col1:
    # Create a visual score gauge
    score = analysis["overall_score"]
    if score >= 70:
        score_color = "#28a745"
    elif score >= 50:
        score_color = "#ffc107"
    else:
        score_color = "#dc3545"
    
    st.markdown(f"""
    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 15px; border: 2px solid {score_color};">
        <h1 style="font-size: 3.5em; margin: 0; color: {score_color};">{score:.0f}</h1>
        <p style="margin: 5px 0; color: #888; font-size: 1.1em;">de 100 puntos</p>
        <h3 style="margin: 10px 0 0 0; color: {score_color};">{analysis['recommendation_icon']} {analysis['recommendation']}</h3>
    </div>
    """, unsafe_allow_html=True)

with score_col2:
    st.markdown(f"""
    <div style="padding: 20px; background: #0e1117; border-radius: 10px; border-left: 4px solid {score_color};">
        <h4 style="margin: 0 0 10px 0; color: #fafafa;">Resumen del Análisis</h4>
        <p style="color: #ccc; line-height: 1.6;">{analysis['summary']}</p>
    </div>
    """, unsafe_allow_html=True)

# Radar Chart for Investment Quality
st.markdown("### 🎯 Perfil de la Inversión")

# Prepare radar chart data - normalize scores to percentages
radar_categories = [m['name'] for m in analysis['metrics']]
radar_values = [(m['score'] / m['max_score']) * 100 for m in analysis['metrics']]
# Close the radar by repeating first value
radar_categories_closed = radar_categories + [radar_categories[0]]
radar_values_closed = radar_values + [radar_values[0]]

# Determine fill color based on overall score
if analysis['overall_score'] >= 70:
    radar_fill_color = 'rgba(40, 167, 69, 0.3)'
    radar_line_color = '#28a745'
elif analysis['overall_score'] >= 50:
    radar_fill_color = 'rgba(255, 193, 7, 0.3)'
    radar_line_color = '#ffc107'
else:
    radar_fill_color = 'rgba(220, 53, 69, 0.3)'
    radar_line_color = '#dc3545'

fig_radar = go.Figure()

fig_radar.add_trace(go.Scatterpolar(
    r=radar_values_closed,
    theta=radar_categories_closed,
    fill='toself',
    fillcolor=radar_fill_color,
    line=dict(color=radar_line_color, width=2),
    name='Tu Inversión'
))

fig_radar.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, 100],
            tickfont=dict(size=10, color='#888'),
            gridcolor='rgba(255,255,255,0.1)',
        ),
        angularaxis=dict(
            tickfont=dict(size=11, color='#ccc'),
            gridcolor='rgba(255,255,255,0.1)',
        ),
        bgcolor='rgba(0,0,0,0)',
    ),
    showlegend=False,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=80, r=80, t=40, b=40),
    height=400,
)

st.plotly_chart(fig_radar, use_container_width=True)

st.caption("El gráfico muestra el porcentaje alcanzado en cada métrica (100% = máximo puntaje)")

# Detailed Metrics
st.markdown("### 📊 Métricas Detalladas")

metrics_cols = st.columns(len(analysis["metrics"]))

for i, metric in enumerate(analysis["metrics"]):
    with metrics_cols[i]:
        status = metric["status"]
        if status == "excellent":
            color = "#28a745"
            bg = "rgba(40, 167, 69, 0.1)"
        elif status == "good":
            color = "#17a2b8"
            bg = "rgba(23, 162, 184, 0.1)"
        elif status == "fair":
            color = "#ffc107"
            bg = "rgba(255, 193, 7, 0.1)"
        elif status == "warning":
            color = "#fd7e14"
            bg = "rgba(253, 126, 20, 0.1)"
        else:  # critical
            color = "#dc3545"
            bg = "rgba(220, 53, 69, 0.1)"
        
        pct = (metric["score"] / metric["max_score"]) * 100
        
        st.markdown(f"""
        <div style="padding: 15px; background: {bg}; border-radius: 10px; border: 1px solid {color}; height: 180px;">
            <p style="color: #888; font-size: 0.85em; margin: 0;">{metric['name']}</p>
            <h3 style="color: {color}; margin: 5px 0;">{metric['value']}</h3>
            <div style="background: #333; border-radius: 5px; height: 8px; margin: 10px 0;">
                <div style="background: {color}; width: {pct}%; height: 8px; border-radius: 5px;"></div>
            </div>
            <p style="color: #aaa; font-size: 0.8em; margin: 0;">{metric['description']}</p>
        </div>
        """, unsafe_allow_html=True)

# Strengths and Warnings
str_warn_col1, str_warn_col2 = st.columns(2)

with str_warn_col1:
    if analysis["strengths"]:
        st.markdown("### ✅ Fortalezas")
        for strength in analysis["strengths"]:
            st.success(f"✓ {strength}")

with str_warn_col2:
    if analysis["warnings"]:
        st.markdown("### ⚠️ Advertencias")
        for warning in analysis["warnings"]:
            st.warning(f"• {warning}")

# Recommendations based on score
st.markdown("### 💡 Recomendaciones")

if analysis["overall_score"] >= 70:
    st.markdown("""
    <div style="padding: 15px; background: rgba(40, 167, 69, 0.1); border-radius: 10px; border-left: 4px solid #28a745;">
        <ul style="color: #ccc; margin: 0; padding-left: 20px;">
            <li>La inversión tiene fundamentales sólidos - considera proceder</li>
            <li>Mantén una reserva de emergencia para imprevistos</li>
            <li>Monitorea los costos operativos mensualmente</li>
            <li>Considera reinvertir las ganancias para acelerar el payback</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
elif analysis["overall_score"] >= 50:
    st.markdown("""
    <div style="padding: 15px; background: rgba(255, 193, 7, 0.1); border-radius: 10px; border-left: 4px solid #ffc107;">
        <ul style="color: #ccc; margin: 0; padding-left: 20px;">
            <li>Busca negociar mejores condiciones de crédito (menor tasa o mayor plazo)</li>
            <li>Explora formas de aumentar los ingresos (más viajes, mejor tarifa)</li>
            <li>Revisa si puedes reducir costos operativos</li>
            <li>Considera aumentar el capital propio para reducir la deuda</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="padding: 15px; background: rgba(220, 53, 69, 0.1); border-radius: 10px; border-left: 4px solid #dc3545;">
        <ul style="color: #ccc; margin: 0; padding-left: 20px;">
            <li><strong>No proceder</strong> con las condiciones actuales</li>
            <li>Necesitas aumentar significativamente los ingresos o reducir costos</li>
            <li>Busca financiamiento con mejores condiciones</li>
            <li>Considera un vehículo más económico o un modelo de negocio diferente</li>
            <li>Reevalúa si este negocio es viable para tu situación financiera</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ------------- Trips Sensitivity Analysis -------------
st.header("📈 Análisis de Sensibilidad: Viajes por Mes")
st.markdown("Explora cómo cambian los resultados con diferentes cantidades de viajes mensuales.")

# Create range of trips to analyze
current_trips = int(trips_per_month)
min_trips = max(5, current_trips - 10)
max_trips = current_trips + 15

trips_range = list(range(min_trips, max_trips + 1, 2))
if current_trips not in trips_range:
    trips_range.append(current_trips)
    trips_range.sort()

sensitivity_data = []
for trips in trips_range:
    # Recalculate diesel and toll cost based on trips
    scenario_diesel_cost = diesel_cost_per_trip * trips
    scenario_toll_cost = toll_cost_per_trip * trips
    scenario_results = monthly_cashflow(
        truck_price=truck_price,
        trailer_price=trailer_price,
        capital=capital,
        reserve_min=reserve_min,
        financed_amount=financed_amount,
        annual_rate=annual_rate,
        years=years,
        m3_per_trip=m3_per_trip,
        price_per_m3=price_per_m3,
        trips_per_month=trips,
        diesel_cost=scenario_diesel_cost,
        toll_cost=scenario_toll_cost,
        driver_salary=driver_salary,
        maintenance_cost=maintenance_cost,
        other_costs=other_costs,
        iva_rate=iva_rate,
        it_rate=it_rate,
    )
    scenario_analysis = analyze_investment(scenario_results, financed_amount, years, scenario_results["investment_total"])
    
    sensitivity_data.append({
        "Viajes/Mes": trips,
        "Ingresos (Bs)": scenario_results["monthly_revenue"],
        "Utilidad Neta (Bs)": scenario_results["profit_after_debt"],
        "Utilidad Anual (Bs)": scenario_results["profit_after_debt"] * 12,
        "Payback (años)": scenario_results["payback_years"] if scenario_results["payback_years"] else float('inf'),
        "Score": scenario_analysis["overall_score"],
        "Recomendación": scenario_analysis["recommendation"],
        "Es actual": trips == current_trips
    })

df_sensitivity = pd.DataFrame(sensitivity_data)

# PDF Download Button
st.markdown("---")
st.subheader("📄 Descargar Reporte PDF")

pdf_col1, pdf_col2 = st.columns([1, 3])

with pdf_col1:
    # Generate PDF with all data
    pdf_bytes = generate_pdf_report(analysis_results, analysis, pdf_inputs, sensitivity_data)
    
    st.download_button(
        label="📥 Descargar Análisis PDF",
        data=pdf_bytes,
        file_name=f"investment_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf",
        help="Descarga un reporte PDF completo con todos los datos del análisis"
    )

with pdf_col2:
    st.markdown("""
    <div style="padding: 10px; background: rgba(30, 136, 229, 0.1); border-radius: 8px; border-left: 3px solid #1e88e5;">
        <p style="margin: 0; color: #ccc; font-size: 0.9em;">
            El PDF incluye: resumen de inversión, detalles del crédito, flujo mensual, 
            análisis de viabilidad, métricas detalladas, fortalezas, advertencias y análisis de sensibilidad.
        </p>
    </div>
    """, unsafe_allow_html=True)

# Save Analysis Section
st.markdown("---")
st.subheader("💾 Guardar Análisis")

save_col1, save_col2 = st.columns([2, 1])

with save_col1:
    analysis_name = st.text_input(
        "Nombre del análisis",
        value=f"{truck_name} - {datetime.now().strftime('%d/%m/%Y')}",
        placeholder="Ej: Análisis SITRAK - Enero 2025",
        key="save_analysis_name"
    )

with save_col2:
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing to align with input
    if st.button("💾 Guardar Análisis", use_container_width=True):
        if analysis_name.strip():
            # Prepare serializable results (remove non-JSON serializable items)
            results_to_save = {k: v for k, v in analysis_results.items() if not isinstance(v, (pd.DataFrame,))}
            analysis_to_save = {k: v for k, v in analysis.items() if k != "metrics" or isinstance(v, list)}
            
            db.save_investment_analysis(
                name=analysis_name.strip(),
                truck_name=truck_name,
                inputs=pdf_inputs,
                results=results_to_save,
                analysis=analysis_to_save
            )
            st.success(f"✅ Análisis '{analysis_name}' guardado exitosamente")
            st.rerun()
        else:
            st.error("Por favor ingresa un nombre para el análisis")

st.markdown("---")

# Create visualization columns
chart_col, table_col = st.columns([1.2, 1])

with chart_col:
    st.markdown("#### Utilidad Neta Mensual por Cantidad de Viajes")
    
    # Prepare chart data
    chart_data = df_sensitivity[["Viajes/Mes", "Utilidad Neta (Bs)"]].copy()
    chart_data = chart_data.set_index("Viajes/Mes")
    
    # Use Streamlit's native chart with highlighting
    st.line_chart(chart_data, height=300)
    
    # Show breakeven point
    breakeven_trips = None
    for row in sensitivity_data:
        if row["Utilidad Neta (Bs)"] >= 0:
            breakeven_trips = row["Viajes/Mes"]
            break
    
    if breakeven_trips:
        st.info(f"📍 **Punto de equilibrio:** Necesitas al menos **{breakeven_trips} viajes/mes** para ser rentable")
    else:
        st.warning("⚠️ No se alcanza punto de equilibrio en el rango analizado")

with table_col:
    st.markdown("#### Comparativa de Escenarios")
    
    # Format the dataframe for display
    display_df = df_sensitivity.copy()
    display_df["Utilidad Neta (Bs)"] = display_df["Utilidad Neta (Bs)"].apply(lambda x: f"{x:,.0f}")
    display_df["Utilidad Anual (Bs)"] = display_df["Utilidad Anual (Bs)"].apply(lambda x: f"{x:,.0f}")
    display_df["Ingresos (Bs)"] = display_df["Ingresos (Bs)"].apply(lambda x: f"{x:,.0f}")
    display_df["Score"] = display_df["Score"].apply(lambda x: f"{x:.0f}")
    display_df["Payback (años)"] = display_df["Payback (años)"].apply(lambda x: f"{x:.1f}" if x != float('inf') else "N/A")
    
    # Add indicator for current scenario
    display_df[""] = display_df["Es actual"].apply(lambda x: "◀ ACTUAL" if x else "")
    
    # Select columns to show
    show_cols = ["Viajes/Mes", "Utilidad Neta (Bs)", "Score", "Recomendación", ""]
    st.dataframe(display_df[show_cols], use_container_width=True, hide_index=True, height=300)

# Interactive scenario comparison
st.markdown("#### 🔄 Comparador Interactivo")
compare_cols = st.columns(3)

with compare_cols[0]:
    compare_trips = st.slider(
        "Selecciona viajes para comparar",
        min_value=min_trips,
        max_value=max_trips,
        value=current_trips,
        step=1
    )

# Calculate comparison scenario (with adjusted diesel and toll cost)
compare_diesel_cost = diesel_cost_per_trip * compare_trips
compare_toll_cost = toll_cost_per_trip * compare_trips
compare_results = monthly_cashflow(
    truck_price=truck_price,
    trailer_price=trailer_price,
    capital=capital,
    reserve_min=reserve_min,
    financed_amount=financed_amount,
    annual_rate=annual_rate,
    years=years,
    m3_per_trip=m3_per_trip,
    price_per_m3=price_per_m3,
    trips_per_month=compare_trips,
    diesel_cost=compare_diesel_cost,
    toll_cost=compare_toll_cost,
    driver_salary=driver_salary,
    maintenance_cost=maintenance_cost,
    other_costs=other_costs,
    iva_rate=iva_rate,
    it_rate=it_rate,
)
compare_analysis = analyze_investment(compare_results, financed_amount, years, compare_results["investment_total"])

with compare_cols[1]:
    diff_profit = compare_results["profit_after_debt"] - results["profit_after_debt"]
    diff_sign = "+" if diff_profit >= 0 else ""
    st.metric(
        f"Utilidad con {compare_trips} viajes",
        f"{compare_results['profit_after_debt']:,.0f} Bs",
        delta=f"{diff_sign}{diff_profit:,.0f} Bs vs actual"
    )

with compare_cols[2]:
    diff_score = compare_analysis["overall_score"] - analysis["overall_score"]
    diff_sign = "+" if diff_score >= 0 else ""
    
    rec_color = compare_analysis.get("recommendation_color", "gray")
    st.metric(
        f"Score con {compare_trips} viajes",
        f"{compare_analysis['overall_score']:.0f} pts",
        delta=f"{diff_sign}{diff_score:.0f} pts"
    )
    st.markdown(f"**{compare_analysis['recommendation_icon']} {compare_analysis['recommendation']}**")

# Quick insight
if compare_trips != current_trips:
    trips_diff = compare_trips - current_trips
    annual_diff = diff_profit * 12
    if trips_diff > 0:
        st.success(f"💡 Aumentando a **{compare_trips} viajes/mes** (+{trips_diff}) ganarías **{annual_diff:,.0f} Bs más al año**")
    else:
        if annual_diff < 0:
            st.warning(f"⚠️ Reduciendo a **{compare_trips} viajes/mes** ({trips_diff}) perderías **{-annual_diff:,.0f} Bs al año**")
        else:
            st.info(f"📊 Con **{compare_trips} viajes/mes** tendrías **{annual_diff:,.0f} Bs de diferencia anual**")

st.markdown("---")
st.subheader("📉 Tabla de amortización del crédito")

if financed_amount > 0 and years > 0:
    schedule = amortization_schedule(financed_amount, annual_rate, years)
    if schedule:
        df_schedule = pd.DataFrame(schedule)
        st.dataframe(df_schedule, use_container_width=True)
    else:
        st.info("No hay datos de amortización para mostrar.")
else:
    st.info("Define un monto financiado y un plazo mayor a 0 para ver la amortización.")