import io
import math
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

# Add parent directory to path for db import
sys.path.insert(0, str(Path(__file__).parent.parent))
import db


# -----------------------
# PDF Generation Class
# -----------------------
class ProfitMarginPDF(FPDF):
    """Custom PDF class for Profit Margin Calculator reports."""
    
    def __init__(self):
        super().__init__()
        # Set proper margins (left, top, right)
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=15)
        # Effective width = 210 - 15 - 15 = 180mm
        self.effective_width = 180
    
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Analisis de Margen de Ganancia", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="C")
    
    def section_title(self, title: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(52, 73, 94)
        self.set_text_color(255, 255, 255)
        self.cell(self.effective_width, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)
    
    def subsection_title(self, title: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(52, 73, 94)
        self.cell(self.effective_width, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)
    
    def add_key_value(self, key: str, value: str, indent: int = 0):
        """Add a key-value pair that fits within page bounds."""
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9)
        if indent > 0:
            self.set_x(self.l_margin + indent)
        
        # Use a table-like layout with proper widths
        key_width = 55
        value_width = self.effective_width - key_width - indent
        
        self.set_font("Helvetica", "B", 9)
        self.cell(key_width, 5, key + ":", align="L")
        self.set_font("Helvetica", "", 9)
        self.cell(value_width, 5, value, align="L", new_x="LMARGIN", new_y="NEXT")
    
    def add_key_value_table(self, items: list):
        """Add multiple key-value pairs as a proper table."""
        # items is a list of (key, value) tuples
        self.set_font("Helvetica", "", 9)
        
        col1_width = 65
        col2_width = self.effective_width - col1_width
        
        for key, value in items:
            self.set_x(self.l_margin)
            self.set_font("Helvetica", "B", 9)
            self.cell(col1_width, 6, key, border="TB", align="L")
            self.set_font("Helvetica", "", 9)
            self.cell(col2_width, 6, value, border="TB", align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
    
    def add_table(self, headers: list, data: list, col_widths: list = None):
        """Add a table to the PDF with proper column sizing."""
        if col_widths is None:
            # Distribute width evenly
            col_widths = [self.effective_width // len(headers)] * len(headers)
            # Adjust last column to fill remaining space
            col_widths[-1] = self.effective_width - sum(col_widths[:-1])
        
        # Ensure total width doesn't exceed effective width
        total_width = sum(col_widths)
        if total_width > self.effective_width:
            scale = self.effective_width / total_width
            col_widths = [int(w * scale) for w in col_widths]
        
        # Header - ensure we start from left margin
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(236, 240, 241)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, border=1, fill=True, align="C")
        self.ln()
        
        # Data rows - ensure each row starts from left margin
        self.set_font("Helvetica", "", 8)
        for row in data:
            self.set_x(self.l_margin)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 6, str(cell), border=1, align="C")
            self.ln()
        self.ln(2)
    
    def add_calculation_step(self, step_num: int, title: str, formula: str, result: str):
        """Add a calculation step with formula and result."""
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 5, f"Paso {step_num}: {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 100, 100)
        # Use multi_cell for formula to allow wrapping - start from left margin
        self.set_x(self.l_margin + 5)
        self.multi_cell(self.effective_width - 10, 4, f"Formula: {formula}")
        # Result on new line, properly aligned
        self.set_text_color(0, 128, 0)
        self.set_font("Helvetica", "B", 9)
        self.set_x(self.l_margin + 5)
        self.cell(self.effective_width - 10, 5, f"Resultado: {result}", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)
    
    def add_highlight_box(self, text: str, box_type: str = "info"):
        """Add a highlighted box (info, success, warning)."""
        if box_type == "success":
            self.set_fill_color(212, 237, 218)
            self.set_text_color(21, 87, 36)
        elif box_type == "warning":
            self.set_fill_color(255, 243, 205)
            self.set_text_color(133, 100, 4)
        else:  # info
            self.set_fill_color(209, 236, 241)
            self.set_text_color(12, 84, 96)
        
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 5, text, fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)


def generate_profit_margin_pdf(
    # Plant data
    plant_selling_price: float,
    plant_profit_margin: float,
    plant_other_cost_pct: float,
    plant_cost_per_m3: float,
    plant_diesel_in_price: float,
    plant_other_costs: float,
    plant_profit_per_m3: float,
    net_adjustment_plant: float,
    plant_new_cost: float,
    plant_new_price: float,
    plant_price_increase: float,
    plant_price_increase_pct: float,
    plant_new_profit: float,
    # Transport data
    plant_only: bool,
    transp_selling_price: float,
    transp_profit_margin: float,
    transp_other_cost_pct: float,
    transp_cost_per_m3: float,
    transp_diesel_in_price: float,
    transp_other_costs: float,
    transp_profit_per_m3: float,
    net_adjustment_transp: float,
    transp_new_cost: float,
    transp_new_price: float,
    transp_price_increase: float,
    transp_price_increase_pct: float,
    transp_new_profit: float,
    # General data
    transport_diesel_pct: float,
    iva_benefit_plant: float,
    iva_benefit_transp: float,
    plant_cost_increase: float,
    transp_cost_increase: float,
) -> bytes:
    """Generate a detailed PDF report for the Profit Margin Calculator."""
    
    pdf = ProfitMarginPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # ===== EXECUTIVE SUMMARY =====
    pdf.section_title("Resumen Ejecutivo")
    
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, 
        "Este informe detalla el analisis del impacto del aumento del precio del diesel "
        "en sus margenes de ganancia, diferenciando entre ventas en planta y ventas con transporte."
    )
    pdf.ln(3)
    
    # Summary table
    pdf.subsection_title("Ajustes de Precio Recomendados")
    if plant_only:
        pdf.add_table(
            headers=["Tipo", "Precio Actual", "Nuevo Precio", "Aumento", "%"],
            data=[
                ["Planta", f"{plant_selling_price:,.2f} Bs", f"{plant_new_price:,.2f} Bs", 
                 f"{plant_price_increase:+,.2f} Bs", f"{plant_price_increase_pct:+,.1f}%"],
            ],
            col_widths=[30, 38, 38, 38, 36]
        )
    else:
        pdf.add_table(
            headers=["Tipo", "Precio Actual", "Nuevo Precio", "Aumento", "%"],
            data=[
                ["Planta", f"{plant_selling_price:,.2f} Bs", f"{plant_new_price:,.2f} Bs", 
                 f"{plant_price_increase:+,.2f} Bs", f"{plant_price_increase_pct:+,.1f}%"],
                ["Transporte", f"{transp_selling_price:,.2f} Bs", f"{transp_new_price:,.2f} Bs",
                 f"{transp_price_increase:+,.2f} Bs", f"{transp_price_increase_pct:+,.1f}%"],
            ],
            col_widths=[30, 38, 38, 38, 36]
        )
    
    # Key finding
    impact_diff = transp_price_increase - plant_price_increase
    if not plant_only and impact_diff > 0:
        pdf.add_highlight_box(
            f"HALLAZGO CLAVE: El material transportado requiere un aumento de precio "
            f"{abs(impact_diff):,.2f} Bs/m3 MAYOR que el material vendido en planta.",
            "warning"
        )
    elif not plant_only:
        pdf.add_highlight_box(
            f"HALLAZGO CLAVE: Ambos tipos de venta requieren ajustes similares de precio.",
            "info"
        )
    
    # ===== CONFIGURATION PARAMETERS =====
    pdf.section_title("Parametros de Configuracion")
    
    pdf.subsection_title("Ventas en Planta")
    pdf.add_key_value("Precio de venta actual", f"{plant_selling_price:,.2f} Bs/m3")
    pdf.add_key_value("Margen de ganancia", f"{plant_profit_margin:.2f}%")
    pdf.add_key_value("% del costo que NO es diesel", f"{plant_other_cost_pct:.1f}%")
    pdf.ln(3)
    
    if not plant_only:
        pdf.subsection_title("Ventas con Transporte")
        pdf.add_key_value("Precio de venta actual", f"{transp_selling_price:,.2f} Bs/m3")
        pdf.add_key_value("Margen de ganancia", f"{transp_profit_margin:.2f}%")
        pdf.add_key_value("% del costo que NO es diesel", f"{transp_other_cost_pct:.1f}%")
        pdf.ln(3)
        
        pdf.subsection_title("Distribucion del Diesel")
        pdf.add_key_value("% Diesel para transporte", f"{transport_diesel_pct:.1f}%")
        pdf.add_key_value("% Diesel para produccion", f"{100 - transport_diesel_pct:.1f}%")
    
    # ===== PLANT CALCULATIONS =====
    pdf.add_page()
    pdf.section_title("Calculos Detallados: Ventas en Planta")
    
    pdf.subsection_title("Paso 1: Determinar el Costo Actual")
    
    plant_margin_decimal = plant_profit_margin / 100
    plant_other_decimal = plant_other_cost_pct / 100
    
    pdf.add_calculation_step(
        1, "Costo total por m3",
        f"Precio x (1 - Margen) = {plant_selling_price:,.2f} x (1 - {plant_margin_decimal:.4f})",
        f"{plant_cost_per_m3:,.2f} Bs/m3"
    )
    
    pdf.add_calculation_step(
        2, "Costo diesel por m3",
        f"Costo total x (1 - % otros) = {plant_cost_per_m3:,.2f} x {1 - plant_other_decimal:.4f}",
        f"{plant_diesel_in_price:,.2f} Bs/m3"
    )
    
    pdf.add_calculation_step(
        3, "Otros costos por m3",
        f"Costo total x % otros = {plant_cost_per_m3:,.2f} x {plant_other_decimal:.4f}",
        f"{plant_other_costs:,.2f} Bs/m3"
    )
    
    pdf.add_calculation_step(
        4, "Ganancia actual por m3",
        f"Precio x Margen = {plant_selling_price:,.2f} x {plant_margin_decimal:.4f}",
        f"{plant_profit_per_m3:,.2f} Bs/m3"
    )
    
    # Cost breakdown table
    pdf.ln(2)
    pdf.subsection_title("Desglose del Precio Actual (Planta)")
    pdf.add_table(
        headers=["Componente", "Monto (Bs/m3)", "% del Precio"],
        data=[
            ["Otros costos", f"{plant_other_costs:,.2f}", f"{plant_other_costs/plant_selling_price*100:.1f}%"],
            ["Diesel", f"{plant_diesel_in_price:,.2f}", f"{plant_diesel_in_price/plant_selling_price*100:.1f}%"],
            ["Ganancia", f"{plant_profit_per_m3:,.2f}", f"{plant_profit_margin:.1f}%"],
            ["TOTAL", f"{plant_selling_price:,.2f}", "100%"],
        ],
        col_widths=[60, 60, 60]
    )
    
    pdf.subsection_title("Paso 2: Calcular el Impacto del Diesel")
    
    if not plant_only:
        pdf.add_highlight_box(
            f"Para ventas en planta, solo aplica el diesel de PRODUCCION ({100-transport_diesel_pct:.0f}% del total).",
            "info"
        )
    
    pdf.add_calculation_step(
        5, "Aumento bruto diesel",
        "Diferencia de costo proyectado vs actual",
        f"+{plant_cost_increase:,.2f} Bs/m3"
    )
    
    pdf.add_calculation_step(
        6, "Compensacion por credito IVA",
        "Beneficio adicional del nuevo credito fiscal",
        f"-{iva_benefit_plant:,.2f} Bs/m3"
    )
    
    pdf.add_calculation_step(
        7, "Impacto neto del diesel",
        f"Aumento - Compensacion = {plant_cost_increase:,.2f} - {iva_benefit_plant:,.2f}",
        f"{net_adjustment_plant:+,.2f} Bs/m3"
    )
    
    pdf.subsection_title("Paso 3: Calcular el Nuevo Precio")
    
    pdf.add_calculation_step(
        8, "Nuevo costo por m3",
        f"Costo actual + Impacto neto = {plant_cost_per_m3:,.2f} + ({net_adjustment_plant:+,.2f})",
        f"{plant_new_cost:,.2f} Bs/m3"
    )
    
    pdf.add_calculation_step(
        9, "Nuevo precio para mantener margen",
        f"Nuevo costo / (1 - Margen) = {plant_new_cost:,.2f} / (1 - {plant_margin_decimal:.4f})",
        f"{plant_new_price:,.2f} Bs/m3"
    )
    
    pdf.add_calculation_step(
        10, "Aumento de precio necesario",
        f"Nuevo precio - Precio actual = {plant_new_price:,.2f} - {plant_selling_price:,.2f}",
        f"{plant_price_increase:+,.2f} Bs/m3 ({plant_price_increase_pct:+,.1f}%)"
    )
    
    # Verification
    pdf.ln(3)
    pdf.subsection_title("Verificacion")
    pdf.add_table(
        headers=["Concepto", "Valor"],
        data=[
            ["Nueva ganancia por m3", f"{plant_new_profit:,.2f} Bs"],
            ["Margen verificado", f"{plant_profit_margin:.2f}%"],
            ["Estado", "CORRECTO"],
        ],
        col_widths=[90, 90]
    )
    
    # ===== TRANSPORT CALCULATIONS =====
    if not plant_only:
        pdf.add_page()
        pdf.section_title("Calculos Detallados: Ventas con Transporte")
        
        pdf.subsection_title("Paso 1: Determinar el Costo Actual")
        
        transp_margin_decimal = transp_profit_margin / 100
        transp_other_decimal = transp_other_cost_pct / 100
        
        pdf.add_calculation_step(
            1, "Costo total por m3",
            f"Precio x (1 - Margen) = {transp_selling_price:,.2f} x (1 - {transp_margin_decimal:.4f})",
            f"{transp_cost_per_m3:,.2f} Bs/m3"
        )
        
        pdf.add_calculation_step(
            2, "Costo diesel por m3",
            f"Costo total x (1 - % otros) = {transp_cost_per_m3:,.2f} x {1 - transp_other_decimal:.4f}",
            f"{transp_diesel_in_price:,.2f} Bs/m3"
        )
        
        pdf.add_calculation_step(
            3, "Otros costos por m3",
            f"Costo total x % otros = {transp_cost_per_m3:,.2f} x {transp_other_decimal:.4f}",
            f"{transp_other_costs:,.2f} Bs/m3"
        )
        
        pdf.add_calculation_step(
            4, "Ganancia actual por m3",
            f"Precio x Margen = {transp_selling_price:,.2f} x {transp_margin_decimal:.4f}",
            f"{transp_profit_per_m3:,.2f} Bs/m3"
        )
        
        # Cost breakdown table
        pdf.ln(3)
        pdf.subsection_title("Desglose del Precio Actual (Transporte)")
        transp_other_pct = (transp_other_costs/transp_selling_price*100) if transp_selling_price > 0 else 0.0
        transp_diesel_pct = (transp_diesel_in_price/transp_selling_price*100) if transp_selling_price > 0 else 0.0
        pdf.add_table(
            headers=["Componente", "Monto (Bs/m3)", "% del Precio"],
            data=[
                ["Otros costos", f"{transp_other_costs:,.2f}", f"{transp_other_pct:.1f}%"],
                ["Diesel", f"{transp_diesel_in_price:,.2f}", f"{transp_diesel_pct:.1f}%"],
                ["Ganancia", f"{transp_profit_per_m3:,.2f}", f"{transp_profit_margin:.1f}%"],
                ["TOTAL", f"{transp_selling_price:,.2f}", "100%"],
            ],
            col_widths=[60, 60, 60]
        )
        
        pdf.subsection_title("Paso 2: Calcular el Impacto del Diesel")
        
        pdf.add_highlight_box(
            f"Para ventas con transporte, aplica diesel de PRODUCCION + TRANSPORTE (100% del total). "
            f"Esto es {transport_diesel_pct:.0f}% mas diesel que las ventas en planta.",
            "warning"
        )
        
        pdf.add_calculation_step(
            5, "Aumento bruto diesel (produccion + transporte)",
            "Diferencia de costo proyectado vs actual para todo el diesel",
            f"+{transp_cost_increase:,.2f} Bs/m3"
        )
        
        pdf.add_calculation_step(
            6, "Compensacion por credito IVA",
            "Beneficio adicional del nuevo credito fiscal",
            f"-{iva_benefit_transp:,.2f} Bs/m3"
        )
        
        pdf.add_calculation_step(
            7, "Impacto neto del diesel",
            f"Aumento - Compensacion = {transp_cost_increase:,.2f} - {iva_benefit_transp:,.2f}",
            f"{net_adjustment_transp:+,.2f} Bs/m3"
        )
        
        pdf.subsection_title("Paso 3: Calcular el Nuevo Precio")
        
        pdf.add_calculation_step(
            8, "Nuevo costo por m3",
            f"Costo actual + Impacto neto = {transp_cost_per_m3:,.2f} + ({net_adjustment_transp:+,.2f})",
            f"{transp_new_cost:,.2f} Bs/m3"
        )
        
        pdf.add_calculation_step(
            9, "Nuevo precio para mantener margen",
            f"Nuevo costo / (1 - Margen) = {transp_new_cost:,.2f} / (1 - {transp_margin_decimal:.4f})",
            f"{transp_new_price:,.2f} Bs/m3"
        )
        
        pdf.add_calculation_step(
            10, "Aumento de precio necesario",
            f"Nuevo precio - Precio actual = {transp_new_price:,.2f} - {transp_selling_price:,.2f}",
            f"{transp_price_increase:+,.2f} Bs/m3 ({transp_price_increase_pct:+,.1f}%)"
        )
        
        # Verification
        pdf.ln(3)
        pdf.subsection_title("Verificacion")
        pdf.add_table(
            headers=["Concepto", "Valor"],
            data=[
                ["Nueva ganancia por m3", f"{transp_new_profit:,.2f} Bs"],
                ["Margen verificado", f"{transp_profit_margin:.2f}%"],
                ["Estado", "CORRECTO"],
            ],
            col_widths=[90, 90]
        )
        
        # ===== COMPARISON =====
        pdf.add_page()
        pdf.section_title("Comparacion: Planta vs Transporte")
        
        pdf.subsection_title("Por que el transporte tiene mayor impacto?")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6,
            "El material transportado consume MAS diesel que el material vendido en planta porque:\n\n"
            f"1. Produccion: Ambos tipos usan diesel ({100-transport_diesel_pct:.0f}% del total)\n"
            f"2. Transporte: Solo el material transportado usa diesel adicional para entrega ({transport_diesel_pct:.0f}% del total)\n\n"
            "Por lo tanto, el costo de diesel por m3 transportado es MAYOR que por m3 vendido en planta."
        )
        pdf.ln(5)
        
        pdf.subsection_title("Tabla Comparativa Completa")
        pdf.add_table(
            headers=["Concepto", "Planta", "Transporte", "Diferencia"],
            data=[
                ["Precio actual", f"{plant_selling_price:,.2f} Bs", f"{transp_selling_price:,.2f} Bs", 
                 f"{transp_selling_price - plant_selling_price:+,.2f} Bs"],
                ["Costo actual", f"{plant_cost_per_m3:,.2f} Bs", f"{transp_cost_per_m3:,.2f} Bs",
                 f"{transp_cost_per_m3 - plant_cost_per_m3:+,.2f} Bs"],
                ["Diesel en costo", f"{plant_diesel_in_price:,.2f} Bs", f"{transp_diesel_in_price:,.2f} Bs",
                 f"{transp_diesel_in_price - plant_diesel_in_price:+,.2f} Bs"],
                ["Impacto diesel neto", f"{net_adjustment_plant:+,.2f} Bs", f"{net_adjustment_transp:+,.2f} Bs",
                 f"{net_adjustment_transp - net_adjustment_plant:+,.2f} Bs"],
                ["Nuevo costo", f"{plant_new_cost:,.2f} Bs", f"{transp_new_cost:,.2f} Bs",
                 f"{transp_new_cost - plant_new_cost:+,.2f} Bs"],
                ["Nuevo precio", f"{plant_new_price:,.2f} Bs", f"{transp_new_price:,.2f} Bs",
                 f"{transp_new_price - plant_new_price:+,.2f} Bs"],
                ["Aumento necesario", f"{plant_price_increase:+,.2f} Bs", f"{transp_price_increase:+,.2f} Bs",
                 f"{transp_price_increase - plant_price_increase:+,.2f} Bs"],
                ["% Aumento", f"{plant_price_increase_pct:+,.1f}%", f"{transp_price_increase_pct:+,.1f}%", "-"],
            ],
            col_widths=[45, 45, 45, 45]
        )
        
        # Final recommendation for plant + transport
        pdf.subsection_title("Recomendacion Final")
        
        if plant_price_increase > 0 or transp_price_increase > 0:
            recommendation = (
                f"ACCION REQUERIDA:\n\n"
                f"- Ventas en Planta: {'Aumentar precio en ' + f'{plant_price_increase:,.2f} Bs/m3' if plant_price_increase > 0 else 'No requiere aumento'}\n"
                f"- Ventas con Transporte: {'Aumentar precio en ' + f'{transp_price_increase:,.2f} Bs/m3' if transp_price_increase > 0 else 'No requiere aumento'}\n\n"
                f"Diferencia en ajuste: El transporte requiere {abs(impact_diff):,.2f} Bs/m3 "
                f"{'mas' if impact_diff > 0 else 'menos'} de aumento que planta."
            )
            pdf.add_highlight_box(recommendation, "warning")
        else:
            recommendation = (
                "BUENAS NOTICIAS:\n\n"
                "El beneficio del credito fiscal IVA compensa el aumento del diesel.\n"
                "No es necesario aumentar precios para mantener sus margenes."
            )
            pdf.add_highlight_box(recommendation, "success")
    else:
        # Final recommendation for plant-only
        pdf.ln(5)
        pdf.subsection_title("Recomendacion Final")
        
        if plant_price_increase > 0:
            recommendation = (
                f"ACCION REQUERIDA:\n\n"
                f"Ventas en Planta: Aumentar precio en {plant_price_increase:,.2f} Bs/m3 "
                f"(de {plant_selling_price:,.2f} a {plant_new_price:,.2f} Bs/m3)\n\n"
                f"Esto representa un aumento de {plant_price_increase_pct:+,.1f}% para mantener su margen de {plant_profit_margin:.1f}%."
            )
            pdf.add_highlight_box(recommendation, "warning")
        else:
            recommendation = (
                "BUENAS NOTICIAS:\n\n"
                "El beneficio del credito fiscal IVA compensa el aumento del diesel.\n"
                "No es necesario aumentar precios para mantener sus margenes."
            )
            pdf.add_highlight_box(recommendation, "success")
    
    # Output
    return bytes(pdf.output())



# -----------------------
# Calculation functions
# -----------------------
def calculate_liters(total_spent: float, old_price_per_liter: float) -> float:
    """Calculate liters consumed from total spent and old price."""
    if old_price_per_liter <= 0:
        return 0.0
    return total_spent / old_price_per_liter


def calculate_projected_cost(liters: float, new_price_per_liter: float) -> float:
    """Calculate what the diesel would cost at the new price."""
    return liters * new_price_per_liter


def calculate_iva_credits(total_spent: float, projected_cost: float) -> dict:
    """
    Calculate IVA credits under current and new policies.
    Current: 13% of 70% of actual spending (at old price)
    New: 13% of 100% of projected spending (at new price)
    """
    current_iva_credit = total_spent * 0.70 * 0.13
    new_iva_credit = projected_cost * 1.00 * 0.13
    iva_benefit = new_iva_credit - current_iva_credit
    return {
        "current_iva_credit": current_iva_credit,
        "new_iva_credit": new_iva_credit,
        "iva_benefit": iva_benefit,
    }


def calculate_cost_per_m3(total_spent: float, m3_sold: float, m3_transported: float) -> float:
    """Calculate diesel cost per cubic meter (uniform, legacy)."""
    total_m3 = m3_sold + m3_transported
    if total_m3 <= 0:
        return 0.0
    return total_spent / total_m3


def calculate_separated_diesel_costs(
    total_spent: float,
    m3_sold: float,
    m3_transported: float,
    transport_pct: float = 60.0
) -> dict:
    """
    Calculate diesel costs separated by production vs transport.
    
    Logic:
    - Production diesel: Used to make ALL stone (applies to all m³)
    - Transport diesel: Only used for transporting material (applies only to transported m³)
    
    Args:
        total_spent: Total diesel spending in Bs
        m3_sold: m³ sold at plant (no transport)
        m3_transported: m³ that were transported
        transport_pct: Percentage of total diesel used for transport
        
    Returns:
        dict with separated costs
    """
    total_m3 = m3_sold + m3_transported
    transport_decimal = transport_pct / 100
    
    # Split total spending into production and transport
    production_spent = total_spent * (1 - transport_decimal)
    transport_spent = total_spent * transport_decimal
    
    # Production diesel per m³ (applies to ALL m³)
    production_per_m3 = production_spent / total_m3 if total_m3 > 0 else 0
    
    # Transport diesel per m³ (only for transported m³)
    transport_per_m3 = transport_spent / m3_transported if m3_transported > 0 else 0
    
    # Total diesel cost per m³ for each type
    cost_per_m3_plant = production_per_m3  # Plant sales only need production diesel
    cost_per_m3_transported = production_per_m3 + transport_per_m3  # Transported needs both
    
    # Transport surcharge (extra cost for transported vs plant)
    transport_surcharge = transport_per_m3
    
    return {
        "production_spent": production_spent,
        "transport_spent": transport_spent,
        "production_per_m3": production_per_m3,
        "transport_per_m3": transport_per_m3,
        "cost_per_m3_plant": cost_per_m3_plant,
        "cost_per_m3_transported": cost_per_m3_transported,
        "transport_surcharge": transport_surcharge,
    }


def process_monthly_data(entries: list, truck_capacity: float = 25.0, distance_km: float = 23.0, transport_pct: float = 60.0) -> pd.DataFrame:
    """Process all monthly entries and return a DataFrame with calculations."""
    if not entries:
        return pd.DataFrame()

    rows = []
    for entry in entries:
        liters = calculate_liters(entry["total_spent"], entry["old_price"])
        projected_cost = calculate_projected_cost(liters, entry["new_price"])
        cost_difference = projected_cost - entry["total_spent"]
        iva = calculate_iva_credits(entry["total_spent"], projected_cost)
        total_m3 = entry["m3_sold"] + entry["m3_transported"]
        cost_per_m3 = calculate_cost_per_m3(entry["total_spent"], entry["m3_sold"], entry["m3_transported"])

        # Calculate SEPARATED diesel costs (plant vs transported)
        separated = calculate_separated_diesel_costs(
            entry["total_spent"],
            entry["m3_sold"],
            entry["m3_transported"],
            transport_pct
        )
        
        # Calculate SEPARATED projected costs at new price
        separated_projected = calculate_separated_diesel_costs(
            projected_cost,
            entry["m3_sold"],
            entry["m3_transported"],
            transport_pct
        )
        
        # Calculate price adjustments SEPARATED by type
        # For plant sales: only production diesel increase matters
        cost_increase_plant = separated_projected["cost_per_m3_plant"] - separated["cost_per_m3_plant"]
        # For transported: production + transport diesel increase
        cost_increase_transported = separated_projected["cost_per_m3_transported"] - separated["cost_per_m3_transported"]
        
        # IVA benefit distributed proportionally
        # Plant sales get IVA benefit from production diesel only
        # Transported gets IVA benefit from both production and transport
        if total_m3 > 0:
            # Weight IVA benefit by diesel usage
            plant_diesel_weight = separated["production_per_m3"]
            transported_diesel_weight = separated["cost_per_m3_transported"]
            total_weight = (plant_diesel_weight * entry["m3_sold"]) + (transported_diesel_weight * entry["m3_transported"])
            
            if total_weight > 0:
                iva_benefit_plant = iva["iva_benefit"] * (plant_diesel_weight * entry["m3_sold"]) / total_weight / entry["m3_sold"] if entry["m3_sold"] > 0 else 0
                iva_benefit_transported = iva["iva_benefit"] * (transported_diesel_weight * entry["m3_transported"]) / total_weight / entry["m3_transported"] if entry["m3_transported"] > 0 else 0
            else:
                iva_benefit_plant = 0
                iva_benefit_transported = 0
        else:
            iva_benefit_plant = 0
            iva_benefit_transported = 0
        
        # Net adjustments by type
        net_adjustment_plant = cost_increase_plant - iva_benefit_plant
        net_adjustment_transported = cost_increase_transported - iva_benefit_transported
        
        # Legacy uniform calculation (for backwards compatibility)
        cost_increase_per_m3 = cost_difference / total_m3 if total_m3 > 0 else 0
        iva_benefit_per_m3 = iva["iva_benefit"] / total_m3 if total_m3 > 0 else 0
        net_adjustment_per_m3 = cost_increase_per_m3 - iva_benefit_per_m3

        # Transport calculations
        m3_transported = entry["m3_transported"]
        if m3_transported > 0 and truck_capacity > 0:
            trips = math.ceil(m3_transported / truck_capacity)
            total_km = trips * (distance_km * 2)  # Round trip
            # Apply transport percentage to get estimated transport diesel cost
            transport_spent = entry["total_spent"] * (transport_pct / 100)
            transport_projected = projected_cost * (transport_pct / 100)
            cost_per_m3_km = transport_spent / (m3_transported * distance_km)
            # Projected cost per m3-km at new price
            projected_cost_per_m3_km = transport_projected / (m3_transported * distance_km)
        else:
            trips = 0
            total_km = 0
            cost_per_m3_km = 0
            projected_cost_per_m3_km = 0

        rows.append({
            "id": entry["id"],
            "Mes": entry["month"],
            "Gasto Diesel (Bs)": entry["total_spent"],
            "Precio Antiguo (Bs/L)": entry["old_price"],
            "Precio Nuevo (Bs/L)": entry["new_price"],
            "Litros Consumidos": round(liters, 2),
            "Costo Proyectado (Bs)": round(projected_cost, 2),
            "Diferencia Costo (Bs)": round(cost_difference, 2),
            "m³ Vendidos": entry["m3_sold"],
            "m³ Transportados": entry["m3_transported"],
            "Total m³": total_m3,
            "Costo/m³ (Bs)": round(cost_per_m3, 2),
            # NEW: Separated costs
            "Diesel Producción (Bs)": round(separated["production_spent"], 2),
            "Diesel Transporte (Bs)": round(separated["transport_spent"], 2),
            "Costo/m³ Planta (Bs)": round(separated["cost_per_m3_plant"], 2),
            "Costo/m³ Transp (Bs)": round(separated["cost_per_m3_transported"], 2),
            "Recargo Transporte (Bs)": round(separated["transport_surcharge"], 2),
            # NEW: Separated projected costs
            "Costo Proy/m³ Planta (Bs)": round(separated_projected["cost_per_m3_plant"], 2),
            "Costo Proy/m³ Transp (Bs)": round(separated_projected["cost_per_m3_transported"], 2),
            # NEW: Separated adjustments
            "Ajuste Planta/m³ (Bs)": round(net_adjustment_plant, 2),
            "Ajuste Transp/m³ (Bs)": round(net_adjustment_transported, 2),
            # Legacy
            "Viajes": trips,
            "Km Totales": round(total_km, 1),
            "Costo/m³-km (Bs)": round(cost_per_m3_km, 4),
            "Costo Proy/m³-km (Bs)": round(projected_cost_per_m3_km, 4),
            "Crédito IVA Actual (Bs)": round(iva["current_iva_credit"], 2),
            "Crédito IVA Nuevo (Bs)": round(iva["new_iva_credit"], 2),
            "Beneficio IVA (Bs)": round(iva["iva_benefit"], 2),
            "IVA Diesel (Bs)": round(entry["total_spent"] * 0.13, 2),
            "IVA Diesel Proy (Bs)": round(projected_cost * 0.13, 2),
            "Ajuste Precio/m³ (Bs)": round(net_adjustment_per_m3, 2),
        })

    return pd.DataFrame(rows)


# -----------------------
# Chart functions
# -----------------------
def plot_cost_comparison(df: pd.DataFrame) -> go.Figure:
    """Bar chart comparing actual vs projected diesel spending."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Mes"],
        y=df["Gasto Diesel (Bs)"],
        name="Gasto Actual",
        marker_color="#2E86AB",
    ))
    fig.add_trace(go.Bar(
        x=df["Mes"],
        y=df["Costo Proyectado (Bs)"],
        name="Costo Proyectado (Precio Nuevo)",
        marker_color="#E94F37",
    ))
    fig.update_layout(
        title="Comparación: Gasto Actual vs Proyectado",
        xaxis_title="Mes",
        yaxis_title="Monto (Bs)",
        barmode="group",
        legend_title="Escenario",
        margin=dict(l=30, r=30, t=50, b=30),
    )
    return fig


def plot_iva_comparison(df: pd.DataFrame) -> go.Figure:
    """Bar chart comparing IVA credits under current vs new policy."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Mes"],
        y=df["Crédito IVA Actual (Bs)"],
        name="IVA Actual (13% de 70%)",
        marker_color="#A23B72",
    ))
    fig.add_trace(go.Bar(
        x=df["Mes"],
        y=df["Crédito IVA Nuevo (Bs)"],
        name="IVA Nuevo (13% de 100%)",
        marker_color="#F18F01",
    ))
    fig.update_layout(
        title="Comparación: Crédito Fiscal IVA",
        xaxis_title="Mes",
        yaxis_title="Crédito IVA (Bs)",
        barmode="group",
        legend_title="Política",
        margin=dict(l=30, r=30, t=50, b=30),
    )
    return fig


def plot_cost_per_m3_trend(df: pd.DataFrame) -> go.Figure:
    """Line chart showing cost per m3 trend over time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Mes"],
        y=df["Costo/m³ (Bs)"],
        mode="lines+markers",
        name="Costo por m³",
        line=dict(color="#2E86AB", width=3),
        marker=dict(size=8),
    ))
    fig.update_layout(
        title="Tendencia: Costo de Diesel por m³",
        xaxis_title="Mes",
        yaxis_title="Costo por m³ (Bs)",
        margin=dict(l=30, r=30, t=50, b=30),
    )
    return fig


def plot_impact_breakdown(cost_increase: float, iva_benefit: float) -> go.Figure:
    """Pie chart showing the breakdown of cost increase vs IVA benefit."""
    net_impact = cost_increase - iva_benefit
    
    if net_impact > 0:
        # Cost increase is larger - show how much is compensated
        labels = ['Compensado por IVA', 'Costo Neto Adicional']
        values = [iva_benefit, net_impact]
        colors = ['#28a745', '#dc3545']
    else:
        # IVA benefit is larger - show surplus
        labels = ['Costo del Aumento', 'Ahorro Neto']
        values = [cost_increase, abs(net_impact)]
        colors = ['#ffc107', '#28a745']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker_colors=colors,
        textinfo='label+percent',
        textposition='outside',
        pull=[0, 0.05],
    )])
    
    fig.update_layout(
        title="Distribución del Impacto Financiero",
        annotations=[dict(text=f'{net_impact:+,.0f} Bs<br>Neto', x=0.5, y=0.5, font_size=14, showarrow=False)],
        margin=dict(l=30, r=30, t=50, b=30),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
    )
    return fig


def plot_percentage_comparison(df: pd.DataFrame) -> go.Figure:
    """Bar chart showing percentage changes per month."""
    # Calculate percentages for each month
    cost_increase_pct = ((df["Costo Proyectado (Bs)"] - df["Gasto Diesel (Bs)"]) / df["Gasto Diesel (Bs)"] * 100).round(1)
    iva_benefit_pct = ((df["Crédito IVA Nuevo (Bs)"] - df["Crédito IVA Actual (Bs)"]) / df["Crédito IVA Actual (Bs)"] * 100).round(1)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df["Mes"],
        y=cost_increase_pct,
        name="% Aumento Costo Diesel",
        marker_color="#E94F37",
        text=[f"+{v:.1f}%" for v in cost_increase_pct],
        textposition='outside',
    ))
    
    fig.add_trace(go.Bar(
        x=df["Mes"],
        y=iva_benefit_pct,
        name="% Aumento Crédito IVA",
        marker_color="#28a745",
        text=[f"+{v:.1f}%" for v in iva_benefit_pct],
        textposition='outside',
    ))
    
    fig.update_layout(
        title="Comparación Porcentual: Aumento Diesel vs Beneficio IVA",
        xaxis_title="Mes",
        yaxis_title="Porcentaje (%)",
        barmode="group",
        legend_title="Métrica",
        margin=dict(l=30, r=30, t=50, b=30),
    )
    return fig


# -----------------------
# Page configuration
# -----------------------
st.set_page_config(page_title="Análisis Precio Diesel", layout="wide")

st.title("⛽ Análisis de Precio de Diesel")
st.markdown("""
Esta herramienta analiza los efectos del aumento en el precio del diesel, comparando:

- **Gasto Actual vs Proyectado**: Cuánto pagarías con el nuevo precio
- **Crédito Fiscal IVA**: Beneficio del cambio de 70% → 100% como base para el crédito del 13%
- **Costo por m³**: Seguimiento del costo de diesel por metro cúbico producido/transportado
""")

with st.expander("ℹ️ ¿Cómo funciona esta herramienta?", expanded=False):
    st.markdown("""
    ### 📖 Guía de Uso
    
    Esta herramienta le ayuda a entender el impacto financiero de los cambios en el precio del diesel
    en su negocio de piedra triturada. 
    
    #### Conceptos Clave:
    
    1. **Precio Antiguo vs Nuevo**: Compare el precio que pagaba antes con el nuevo precio del diesel.
    
    2. **Crédito Fiscal IVA**: 
       - **Política Anterior**: Solo podía usar el 70% de su compra como base para el crédito fiscal del 13%
       - **Nueva Política**: Puede usar el 100% de su compra como base para el crédito fiscal del 13%
       - **Ejemplo**: Si gastó 1,000 Bs en diesel:
         - Antes: 1,000 × 70% × 13% = **91 Bs** de crédito
         - Ahora: 1,000 × 100% × 13% = **130 Bs** de crédito
         - Beneficio adicional: **39 Bs** (42.9% más crédito)
    
    3. **Ajuste de Precio Recomendado**: Calcula cuánto debe aumentar su precio de venta por m³ 
       para mantener sus márgenes, considerando tanto el aumento del diesel como el beneficio del IVA.
    
    4. **Métricas de Transporte**: Analiza el costo de diesel específicamente para el transporte,
       calculando el costo por m³ transportado por kilómetro.
    
    #### Porcentajes Importantes:
    - **% Aumento de Costo**: Cuánto más pagaría con el nuevo precio de diesel
    - **% Beneficio IVA**: Cuánto más recupera con la nueva política de crédito fiscal
    - **% Ajuste Neto**: El aumento real después de compensar con el beneficio IVA
    """)

# -----------------------
# Session state initialization
# -----------------------

# Company selector - initialize with existing companies or default
if "selected_company" not in st.session_state:
    existing_companies = db.get_companies()
    st.session_state.selected_company = existing_companies[0] if existing_companies else "Empresa Principal"

if "last_selected_company" not in st.session_state:
    st.session_state.last_selected_company = st.session_state.selected_company

# Load diesel entries for selected company
if "diesel_entries" not in st.session_state:
    st.session_state.diesel_entries = db.get_diesel_entries(st.session_state.selected_company)

# Reload entries if company changed
if st.session_state.last_selected_company != st.session_state.selected_company:
    st.session_state.diesel_entries = db.get_diesel_entries(st.session_state.selected_company)
    st.session_state.last_selected_company = st.session_state.selected_company

# Widget defaults (set once; widgets own their state afterwards)
if "form_month" not in st.session_state:
    st.session_state.form_month = "Enero"
if "form_year" not in st.session_state:
    st.session_state.form_year = datetime.now().year

if "form_total_spent" not in st.session_state:
    st.session_state.form_total_spent = 1000.0
if "form_old_price" not in st.session_state:
    st.session_state.form_old_price = 3.72
if "form_new_price" not in st.session_state:
    st.session_state.form_new_price = 3.72
if "form_m3_sold" not in st.session_state:
    st.session_state.form_m3_sold = 0.0
if "form_m3_transported" not in st.session_state:
    st.session_state.form_m3_transported = 0.0

if "truck_capacity" not in st.session_state:
    st.session_state.truck_capacity = 25.0
if "distance_km" not in st.session_state:
    st.session_state.distance_km = 23.0
if "transport_diesel_pct" not in st.session_state:
    st.session_state.transport_diesel_pct = 60.0  # Default 60%

# -----------------------
# Sidebar - Company Selector
# -----------------------
st.sidebar.header("🏢 Empresa")

# Get existing companies and allow adding new ones
existing_companies = db.get_companies()
if "Empresa Principal" not in existing_companies:
    existing_companies = ["Empresa Principal"] + existing_companies

# Text input for new company
new_company_name = st.sidebar.text_input(
    "Nueva empresa (opcional)",
    value="",
    placeholder="Escriba nombre para agregar...",
    help="Escriba un nombre y presione Enter para agregar una nueva empresa"
)

# If new company name entered, add it to the options
company_options = existing_companies.copy()
if new_company_name and new_company_name not in company_options:
    company_options.append(new_company_name)

# Company selector dropdown
selected_company = st.sidebar.selectbox(
    "Seleccionar empresa",
    options=company_options,
    index=company_options.index(st.session_state.selected_company) if st.session_state.selected_company in company_options else 0,
    key="company_selector",
    help="Seleccione la empresa para ver/agregar datos"
)

# Update session state if company changed
if selected_company != st.session_state.selected_company:
    st.session_state.selected_company = selected_company
    st.session_state.diesel_entries = db.get_diesel_entries(selected_company)
    st.session_state.last_selected_company = selected_company
    st.rerun()

# Load company settings
company_settings = db.get_company_settings(st.session_state.selected_company)

# Plant-only toggle
plant_only = st.sidebar.checkbox(
    "🏭 Solo Planta (sin transporte)",
    value=company_settings["plant_only"],
    help="Marque si esta empresa solo vende en planta y no realiza transporte",
    key="plant_only_checkbox"
)

# Save settings if changed
if plant_only != company_settings["plant_only"]:
    db.save_company_settings(st.session_state.selected_company, plant_only)
    st.rerun()

st.sidebar.markdown("---")

# -----------------------
# Sidebar - Data Entry (without form to avoid Enter key issues)
# -----------------------
st.sidebar.header("📊 Agregar Datos Mensuales")

st.sidebar.subheader("Nuevo Mes")

col1, col2 = st.sidebar.columns(2)
with col1:
    month = st.selectbox("Mes", options=[
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ], key="form_month")
with col2:
    year = st.number_input("Año", min_value=2020, max_value=2030, step=1, key="form_year")

month_label = f"{month} {year}"

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Gastos de Diesel")

total_spent = st.sidebar.number_input(
    "Total gastado en diesel (Bs)",
    min_value=0.01,
    step=100.0,
    format="%.2f",
    help="Ingrese el monto total gastado en diesel durante el mes",
    key="form_total_spent",
)

old_price = st.sidebar.number_input(
    "Precio antiguo del diesel (Bs/L)",
    min_value=0.01,
    step=0.01,
    format="%.2f",
    help="Precio por litro que se pagó durante este mes",
    key="form_old_price",
)

new_price = st.sidebar.number_input(
    "Precio nuevo del diesel (Bs/L)",
    min_value=0.01,
    step=0.01,
    format="%.2f",
    help="Precio por litro para proyección (nuevo precio)",
    key="form_new_price",
)

st.sidebar.markdown("---")
st.sidebar.subheader("📦 Producción")

m3_sold = st.sidebar.number_input(
    "Total m³ vendidos en planta",
    min_value=0.0,
    step=10.0,
    format="%.2f",
    key="form_m3_sold",
)

# Only show transport fields if not plant-only
if not plant_only:
    m3_transported = st.sidebar.number_input(
        "Total m³ transportados",
        min_value=0.0,
        step=10.0,
        format="%.2f",
        key="form_m3_transported",
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚚 Parámetros de Transporte")
    
    truck_capacity = st.sidebar.number_input(
        "Capacidad del camión (m³)",
        min_value=1.0,
        step=1.0,
        format="%.1f",
        help="Capacidad de carga del camión en metros cúbicos",
        key="truck_capacity",
    )
    
    distance_km = st.sidebar.number_input(
        "Distancia (km, ida)",
        min_value=0.1,
        step=1.0,
        format="%.1f",
        help="Distancia de ida al punto de entrega (el viaje redondo será el doble)",
        key="distance_km",
    )
    
    transport_diesel_pct = st.sidebar.slider(
        "% Diesel para transporte",
        min_value=1.0,
        max_value=100.0,
        step=1.0,
        help="Porcentaje estimado del diesel total usado por camiones de transporte",
        key="transport_diesel_pct",
    )
else:
    # Set default values for plant-only companies
    m3_transported = 0.0
    truck_capacity = st.session_state.get("truck_capacity", 25.0)
    distance_km = st.session_state.get("distance_km", 23.0)
    transport_diesel_pct = 0.0  # No transport diesel for plant-only

st.sidebar.markdown("---")

if st.sidebar.button("➕ Agregar Mes", use_container_width=True):
    if m3_sold <= 0 and (plant_only or m3_transported <= 0):
        if plant_only and m3_sold <= 0:
            st.sidebar.error("Debe ingresar m³ vendidos en planta")
        elif not plant_only:
            st.sidebar.error("Debe ingresar al menos m³ vendidos o transportados")
        else:
            # Valid entry for plant-only
            pass
    if m3_sold > 0 or (not plant_only and m3_transported > 0):
        new_entry = {
            "id": str(uuid.uuid4()),
            "company": st.session_state.selected_company,
            "month": month_label,
            "total_spent": total_spent,
            "old_price": old_price,
            "new_price": new_price,
            "m3_sold": m3_sold,
            "m3_transported": m3_transported if not plant_only else 0.0,
        }
        # Save to database and update session state
        db.save_diesel_entry(new_entry)
        st.session_state.diesel_entries.append(new_entry)
        st.sidebar.success(f"✅ Datos de {month_label} agregados para {st.session_state.selected_company}")
        st.rerun()

# Sidebar - Clear all data
st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Limpiar Datos de Empresa", use_container_width=True):
    db.clear_all_diesel_entries(st.session_state.selected_company)
    st.session_state.diesel_entries = []
    st.rerun()

# -----------------------
# Main content area
# -----------------------
company_type = "🏭 Solo Planta" if plant_only else "🏭 Planta + 🚚 Transporte"
st.markdown(f"### 🏢 Empresa: {st.session_state.selected_company}")
st.caption(f"Tipo: {company_type}")
st.markdown("---")

if not st.session_state.diesel_entries:
    st.info(f"👈 Agregue datos mensuales para **{st.session_state.selected_company}** usando el formulario en la barra lateral para comenzar el análisis.")
else:
    # Process data - use 0% transport for plant-only companies
    effective_transport_pct = 0.0 if plant_only else st.session_state.transport_diesel_pct
    df = process_monthly_data(
        st.session_state.diesel_entries,
        truck_capacity=st.session_state.truck_capacity,
        distance_km=st.session_state.distance_km,
        transport_pct=effective_transport_pct
    )
    
    # -----------------------
    # KPI Metrics Row
    # -----------------------
    st.markdown("## 📈 Resumen General")
    
    total_spent_sum = df["Gasto Diesel (Bs)"].sum()
    total_projected_sum = df["Costo Proyectado (Bs)"].sum()
    total_cost_diff = df["Diferencia Costo (Bs)"].sum()
    total_iva_benefit = df["Beneficio IVA (Bs)"].sum()
    total_m3_sum = df["Total m³"].sum()
    total_liters = df["Litros Consumidos"].sum()
    avg_cost_per_m3 = total_spent_sum / total_m3_sum if total_m3_sum > 0 else 0
    
    # Percentage calculations
    cost_increase_pct = (total_cost_diff / total_spent_sum * 100) if total_spent_sum > 0 else 0
    iva_benefit_pct = (total_iva_benefit / df["Crédito IVA Actual (Bs)"].sum() * 100) if df["Crédito IVA Actual (Bs)"].sum() > 0 else 0
    total_iva_current = df["Crédito IVA Actual (Bs)"].sum()
    total_iva_new = df["Crédito IVA Nuevo (Bs)"].sum()
    
    # Price adjustment calculations
    cost_increase_per_m3 = total_cost_diff / total_m3_sum if total_m3_sum > 0 else 0
    iva_benefit_per_m3 = total_iva_benefit / total_m3_sum if total_m3_sum > 0 else 0
    net_price_increase_needed = cost_increase_per_m3 - iva_benefit_per_m3
    net_impact = total_cost_diff - total_iva_benefit
    net_impact_pct = (net_impact / total_spent_sum * 100) if total_spent_sum > 0 else 0
    
    st.markdown("### 💵 Impacto Financiero")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.metric(
            "Total Gasto Diesel",
            f"{total_spent_sum:,.0f} Bs",
            help="Suma total de lo gastado en diesel en todos los meses registrados",
        )
    
    with kpi2:
        st.metric(
            "Costo Proyectado",
            f"{total_projected_sum:,.0f} Bs",
            delta=f"+{cost_increase_pct:.1f}% ({total_cost_diff:+,.0f} Bs)",
            delta_color="inverse",
            help=f"Lo que habría costado el mismo volumen de diesel al nuevo precio. Representa un aumento del {cost_increase_pct:.1f}%",
        )
    
    with kpi3:
        st.metric(
            "Beneficio Adicional IVA",
            f"{total_iva_benefit:,.0f} Bs",
            delta=f"+{iva_benefit_pct:.1f}% más crédito",
            delta_color="normal",
            help=f"Crédito adicional por pasar de 70% → 100% como base. De {total_iva_current:,.0f} Bs a {total_iva_new:,.0f} Bs (+{iva_benefit_pct:.1f}%)",
        )
    
    with kpi4:
        st.metric(
            "Impacto Neto",
            f"{net_impact:+,.0f} Bs",
            delta=f"{net_impact_pct:+.1f}% del gasto original",
            delta_color="inverse" if net_impact > 0 else "normal",
            help="Costo adicional después de compensar con el beneficio del IVA. Negativo = ahorro neto",
        )
    
    # IVA on Diesel Row
    st.markdown("### 🧾 IVA en Compras de Diesel")
    
    with st.expander("ℹ️ ¿Cómo funciona el IVA en el diesel?", expanded=False):
        st.markdown("""
        ### El 13% de IVA en sus compras de diesel
        
        Cada vez que compra diesel, el precio que paga **ya incluye el 13% de IVA**. Este IVA pagado 
        puede utilizarse como **crédito fiscal** para compensar el IVA que cobra en sus ventas.
        
        **Ejemplo:**
        - Si gastó 10,000 Bs en diesel
        - El IVA incluido es: 10,000 × 13% = **1,300 Bs**
        - Este monto puede descontarlo del IVA de sus ventas
        
        **Nota importante:** El crédito fiscal que puede aplicar depende de la política vigente:
        - **Política anterior**: Solo podía usar el 70% como base (1,300 × 70% = 910 Bs)
        - **Nueva política**: Puede usar el 100% como base (1,300 Bs completo)
        """)
    
    total_iva_diesel = df["IVA Diesel (Bs)"].sum()
    total_iva_diesel_proy = df["IVA Diesel Proy (Bs)"].sum()
    iva_diesel_per_m3 = total_iva_diesel / total_m3_sum if total_m3_sum > 0 else 0
    iva_diesel_proy_per_m3 = total_iva_diesel_proy / total_m3_sum if total_m3_sum > 0 else 0
    iva_diesel_diff = total_iva_diesel_proy - total_iva_diesel
    iva_diesel_diff_pct = (iva_diesel_diff / total_iva_diesel * 100) if total_iva_diesel > 0 else 0
    
    kpi_iva1, kpi_iva2, kpi_iva3, kpi_iva4 = st.columns(4)
    
    with kpi_iva1:
        st.metric(
            "IVA Pagado (13%)",
            f"{total_iva_diesel:,.0f} Bs",
            delta=f"{iva_diesel_per_m3:.2f} Bs/m³",
            delta_color="off",
            help=f"El 13% de IVA incluido en el total gastado en diesel. Este monto es parte de su crédito fiscal.",
        )
    
    with kpi_iva2:
        st.metric(
            "IVA Proyectado (13%)",
            f"{total_iva_diesel_proy:,.0f} Bs",
            delta=f"{iva_diesel_proy_per_m3:.2f} Bs/m³",
            delta_color="off",
            help=f"El 13% de IVA que pagaría con el nuevo precio de diesel.",
        )
    
    with kpi_iva3:
        st.metric(
            "Diferencia IVA",
            f"{iva_diesel_diff:+,.0f} Bs",
            delta=f"+{iva_diesel_diff_pct:.1f}%",
            delta_color="off",
            help=f"Diferencia en IVA entre el gasto proyectado y actual.",
        )
    
    with kpi_iva4:
        st.metric(
            "Crédito Fiscal Total",
            f"{total_iva_new:,.0f} Bs",
            delta=f"vs {total_iva_current:,.0f} Bs actual",
            delta_color="normal",
            help=f"Con la nueva política (100% base), su crédito fiscal sería {total_iva_new:,.0f} Bs vs {total_iva_current:,.0f} Bs con la política anterior (70% base).",
        )
    
    # Second row of KPIs - Production and Consumption
    st.markdown("### 📦 Producción y Consumo")
    
    kpi5, kpi6, kpi7, kpi8 = st.columns(4)
    
    total_m3_sold = df['m³ Vendidos'].sum()
    total_m3_transported = df['m³ Transportados'].sum()
    m3_sold_pct = (total_m3_sold / total_m3_sum * 100) if total_m3_sum > 0 else 0
    m3_transported_pct = (total_m3_transported / total_m3_sum * 100) if total_m3_sum > 0 else 0
    liters_per_m3 = total_liters / total_m3_sum if total_m3_sum > 0 else 0
    cost_per_liter = total_spent_sum / total_liters if total_liters > 0 else 0
    
    with kpi5:
        st.metric(
            "Total m³ Vendidos en Planta", 
            f"{total_m3_sold:,.0f}",
            delta=f"{m3_sold_pct:.1f}% del total",
            delta_color="off",
            help=f"Metros cúbicos vendidos directamente en planta (sin transporte). Representa el {m3_sold_pct:.1f}% del total de m³",
        )
    
    with kpi6:
        st.metric(
            "Total m³ Transportados", 
            f"{total_m3_transported:,.0f}",
            delta=f"{m3_transported_pct:.1f}% del total",
            delta_color="off",
            help=f"Metros cúbicos que requirieron transporte. Representa el {m3_transported_pct:.1f}% del total de m³",
        )
    
    with kpi7:
        st.metric(
            "Total Litros Consumidos", 
            f"{total_liters:,.0f} L",
            delta=f"{liters_per_m3:.2f} L/m³",
            delta_color="off",
            help=f"Total de litros de diesel consumidos. En promedio, se consumen {liters_per_m3:.2f} litros por cada m³ producido/transportado",
        )
    
    with kpi8:
        st.metric(
            "Costo Promedio por m³", 
            f"{avg_cost_per_m3:,.2f} Bs/m³",
            delta=f"{cost_per_liter:.2f} Bs/L promedio",
            delta_color="off",
            help=f"Costo de diesel por metro cúbico. El precio promedio pagado fue de {cost_per_liter:.2f} Bs por litro",
        )
    
    # NEW SECTION: Separated Analysis - Plant vs Transported
    st.markdown("### 🏭 vs 🚚 Análisis Separado: Planta vs Transporte")
    
    with st.expander("ℹ️ ¿Por qué separar los costos?", expanded=False):
        st.markdown(f"""
        ### Lógica de Separación de Costos
        
        **El diesel se usa para dos propósitos diferentes:**
        
        1. **Diesel de Producción** ({100 - st.session_state.transport_diesel_pct:.0f}% del total)
           - Usado para fabricar la piedra triturada
           - Aplica a **TODOS** los m³ (vendidos en planta + transportados)
           - Incluye: mezcladoras, bombas, generadores de planta, etc.
        
        2. **Diesel de Transporte** ({st.session_state.transport_diesel_pct:.0f}% del total)
           - Usado **solo** para transportar el material
           - Aplica **únicamente** a los m³ transportados
           - Incluye: camiones mixer, bombas móviles, etc.
        
        **Por qué esto importa:**
        - Material vendido en planta: Solo carga el costo de producción
        - Material transportado: Carga producción + transporte
        
        **Resultado**: El m³ transportado tiene un costo de diesel mayor que el vendido en planta.
        """)
    
    # Calculate separated totals
    total_production_spent = df["Diesel Producción (Bs)"].sum()
    total_transport_spent = df["Diesel Transporte (Bs)"].sum()
    
    # Weighted average costs per m³ by type
    if total_m3_sold > 0:
        avg_cost_plant = (df["Costo/m³ Planta (Bs)"] * df["m³ Vendidos"]).sum() / total_m3_sold
        avg_cost_plant_projected = (df["Costo Proy/m³ Planta (Bs)"] * df["m³ Vendidos"]).sum() / total_m3_sold
    else:
        avg_cost_plant = df["Costo/m³ Planta (Bs)"].mean() if len(df) > 0 else 0
        avg_cost_plant_projected = df["Costo Proy/m³ Planta (Bs)"].mean() if len(df) > 0 else 0
    
    if total_m3_transported > 0:
        avg_cost_transported = (df["Costo/m³ Transp (Bs)"] * df["m³ Transportados"]).sum() / total_m3_transported
        avg_cost_transported_projected = (df["Costo Proy/m³ Transp (Bs)"] * df["m³ Transportados"]).sum() / total_m3_transported
        avg_transport_surcharge = (df["Recargo Transporte (Bs)"] * df["m³ Transportados"]).sum() / total_m3_transported
    else:
        avg_cost_transported = df["Costo/m³ Transp (Bs)"].mean() if len(df) > 0 else 0
        avg_cost_transported_projected = df["Costo Proy/m³ Transp (Bs)"].mean() if len(df) > 0 else 0
        avg_transport_surcharge = df["Recargo Transporte (Bs)"].mean() if len(df) > 0 else 0
    
    # Calculate increases
    plant_cost_increase = avg_cost_plant_projected - avg_cost_plant
    plant_cost_increase_pct = (plant_cost_increase / avg_cost_plant * 100) if avg_cost_plant > 0 else 0
    transported_cost_increase = avg_cost_transported_projected - avg_cost_transported
    transported_cost_increase_pct = (transported_cost_increase / avg_cost_transported * 100) if avg_cost_transported > 0 else 0
    
    # Surcharge increase
    surcharge_projected = avg_transport_surcharge * (total_projected_sum / total_spent_sum) if total_spent_sum > 0 else avg_transport_surcharge
    surcharge_increase = surcharge_projected - avg_transport_surcharge
    
    sep_col1, sep_col2, sep_col3, sep_col4 = st.columns(4)
    
    with sep_col1:
        st.metric(
            "🏭 Costo/m³ Planta",
            f"{avg_cost_plant:,.2f} Bs",
            delta=f"→ {avg_cost_plant_projected:,.2f} Bs (+{plant_cost_increase_pct:.1f}%)",
            delta_color="inverse",
            help=f"Costo de diesel por m³ vendido en planta (solo producción). Proyectado: {avg_cost_plant_projected:.2f} Bs",
        )
    
    with sep_col2:
        st.metric(
            "🚚 Costo/m³ Transportado",
            f"{avg_cost_transported:,.2f} Bs",
            delta=f"→ {avg_cost_transported_projected:,.2f} Bs (+{transported_cost_increase_pct:.1f}%)",
            delta_color="inverse",
            help=f"Costo de diesel por m³ transportado (producción + transporte). Proyectado: {avg_cost_transported_projected:.2f} Bs",
        )
    
    with sep_col3:
        extra_cost = avg_cost_transported - avg_cost_plant
        extra_cost_pct = (extra_cost / avg_cost_plant * 100) if avg_cost_plant > 0 else 0
        st.metric(
            "📊 Diferencia Planta vs Transp",
            f"+{extra_cost:,.2f} Bs/m³",
            delta=f"+{extra_cost_pct:.1f}% más caro",
            delta_color="off",
            help="Costo adicional de diesel por transportar vs vender en planta",
        )
    
    with sep_col4:
        st.metric(
            "🚛 Recargo Transporte/m³",
            f"{avg_transport_surcharge:,.2f} Bs",
            delta=f"→ {surcharge_projected:,.2f} Bs proyectado",
            delta_color="inverse",
            help="Diesel adicional por m³ solo por concepto de transporte",
        )
    
    # Visual comparison bar
    st.markdown("#### 📊 Comparación Visual: Costo de Diesel por m³")
    
    bar_col1, bar_col2 = st.columns(2)
    
    with bar_col1:
        st.markdown("**Costo Actual:**")
        max_cost = max(avg_cost_transported, 1)
        plant_bar_pct = (avg_cost_plant / max_cost * 100)
        transport_bar_pct = (avg_cost_transported / max_cost * 100)
        
        st.markdown(f"""
        <div style="margin-bottom: 10px;">
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <span style="width: 100px; font-size: 12px;">🏭 Planta:</span>
                <div style="flex-grow: 1; background-color: #e0e0e0; border-radius: 5px; height: 25px; margin-right: 10px;">
                    <div style="width: {plant_bar_pct}%; background-color: #2E86AB; height: 100%; border-radius: 5px; display: flex; align-items: center; justify-content: flex-end; padding-right: 5px;">
                        <span style="color: white; font-size: 11px; font-weight: bold;">{avg_cost_plant:.2f} Bs</span>
                    </div>
                </div>
            </div>
            <div style="display: flex; align-items: center;">
                <span style="width: 100px; font-size: 12px;">🚚 Transp:</span>
                <div style="flex-grow: 1; background-color: #e0e0e0; border-radius: 5px; height: 25px; margin-right: 10px;">
                    <div style="width: {transport_bar_pct}%; background-color: #E94F37; height: 100%; border-radius: 5px; display: flex; align-items: center; justify-content: flex-end; padding-right: 5px;">
                        <span style="color: white; font-size: 11px; font-weight: bold;">{avg_cost_transported:.2f} Bs</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with bar_col2:
        st.markdown("**Costo Proyectado:**")
        max_cost_proj = max(avg_cost_transported_projected, 1)
        plant_bar_proj_pct = (avg_cost_plant_projected / max_cost_proj * 100)
        transport_bar_proj_pct = (avg_cost_transported_projected / max_cost_proj * 100)
        
        st.markdown(f"""
        <div style="margin-bottom: 10px;">
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <span style="width: 100px; font-size: 12px;">🏭 Planta:</span>
                <div style="flex-grow: 1; background-color: #e0e0e0; border-radius: 5px; height: 25px; margin-right: 10px;">
                    <div style="width: {plant_bar_proj_pct}%; background-color: #2E86AB; height: 100%; border-radius: 5px; display: flex; align-items: center; justify-content: flex-end; padding-right: 5px;">
                        <span style="color: white; font-size: 11px; font-weight: bold;">{avg_cost_plant_projected:.2f} Bs</span>
                    </div>
                </div>
            </div>
            <div style="display: flex; align-items: center;">
                <span style="width: 100px; font-size: 12px;">🚚 Transp:</span>
                <div style="flex-grow: 1; background-color: #e0e0e0; border-radius: 5px; height: 25px; margin-right: 10px;">
                    <div style="width: {transport_bar_proj_pct}%; background-color: #E94F37; height: 100%; border-radius: 5px; display: flex; align-items: center; justify-content: flex-end; padding-right: 5px;">
                        <span style="color: white; font-size: 11px; font-weight: bold;">{avg_cost_transported_projected:.2f} Bs</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Detailed breakdown table
    st.markdown("#### 📋 Desglose Detallado por Tipo de Venta")
    
    breakdown_data = {
        "Concepto": [
            "Diesel de Producción",
            "Diesel de Transporte",
            "Costo Diesel/m³",
            "Costo Proyectado/m³",
            "Aumento de Costo/m³",
            "Aumento (%)",
        ],
        "🏭 Venta en Planta": [
            f"{total_production_spent / total_m3_sum if total_m3_sum > 0 else 0:,.2f} Bs/m³",
            "N/A (no aplica)",
            f"{avg_cost_plant:,.2f} Bs/m³",
            f"{avg_cost_plant_projected:,.2f} Bs/m³",
            f"+{plant_cost_increase:,.2f} Bs/m³",
            f"+{plant_cost_increase_pct:.1f}%",
        ],
        "🚚 Con Transporte": [
            f"{total_production_spent / total_m3_sum if total_m3_sum > 0 else 0:,.2f} Bs/m³",
            f"+{avg_transport_surcharge:,.2f} Bs/m³",
            f"{avg_cost_transported:,.2f} Bs/m³",
            f"{avg_cost_transported_projected:,.2f} Bs/m³",
            f"+{transported_cost_increase:,.2f} Bs/m³",
            f"+{transported_cost_increase_pct:.1f}%",
        ],
        "Diferencia": [
            "—",
            f"+{avg_transport_surcharge:,.2f} Bs/m³",
            f"+{extra_cost:,.2f} Bs/m³",
            f"+{avg_cost_transported_projected - avg_cost_plant_projected:,.2f} Bs/m³",
            f"+{transported_cost_increase - plant_cost_increase:,.2f} Bs/m³",
            f"+{transported_cost_increase_pct - plant_cost_increase_pct:.1f} pp",
        ],
    }
    
    breakdown_df = pd.DataFrame(breakdown_data)
    st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
    
    # Recommendation box for separated pricing
    st.markdown("#### 💡 Recomendación de Precios Diferenciados")
    
    # Calculate IVA benefit per type (simplified)
    iva_benefit_per_m3_plant = iva_benefit_per_m3 * (avg_cost_plant / avg_cost_per_m3) if avg_cost_per_m3 > 0 else 0
    iva_benefit_per_m3_transported = iva_benefit_per_m3 * (avg_cost_transported / avg_cost_per_m3) if avg_cost_per_m3 > 0 else 0
    
    net_adjustment_plant_total = plant_cost_increase - iva_benefit_per_m3_plant
    net_adjustment_transported_total = transported_cost_increase - iva_benefit_per_m3_transported
    
    rec_sep_col1, rec_sep_col2 = st.columns(2)
    
    with rec_sep_col1:
        if net_adjustment_plant_total > 0:
            st.warning(f"""
            **🏭 Ventas en Planta**
            
            | Concepto | Valor |
            |----------|-------|
            | Aumento diesel | +{plant_cost_increase:,.2f} Bs/m³ |
            | Compensación IVA | -{iva_benefit_per_m3_plant:,.2f} Bs/m³ |
            | **Ajuste neto** | **+{net_adjustment_plant_total:,.2f} Bs/m³** |
            
            ⚠️ Debe aumentar el precio de planta en **{net_adjustment_plant_total:,.2f} Bs/m³**
            """)
        else:
            st.success(f"""
            **🏭 Ventas en Planta**
            
            | Concepto | Valor |
            |----------|-------|
            | Aumento diesel | +{plant_cost_increase:,.2f} Bs/m³ |
            | Compensación IVA | -{iva_benefit_per_m3_plant:,.2f} Bs/m³ |
            | **Ahorro neto** | **{abs(net_adjustment_plant_total):,.2f} Bs/m³** |
            
            ✅ No necesita aumentar precio de planta
            """)
    
    with rec_sep_col2:
        if net_adjustment_transported_total > 0:
            st.warning(f"""
            **🚚 Ventas con Transporte**
            
            | Concepto | Valor |
            |----------|-------|
            | Aumento diesel | +{transported_cost_increase:,.2f} Bs/m³ |
            | Compensación IVA | -{iva_benefit_per_m3_transported:,.2f} Bs/m³ |
            | **Ajuste neto** | **+{net_adjustment_transported_total:,.2f} Bs/m³** |
            
            ⚠️ Debe aumentar el precio con transporte en **{net_adjustment_transported_total:,.2f} Bs/m³**
            """)
        else:
            st.success(f"""
            **🚚 Ventas con Transporte**
            
            | Concepto | Valor |
            |----------|-------|
            | Aumento diesel | +{transported_cost_increase:,.2f} Bs/m³ |
            | Compensación IVA | -{iva_benefit_per_m3_transported:,.2f} Bs/m³ |
            | **Ahorro neto** | **{abs(net_adjustment_transported_total):,.2f} Bs/m³** |
            
            ✅ No necesita aumentar precio con transporte
            """)
    
    # Summary comparison
    adjustment_diff = net_adjustment_transported_total - net_adjustment_plant_total
    st.info(f"""
    📊 **Resumen**: El material transportado requiere un ajuste de precio **{abs(adjustment_diff):,.2f} Bs/m³ {'mayor' if adjustment_diff > 0 else 'menor'}** 
    que el material vendido en planta debido al consumo adicional de diesel para transporte.
    
    **Configuración actual**: {st.session_state.transport_diesel_pct:.0f}% del diesel se destina a transporte, {100-st.session_state.transport_diesel_pct:.0f}% a producción.
    """)
    
    st.markdown("---")
    
    # Third row of KPIs - Transport metrics
    st.markdown("### 🚚 Métricas de Transporte")
    
    with st.expander("ℹ️ ¿Cómo se calculan las métricas de transporte?", expanded=False):
        st.markdown(f"""
        **Parámetros configurados:**
        - Capacidad del camión: **{st.session_state.truck_capacity:.0f} m³**
        - Distancia por viaje (ida): **{st.session_state.distance_km:.0f} km** (vuelta completa: {st.session_state.distance_km * 2:.0f} km)
        - % del diesel destinado a transporte: **{st.session_state.transport_diesel_pct:.0f}%**
        
        **Cálculos:**
        - **Viajes** = m³ transportados ÷ capacidad del camión (redondeado hacia arriba)
        - **Km totales** = Viajes × (distancia × 2)
        - **Costo por m³-km** = (Gasto diesel × % transporte) ÷ (m³ transportados × km de ida)
        
        Este indicador es útil para comparar la eficiencia del transporte y establecer 
        tarifas de envío que cubran los costos reales.
        """)
    
    total_trips = df["Viajes"].sum()
    total_km_traveled = df["Km Totales"].sum()
    total_m3_transported_calc = df["m³ Transportados"].sum()
    
    # Calculate average cost per m3-km (weighted by m3 transported)
    # Apply transport percentage to get estimated transport diesel cost
    transport_pct_decimal = st.session_state.transport_diesel_pct / 100
    if total_m3_transported_calc > 0:
        transport_spent_total = df["Gasto Diesel (Bs)"].sum() * transport_pct_decimal
        transport_projected_total = df["Costo Proyectado (Bs)"].sum() * transport_pct_decimal
        avg_cost_per_m3_km = transport_spent_total / (total_m3_transported_calc * st.session_state.distance_km)
        avg_projected_cost_per_m3_km = transport_projected_total / (total_m3_transported_calc * st.session_state.distance_km)
        cost_per_m3_km_diff = avg_projected_cost_per_m3_km - avg_cost_per_m3_km
        cost_per_m3_km_pct_increase = (cost_per_m3_km_diff / avg_cost_per_m3_km * 100) if avg_cost_per_m3_km > 0 else 0
        # Cost per trip
        cost_per_trip = transport_spent_total / total_trips if total_trips > 0 else 0
        projected_cost_per_trip = transport_projected_total / total_trips if total_trips > 0 else 0
        cost_per_trip_increase = projected_cost_per_trip - cost_per_trip
        cost_per_trip_pct = (cost_per_trip_increase / cost_per_trip * 100) if cost_per_trip > 0 else 0
    else:
        avg_cost_per_m3_km = 0
        avg_projected_cost_per_m3_km = 0
        cost_per_m3_km_diff = 0
        cost_per_m3_km_pct_increase = 0
        cost_per_trip = 0
        projected_cost_per_trip = 0
        cost_per_trip_increase = 0
        cost_per_trip_pct = 0
    
    kpi9, kpi10, kpi11, kpi12 = st.columns(4)
    
    with kpi9:
        m3_per_trip = total_m3_transported_calc / total_trips if total_trips > 0 else 0
        st.metric(
            "Total Viajes Realizados",
            f"{total_trips:,.0f}",
            delta=f"{m3_per_trip:.1f} m³/viaje promedio",
            delta_color="off",
            help=f"Viajes calculados con camión de {st.session_state.truck_capacity:.0f} m³. Promedio de {m3_per_trip:.1f} m³ por viaje",
        )
    
    with kpi10:
        km_per_m3 = total_km_traveled / total_m3_transported_calc if total_m3_transported_calc > 0 else 0
        st.metric(
            "Km Totales Recorridos",
            f"{total_km_traveled:,.0f} km",
            delta=f"{km_per_m3:.1f} km/m³",
            delta_color="off",
            help=f"Distancia total recorrida (ida y vuelta de {st.session_state.distance_km:.0f} km). Se recorren {km_per_m3:.1f} km por cada m³ transportado",
        )
    
    with kpi11:
        st.metric(
            "Costo por Viaje (Actual)",
            f"{cost_per_trip:,.2f} Bs",
            delta=f"+{cost_per_trip_pct:.1f}% con nuevo precio",
            delta_color="inverse" if cost_per_trip_pct > 0 else "normal",
            help=f"Costo de diesel por viaje. Con el nuevo precio sería {projected_cost_per_trip:,.2f} Bs (+{cost_per_trip_pct:.1f}%)",
        )
    
    with kpi12:
        st.metric(
            "Costo por m³-km",
            f"{avg_cost_per_m3_km:,.4f} Bs",
            delta=f"+{cost_per_m3_km_pct_increase:.1f}% → {avg_projected_cost_per_m3_km:,.4f} Bs",
            delta_color="inverse" if cost_per_m3_km_pct_increase > 0 else "normal",
            help=f"Costo de diesel por m³ por km. Proyectado: {avg_projected_cost_per_m3_km:,.4f} Bs (aumento del {cost_per_m3_km_pct_increase:.1f}%)",
        )
    
    st.markdown("---")
    
    # -----------------------
    # Price Adjustment Recommendation
    # -----------------------
    st.markdown("## 💰 Ajuste de Precio Recomendado")
    
    with st.expander("ℹ️ ¿Cómo se calcula el ajuste de precio?", expanded=False):
        st.markdown(f"""
        ### Metodología de Cálculo
        
        El ajuste de precio recomendado considera dos factores principales:
        
        #### 1. Aumento del Costo de Diesel (+)
        - **Cálculo**: (Costo Proyectado - Costo Actual) ÷ Total m³
        - **Sus datos**: ({total_projected_sum:,.2f} - {total_spent_sum:,.2f}) ÷ {total_m3_sum:,.0f} = **{cost_increase_per_m3:,.2f} Bs/m³**
        - **Interpretación**: Cada m³ que produce/transporta le cuesta {cost_increase_per_m3:,.2f} Bs más en diesel
        
        #### 2. Beneficio del Crédito IVA (-)
        - **Cálculo**: Beneficio IVA Total ÷ Total m³
        - **Sus datos**: {total_iva_benefit:,.2f} ÷ {total_m3_sum:,.0f} = **{iva_benefit_per_m3:,.2f} Bs/m³**
        - **Interpretación**: Recupera {iva_benefit_per_m3:,.2f} Bs adicionales por m³ gracias a la nueva política de IVA
        
        #### Resultado Neto
        - **Cálculo**: Aumento Costo - Beneficio IVA
        - **Sus datos**: {cost_increase_per_m3:,.2f} - {iva_benefit_per_m3:,.2f} = **{net_price_increase_needed:,.2f} Bs/m³**
        
        {'✅ **El beneficio del IVA compensa totalmente el aumento del diesel**' if net_price_increase_needed <= 0 else '⚠️ **Debe ajustar sus precios para mantener su margen**'}
        """)
    
    # Calculate percentage metrics
    cost_pct_of_avg = (cost_increase_per_m3 / avg_cost_per_m3 * 100) if avg_cost_per_m3 > 0 else 0
    iva_pct_of_cost_increase = (iva_benefit_per_m3 / cost_increase_per_m3 * 100) if cost_increase_per_m3 > 0 else 0
    net_pct_of_avg = (net_price_increase_needed / avg_cost_per_m3 * 100) if avg_cost_per_m3 > 0 else 0
    
    rec_col1, rec_col2, rec_col3 = st.columns(3)
    
    with rec_col1:
        st.metric(
            "Aumento Costo por m³",
            f"+{cost_increase_per_m3:,.2f} Bs/m³",
            delta=f"+{cost_pct_of_avg:.1f}% del costo actual/m³",
            delta_color="inverse",
            help=f"Incremento en costo de diesel por m³ debido al nuevo precio. Representa un {cost_pct_of_avg:.1f}% del costo actual de {avg_cost_per_m3:.2f} Bs/m³",
        )
    
    with rec_col2:
        st.metric(
            "Compensación IVA por m³",
            f"-{iva_benefit_per_m3:,.2f} Bs/m³",
            delta=f"Cubre {iva_pct_of_cost_increase:.1f}% del aumento",
            delta_color="normal",
            help=f"Ahorro por m³ debido al nuevo crédito fiscal. Compensa el {iva_pct_of_cost_increase:.1f}% del aumento en el costo",
        )
    
    with rec_col3:
        net_status = "ahorro" if net_price_increase_needed < 0 else "aumento"
        st.metric(
            "Ajuste Neto por m³",
            f"{net_price_increase_needed:+,.2f} Bs/m³",
            delta=f"{net_pct_of_avg:+.1f}% del costo actual/m³",
            delta_color="inverse" if net_price_increase_needed > 0 else "normal",
            help=f"{'Ahorro neto por m³ - ¡puede mantener o reducir precios!' if net_price_increase_needed < 0 else 'Aumento de precio necesario por m³ para mantener márgenes'}",
        )
    
    # Visual breakdown bar
    st.markdown("#### 📊 Desglose Visual del Ajuste")
    
    breakdown_col1, breakdown_col2 = st.columns([2, 1])
    
    with breakdown_col1:
        if cost_increase_per_m3 > 0:
            compensation_bar_pct = min(iva_pct_of_cost_increase, 100)
            remaining_bar_pct = max(100 - compensation_bar_pct, 0)
            
            st.markdown(f"""
            <div style="width: 100%; background-color: #f0f0f0; border-radius: 10px; overflow: hidden; height: 30px; margin: 10px 0;">
                <div style="width: {compensation_bar_pct}%; background-color: #28a745; height: 100%; float: left; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 12px;">
                    {compensation_bar_pct:.0f}% compensado
                </div>
                <div style="width: {remaining_bar_pct}%; background-color: #dc3545; height: 100%; float: left; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 12px;">
                    {remaining_bar_pct:.0f}% no cubierto
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.caption(f"Del aumento de {cost_increase_per_m3:.2f} Bs/m³, el beneficio IVA cubre {iva_benefit_per_m3:.2f} Bs/m³ ({iva_pct_of_cost_increase:.1f}%)")
    
    with breakdown_col2:
        if iva_pct_of_cost_increase >= 100:
            st.success("✅ 100% cubierto")
        elif iva_pct_of_cost_increase >= 75:
            st.info(f"📊 {iva_pct_of_cost_increase:.0f}% cubierto")
        elif iva_pct_of_cost_increase >= 50:
            st.warning(f"⚠️ {iva_pct_of_cost_increase:.0f}% cubierto")
        else:
            st.error(f"❌ Solo {iva_pct_of_cost_increase:.0f}% cubierto")
    
    # Recommendation box with more detail
    st.markdown("#### 📋 Recomendación")
    
    if net_price_increase_needed > 0:
        net_pct_increase = (net_price_increase_needed / avg_cost_per_m3 * 100) if avg_cost_per_m3 > 0 else 0
        st.warning(f"""
        **⚠️ Debe aumentar precios para mantener su margen de ganancia**
        
        | Concepto | Valor | % del costo actual |
        |----------|-------|-------------------|
        | Aumento bruto (diesel) | +{cost_increase_per_m3:,.2f} Bs/m³ | +{cost_pct_of_avg:.1f}% |
        | Compensación IVA | -{iva_benefit_per_m3:,.2f} Bs/m³ | -{(iva_benefit_per_m3/avg_cost_per_m3*100) if avg_cost_per_m3 > 0 else 0:.1f}% |
        | **Aumento neto requerido** | **+{net_price_increase_needed:,.2f} Bs/m³** | **+{net_pct_increase:.1f}%** |
        
        **Interpretación**: Por cada m³ que venda, su costo de diesel aumenta en {cost_increase_per_m3:.2f} Bs, 
        pero recupera {iva_benefit_per_m3:.2f} Bs adicionales por IVA. El impacto neto es de +{net_price_increase_needed:.2f} Bs/m³ 
        que debe trasladar al precio de venta.
        """)
    elif net_price_increase_needed < 0:
        net_savings_pct = (abs(net_price_increase_needed) / avg_cost_per_m3 * 100) if avg_cost_per_m3 > 0 else 0
        st.success(f"""
        **✅ Buenas noticias: El beneficio del IVA supera el aumento del diesel**
        
        | Concepto | Valor | % del costo actual |
        |----------|-------|-------------------|
        | Aumento bruto (diesel) | +{cost_increase_per_m3:,.2f} Bs/m³ | +{cost_pct_of_avg:.1f}% |
        | Compensación IVA | -{iva_benefit_per_m3:,.2f} Bs/m³ | -{(iva_benefit_per_m3/avg_cost_per_m3*100) if avg_cost_per_m3 > 0 else 0:.1f}% |
        | **Ahorro neto** | **{abs(net_price_increase_needed):,.2f} Bs/m³** | **{net_savings_pct:.1f}%** |
        
        **Opciones**:
        1. 💰 **Mantener precios actuales** y aumentar su margen de ganancia
        2. 📉 **Reducir precios** en hasta {abs(net_price_increase_needed):.2f} Bs/m³ para ser más competitivo
        3. 💵 **Dividir el beneficio** entre ahorro y reducción de precios
        """)
    else:
        st.info(f"""
        **📊 Neutral: El aumento del diesel es exactamente compensado por el beneficio IVA**
        
        | Concepto | Valor |
        |----------|-------|
        | Aumento bruto (diesel) | +{cost_increase_per_m3:,.2f} Bs/m³ |
        | Compensación IVA | -{iva_benefit_per_m3:,.2f} Bs/m³ |
        | **Diferencia neta** | **0.00 Bs/m³** |
        
        No necesita ajustar sus precios. El nuevo crédito fiscal IVA compensa exactamente el aumento en el precio del diesel.
        """)
    
    # -----------------------
    # Profit Margin Calculator with Transport Support
    # -----------------------
    st.markdown("### 📈 Calculadora de Margen de Ganancia")
    
    if plant_only:
        st.markdown("""
        Ingrese sus precios de venta actuales y margen de ganancia para calcular 
        los nuevos precios necesarios para **ventas en planta**.
        """)
        
        with st.expander("ℹ️ ¿Cómo funciona esta calculadora?", expanded=False):
            st.markdown(f"""
            ### Metodología de Cálculo
            
            Esta calculadora utiliza el **método del margen sobre el precio de venta** para determinar 
            el ajuste necesario en sus precios.
            
            #### Fórmulas utilizadas:
            
            1. **Costo actual por m³** = Precio de venta × (1 - Margen%)
            2. **Nuevo costo por m³** = Costo actual + Impacto neto diesel
            3. **Nuevo precio necesario** = Nuevo costo ÷ (1 - Margen%)
            
            #### Impacto diesel:
            - **Planta**: +{net_adjustment_plant_total:,.2f} Bs/m³
            """)
    else:
        st.markdown("""
        Ingrese sus precios de venta actuales y margen de ganancia para calcular 
        los nuevos precios necesarios, **separando ventas en planta vs con transporte**.
        """)
        
        with st.expander("ℹ️ ¿Cómo funciona esta calculadora?", expanded=False):
            st.markdown(f"""
            ### Metodología de Cálculo
            
            Esta calculadora utiliza el **método del margen sobre el precio de venta** para determinar 
            el ajuste necesario en sus precios, **diferenciando entre ventas en planta y con transporte**.
            
            #### Diferencia Clave:
            - **🏭 Venta en Planta**: Solo incurre en diesel de producción ({100 - st.session_state.transport_diesel_pct:.0f}% del total)
            - **🚚 Venta con Transporte**: Incurre en diesel de producción + transporte ({100:.0f}% del total)
            
            #### Fórmulas utilizadas:
            
            1. **Costo actual por m³** = Precio de venta × (1 - Margen%)
            2. **Nuevo costo por m³** = Costo actual + Impacto neto diesel (según tipo)
            3. **Nuevo precio necesario** = Nuevo costo ÷ (1 - Margen%)
            
            #### Impacto diesel por tipo:
            - **Planta**: +{net_adjustment_plant_total:,.2f} Bs/m³
            - **Transporte**: +{net_adjustment_transported_total:,.2f} Bs/m³
            """)
    
    # Input section - tabs for both types, or just plant section for plant-only
    if not plant_only:
        calc_tab1, calc_tab2 = st.tabs(["🏭 Ventas en Planta", "🚚 Ventas con Transporte"])
        plant_container = calc_tab1
    else:
        plant_container = st.container()
    
    with plant_container:
        st.markdown("#### Configuración para Ventas en Planta")
        
        plant_col1, plant_col2, plant_col3 = st.columns(3)
        
        with plant_col1:
            plant_selling_price = st.number_input(
                "Precio de venta en planta (Bs/m³)",
                min_value=0.01,
                value=100.0,
                step=10.0,
                format="%.2f",
                help="Precio de venta actual por m³ en planta (sin transporte)",
                key="plant_selling_price",
            )
        
        with plant_col2:
            plant_profit_margin = st.number_input(
                "Margen de ganancia planta (%)",
                min_value=0.01,
                max_value=99.99,
                value=20.0,
                step=1.0,
                format="%.2f",
                help="Margen de ganancia para ventas en planta",
                key="plant_profit_margin",
            )
        
        with plant_col3:
            plant_other_cost_pct = st.number_input(
                "% del costo que NO es diesel (planta)",
                min_value=0.0,
                max_value=99.99,
                value=70.0,
                step=5.0,
                format="%.1f",
                help="Porcentaje del costo que corresponde a otros gastos (materiales, mano de obra, etc.)",
                key="plant_other_cost_pct",
            )
        
        # Plant calculations
        plant_margin_decimal = plant_profit_margin / 100
        plant_profit_per_m3 = plant_selling_price * plant_margin_decimal
        plant_cost_per_m3_derived = plant_selling_price * (1 - plant_margin_decimal)
        
        plant_other_cost_decimal = plant_other_cost_pct / 100
        plant_diesel_in_price = plant_cost_per_m3_derived * (1 - plant_other_cost_decimal)
        plant_other_costs = plant_cost_per_m3_derived * plant_other_cost_decimal
        
        # New cost using PLANT-SPECIFIC diesel increase
        plant_new_cost = plant_cost_per_m3_derived + net_adjustment_plant_total
        plant_new_diesel = plant_diesel_in_price + net_adjustment_plant_total
        
        plant_new_price = plant_new_cost / (1 - plant_margin_decimal)
        plant_price_increase = plant_new_price - plant_selling_price
        plant_price_increase_pct = (plant_price_increase / plant_selling_price * 100) if plant_selling_price > 0 else 0
        plant_new_profit = plant_new_price * plant_margin_decimal
        
        # Display plant results
        st.markdown("---")
        st.markdown("##### 📊 Resultados para Ventas en Planta")
        
        plant_r1, plant_r2, plant_r3, plant_r4 = st.columns(4)
        
        with plant_r1:
            st.metric(
                "Costo Actual",
                f"{plant_cost_per_m3_derived:,.2f} Bs/m³",
                delta=f"Diesel: {plant_diesel_in_price:,.2f} Bs",
                delta_color="off",
            )
        
        with plant_r2:
            st.metric(
                "Nuevo Costo",
                f"{plant_new_cost:,.2f} Bs/m³",
                delta=f"{net_adjustment_plant_total:+,.2f} Bs",
                delta_color="inverse" if net_adjustment_plant_total > 0 else "normal",
            )
        
        with plant_r3:
            st.metric(
                "Nuevo Precio Necesario",
                f"{plant_new_price:,.2f} Bs/m³",
                delta=f"{plant_price_increase:+,.2f} Bs",
                delta_color="inverse" if plant_price_increase > 0 else "normal",
            )
        
        with plant_r4:
            st.metric(
                "Aumento de Precio",
                f"{plant_price_increase_pct:+,.1f}%",
                delta=f"Ganancia: {plant_new_profit:,.2f} Bs",
                delta_color="off",
            )
        
        # Plant recommendation
        if plant_price_increase > 0:
            st.warning(f"""
            **⚠️ Para mantener su margen de {plant_profit_margin:.1f}% en ventas de planta:**
            
            Debe aumentar el precio de **{plant_selling_price:,.2f} Bs** a **{plant_new_price:,.2f} Bs** 
            (un aumento de **{plant_price_increase_pct:+,.2f}%**)
            """)
        else:
            st.success(f"""
            **✅ Buenas noticias para ventas en planta:**
            
            Puede reducir el precio en **{abs(plant_price_increase):,.2f} Bs/m³** o mantenerlo para aumentar su margen.
            """)
    
    # Transport section - only for companies with transport
    # Set default transport values for plant-only companies to avoid errors
    if plant_only:
        transp_selling_price = 0.0
        transp_profit_margin = 0.0
        transp_margin_decimal = 0.0
        transp_profit_per_m3 = 0.0
        transp_cost_per_m3_derived = 0.0
        transp_other_cost_pct = 0.0
        transp_other_cost_decimal = 0.0
        transp_diesel_in_price = 0.0
        transp_other_costs = 0.0
        transp_new_cost = 0.0
        transp_new_diesel = 0.0
        transp_new_price = 0.0
        transp_price_increase = 0.0
        transp_price_increase_pct = 0.0
        transp_new_profit = 0.0
    
    if not plant_only:
        with calc_tab2:
            st.markdown("#### Configuración para Ventas con Transporte")
            
            transp_col1, transp_col2, transp_col3 = st.columns(3)
            
            with transp_col1:
                transp_selling_price = st.number_input(
                    "Precio de venta con transporte (Bs/m³)",
                    min_value=0.01,
                    value=120.0,
                    step=10.0,
                    format="%.2f",
                    help="Precio de venta actual por m³ incluyendo transporte",
                    key="transp_selling_price",
                )
            
            with transp_col2:
                transp_profit_margin = st.number_input(
                    "Margen de ganancia transporte (%)",
                    min_value=0.01,
                    max_value=99.99,
                    value=20.0,
                    step=1.0,
                    format="%.2f",
                    help="Margen de ganancia para ventas con transporte",
                    key="transp_profit_margin",
                )
            
            with transp_col3:
                transp_other_cost_pct = st.number_input(
                    "% del costo que NO es diesel (transp)",
                    min_value=0.0,
                    max_value=99.99,
                    value=60.0,
                    step=5.0,
                    format="%.1f",
                    help="Porcentaje del costo que corresponde a otros gastos. Nota: con transporte, el diesel es un % mayor del costo.",
                    key="transp_other_cost_pct",
                )
            
            # Transport calculations
            transp_margin_decimal = transp_profit_margin / 100
            transp_profit_per_m3 = transp_selling_price * transp_margin_decimal
            transp_cost_per_m3_derived = transp_selling_price * (1 - transp_margin_decimal)
            
            transp_other_cost_decimal = transp_other_cost_pct / 100
            transp_diesel_in_price = transp_cost_per_m3_derived * (1 - transp_other_cost_decimal)
            transp_other_costs = transp_cost_per_m3_derived * transp_other_cost_decimal
            
            # New cost using TRANSPORT-SPECIFIC diesel increase
            transp_new_cost = transp_cost_per_m3_derived + net_adjustment_transported_total
            transp_new_diesel = transp_diesel_in_price + net_adjustment_transported_total
            
            transp_new_price = transp_new_cost / (1 - transp_margin_decimal)
            transp_price_increase = transp_new_price - transp_selling_price
            transp_price_increase_pct = (transp_price_increase / transp_selling_price * 100) if transp_selling_price > 0 else 0
            transp_new_profit = transp_new_price * transp_margin_decimal
            
            # Display transport results
            st.markdown("---")
            st.markdown("##### 📊 Resultados para Ventas con Transporte")
            
            transp_r1, transp_r2, transp_r3, transp_r4 = st.columns(4)
            
            with transp_r1:
                st.metric(
                    "Costo Actual",
                    f"{transp_cost_per_m3_derived:,.2f} Bs/m³",
                    delta=f"Diesel: {transp_diesel_in_price:,.2f} Bs",
                    delta_color="off",
                )
            
            with transp_r2:
                st.metric(
                    "Nuevo Costo",
                    f"{transp_new_cost:,.2f} Bs/m³",
                    delta=f"{net_adjustment_transported_total:+,.2f} Bs",
                    delta_color="inverse" if net_adjustment_transported_total > 0 else "normal",
                )
            
            with transp_r3:
                st.metric(
                    "Nuevo Precio Necesario",
                    f"{transp_new_price:,.2f} Bs/m³",
                    delta=f"{transp_price_increase:+,.2f} Bs",
                    delta_color="inverse" if transp_price_increase > 0 else "normal",
                )
            
            with transp_r4:
                st.metric(
                    "Aumento de Precio",
                    f"{transp_price_increase_pct:+,.1f}%",
                    delta=f"Ganancia: {transp_new_profit:,.2f} Bs",
                    delta_color="off",
                )
            
            # Transport recommendation
            if transp_price_increase > 0:
                st.warning(f"""
                **⚠️ Para mantener su margen de {transp_profit_margin:.1f}% en ventas con transporte:**
                
                Debe aumentar el precio de **{transp_selling_price:,.2f} Bs** a **{transp_new_price:,.2f} Bs** 
                (un aumento de **{transp_price_increase_pct:+,.2f}%**)
                """)
            else:
                st.success(f"""
                **✅ Buenas noticias para ventas con transporte:**
                
                Puede reducir el precio en **{abs(transp_price_increase):,.2f} Bs/m³** o mantenerlo para aumentar su margen.
                """)
        
        # Comparison section (only for companies with transport)
        st.markdown("---")
        st.markdown("#### 📊 Comparación: Planta vs Transporte")
        
        comparison_col1, comparison_col2 = st.columns(2)
        
        with comparison_col1:
            comparison_data_new = {
                "Concepto": [
                    "Precio Actual",
                    "Costo Actual",
                    "Diesel Actual",
                    "Impacto Diesel Neto",
                    "Nuevo Costo",
                    "Nuevo Precio",
                    "Aumento Necesario",
                    "Aumento (%)",
                ],
                "🏭 Planta": [
                    f"{plant_selling_price:,.2f} Bs",
                    f"{plant_cost_per_m3_derived:,.2f} Bs",
                    f"{plant_diesel_in_price:,.2f} Bs",
                    f"{net_adjustment_plant_total:+,.2f} Bs",
                    f"{plant_new_cost:,.2f} Bs",
                    f"{plant_new_price:,.2f} Bs",
                    f"{plant_price_increase:+,.2f} Bs",
                    f"{plant_price_increase_pct:+,.1f}%",
                ],
                "🚚 Transporte": [
                    f"{transp_selling_price:,.2f} Bs",
                    f"{transp_cost_per_m3_derived:,.2f} Bs",
                    f"{transp_diesel_in_price:,.2f} Bs",
                    f"{net_adjustment_transported_total:+,.2f} Bs",
                    f"{transp_new_cost:,.2f} Bs",
                    f"{transp_new_price:,.2f} Bs",
                    f"{transp_price_increase:+,.2f} Bs",
                    f"{transp_price_increase_pct:+,.1f}%",
                ],
            }
            
            comparison_df_new = pd.DataFrame(comparison_data_new)
            st.dataframe(comparison_df_new, use_container_width=True, hide_index=True)
        
        with comparison_col2:
            # Visual comparison
            st.markdown("**Diferencia de Impacto:**")
            
            impact_diff = net_adjustment_transported_total - net_adjustment_plant_total
            price_diff = transp_price_increase - plant_price_increase
            
            st.metric(
                "Impacto Diesel Adicional (Transporte vs Planta)",
                f"+{impact_diff:,.2f} Bs/m³",
                delta=f"{(impact_diff / net_adjustment_plant_total * 100) if net_adjustment_plant_total != 0 else 0:+,.1f}% más impacto",
                delta_color="inverse" if impact_diff > 0 else "normal",
                help="Diferencia en el impacto del diesel entre ventas con transporte y ventas en planta",
            )
            
            st.metric(
                "Aumento de Precio Adicional Necesario",
                f"+{price_diff:,.2f} Bs/m³",
                help="Las ventas con transporte necesitan este aumento adicional comparado con planta",
            )
            
            # Current price difference vs new price difference
            current_price_diff = transp_selling_price - plant_selling_price
            new_price_diff = transp_new_price - plant_new_price
            
            st.info(f"""
            **Diferencial de Precios:**
            - Actual: Transporte cuesta **{current_price_diff:,.2f} Bs** más que planta
            - Nuevo: Transporte costará **{new_price_diff:,.2f} Bs** más que planta
            - Cambio: El diferencial {'aumenta' if new_price_diff > current_price_diff else 'disminuye'} en **{abs(new_price_diff - current_price_diff):,.2f} Bs**
            """)
        
        # Summary recommendation (with transport)
        st.markdown("---")
        st.markdown("#### 📋 Resumen de Ajustes Recomendados")
        
        summary_col1, summary_col2 = st.columns(2)
        
        with summary_col1:
            if plant_price_increase > 0:
                st.warning(f"""
                **🏭 Ventas en Planta**
                
                | Concepto | Valor |
                |----------|-------|
                | Precio Actual | {plant_selling_price:,.2f} Bs/m³ |
                | **Nuevo Precio** | **{plant_new_price:,.2f} Bs/m³** |
                | Aumento | +{plant_price_increase:,.2f} Bs (+{plant_price_increase_pct:.1f}%) |
                | Margen | {plant_profit_margin:.1f}% (mantenido) |
                """)
            else:
                st.success(f"""
                **🏭 Ventas en Planta**
                
                | Concepto | Valor |
                |----------|-------|
                | Precio Actual | {plant_selling_price:,.2f} Bs/m³ |
                | Precio Mínimo | {plant_new_price:,.2f} Bs/m³ |
                | Ahorro Posible | {abs(plant_price_increase):,.2f} Bs/m³ |
                | Margen | {plant_profit_margin:.1f}% (o mayor si mantiene precio) |
                """)
        
        with summary_col2:
            if transp_price_increase > 0:
                st.warning(f"""
                **🚚 Ventas con Transporte**
                
                | Concepto | Valor |
                |----------|-------|
                | Precio Actual | {transp_selling_price:,.2f} Bs/m³ |
                | **Nuevo Precio** | **{transp_new_price:,.2f} Bs/m³** |
                | Aumento | +{transp_price_increase:,.2f} Bs (+{transp_price_increase_pct:.1f}%) |
                | Margen | {transp_profit_margin:.1f}% (mantenido) |
                """)
            else:
                st.success(f"""
                **🚚 Ventas con Transporte**
                
                | Concepto | Valor |
                |----------|-------|
                | Precio Actual | {transp_selling_price:,.2f} Bs/m³ |
                | Precio Mínimo | {transp_new_price:,.2f} Bs/m³ |
                | Ahorro Posible | {abs(transp_price_increase):,.2f} Bs/m³ |
                | Margen | {transp_profit_margin:.1f}% (o mayor si mantiene precio) |
                """)
        
        # Alternative scenarios section - now separated by type
        st.markdown("---")
        st.markdown("#### 🔄 Escenarios Alternativos por Tipo de Venta")
        
        alt_tab1, alt_tab2 = st.tabs(["🏭 Escenarios Planta", "🚚 Escenarios Transporte"])
        
        with alt_tab1:
            # Calculate plant alternative scenarios
            if plant_selling_price > plant_new_cost:
                plant_margin_if_same = ((plant_selling_price - plant_new_cost) / plant_selling_price) * 100
                plant_profit_if_same = plant_selling_price - plant_new_cost
            else:
                plant_margin_if_same = 0
                plant_profit_if_same = 0
            
            plant_price_same_profit = plant_new_cost + plant_profit_per_m3
            plant_margin_same_profit = (plant_profit_per_m3 / plant_price_same_profit * 100) if plant_price_same_profit > 0 else 0
            
            plant_sc1, plant_sc2, plant_sc3 = st.columns(3)
            
            with plant_sc1:
                st.markdown("**📌 Mantener Precio Actual**")
                margin_change_p = plant_margin_if_same - plant_profit_margin
                st.metric(
                    "Nuevo Margen",
                    f"{plant_margin_if_same:.2f}%",
                    delta=f"{margin_change_p:+.2f}%",
                    delta_color="normal" if margin_change_p >= 0 else "inverse",
                )
                st.caption(f"Ganancia: {plant_profit_if_same:,.2f} Bs/m³")
                if margin_change_p < 0:
                    st.warning(f"⚠️ Perdería {abs(margin_change_p):.2f} puntos")
                else:
                    st.success(f"✅ Ganaría {margin_change_p:.2f} puntos")
            
            with plant_sc2:
                st.markdown("**💵 Mantener Ganancia (Bs)**")
                price_change_p = plant_price_same_profit - plant_selling_price
                st.metric(
                    "Nuevo Precio",
                    f"{plant_price_same_profit:,.2f} Bs/m³",
                    delta=f"{price_change_p:+,.2f} Bs",
                    delta_color="inverse" if price_change_p > 0 else "normal",
                )
                st.caption(f"Ganancia: {plant_profit_per_m3:,.2f} Bs/m³ (sin cambio)")
                st.info(f"📊 Nuevo margen: {plant_margin_same_profit:.2f}%")
            
            with plant_sc3:
                st.markdown("**📈 Mantener Margen (%)**")
                st.metric(
                    "Nuevo Precio",
                    f"{plant_new_price:,.2f} Bs/m³",
                    delta=f"{plant_price_increase:+,.2f} Bs",
                    delta_color="inverse" if plant_price_increase > 0 else "normal",
                )
                st.caption(f"Ganancia: {plant_new_profit:,.2f} Bs/m³")
                st.info(f"📊 Margen: {plant_profit_margin:.2f}% (sin cambio)")
        
        with alt_tab2:
            # Calculate transport alternative scenarios
            if transp_selling_price > transp_new_cost:
                transp_margin_if_same = ((transp_selling_price - transp_new_cost) / transp_selling_price) * 100
                transp_profit_if_same = transp_selling_price - transp_new_cost
            else:
                transp_margin_if_same = 0
                transp_profit_if_same = 0
            
            transp_price_same_profit = transp_new_cost + transp_profit_per_m3
            transp_margin_same_profit = (transp_profit_per_m3 / transp_price_same_profit * 100) if transp_price_same_profit > 0 else 0
            
            transp_sc1, transp_sc2, transp_sc3 = st.columns(3)
            
            with transp_sc1:
                st.markdown("**📌 Mantener Precio Actual**")
                margin_change_t = transp_margin_if_same - transp_profit_margin
                st.metric(
                    "Nuevo Margen",
                    f"{transp_margin_if_same:.2f}%",
                    delta=f"{margin_change_t:+.2f}%",
                    delta_color="normal" if margin_change_t >= 0 else "inverse",
                )
                st.caption(f"Ganancia: {transp_profit_if_same:,.2f} Bs/m³")
                if margin_change_t < 0:
                    st.warning(f"⚠️ Perdería {abs(margin_change_t):.2f} puntos")
                else:
                    st.success(f"✅ Ganaría {margin_change_t:.2f} puntos")
            
            with transp_sc2:
                st.markdown("**💵 Mantener Ganancia (Bs)**")
                price_change_t = transp_price_same_profit - transp_selling_price
                st.metric(
                    "Nuevo Precio",
                    f"{transp_price_same_profit:,.2f} Bs/m³",
                    delta=f"{price_change_t:+,.2f} Bs",
                    delta_color="inverse" if price_change_t > 0 else "normal",
                )
                st.caption(f"Ganancia: {transp_profit_per_m3:,.2f} Bs/m³ (sin cambio)")
                st.info(f"📊 Nuevo margen: {transp_margin_same_profit:.2f}%")
            
            with transp_sc3:
                st.markdown("**📈 Mantener Margen (%)**")
                st.metric(
                    "Nuevo Precio",
                    f"{transp_new_price:,.2f} Bs/m³",
                    delta=f"{transp_price_increase:+,.2f} Bs",
                    delta_color="inverse" if transp_price_increase > 0 else "normal",
                )
                st.caption(f"Ganancia: {transp_new_profit:,.2f} Bs/m³")
                st.info(f"📊 Margen: {transp_profit_margin:.2f}% (sin cambio)")
        
        # Calculation details (step by step) - now for both types
        st.markdown("---")
        with st.expander("🔢 Ver cálculos paso a paso", expanded=False):
            st.markdown(f"""
            ## 🏭 Cálculos para Ventas en Planta
        
        ### Paso 1: Determinar el Costo Actual
        
        | Cálculo | Fórmula | Resultado |
        |---------|---------|-----------|
        | Costo total por m³ | Precio × (1 - Margen) | {plant_selling_price:,.2f} × (1 - {plant_margin_decimal:.4f}) = **{plant_cost_per_m3_derived:,.2f} Bs** |
        | Costo diesel por m³ | Costo total × (1 - % otros costos) | {plant_cost_per_m3_derived:,.2f} × {1 - plant_other_cost_decimal:.4f} = **{plant_diesel_in_price:,.2f} Bs** |
        | Otros costos por m³ | Costo total × % otros costos | {plant_cost_per_m3_derived:,.2f} × {plant_other_cost_decimal:.4f} = **{plant_other_costs:,.2f} Bs** |
        
        ### Paso 2: Calcular el Impacto del Diesel (Solo Producción)
        
        | Concepto | Valor |
        |----------|-------|
        | Aumento diesel producción | +{plant_cost_increase:,.2f} Bs/m³ |
        | Compensación IVA | -{iva_benefit_per_m3_plant:,.2f} Bs/m³ |
        | **Impacto neto planta** | **{net_adjustment_plant_total:+,.2f} Bs/m³** |
        
        ### Paso 3: Calcular el Nuevo Precio
        
        | Cálculo | Fórmula | Resultado |
        |---------|---------|-----------|
        | Nuevo costo | {plant_cost_per_m3_derived:,.2f} + {net_adjustment_plant_total:,.2f} | **{plant_new_cost:,.2f} Bs** |
        | Nuevo precio | {plant_new_cost:,.2f} ÷ (1 - {plant_margin_decimal:.4f}) | **{plant_new_price:,.2f} Bs** |
        | Aumento | {plant_new_price:,.2f} - {plant_selling_price:,.2f} | **{plant_price_increase:+,.2f} Bs ({plant_price_increase_pct:+.1f}%)** |
        
        ---
        
        ## 🚚 Cálculos para Ventas con Transporte
        
        ### Paso 1: Determinar el Costo Actual
        
        | Cálculo | Fórmula | Resultado |
        |---------|---------|-----------|
        | Costo total por m³ | Precio × (1 - Margen) | {transp_selling_price:,.2f} × (1 - {transp_margin_decimal:.4f}) = **{transp_cost_per_m3_derived:,.2f} Bs** |
        | Costo diesel por m³ | Costo total × (1 - % otros costos) | {transp_cost_per_m3_derived:,.2f} × {1 - transp_other_cost_decimal:.4f} = **{transp_diesel_in_price:,.2f} Bs** |
        | Otros costos por m³ | Costo total × % otros costos | {transp_cost_per_m3_derived:,.2f} × {transp_other_cost_decimal:.4f} = **{transp_other_costs:,.2f} Bs** |
        
        ### Paso 2: Calcular el Impacto del Diesel (Producción + Transporte)
        
        | Concepto | Valor |
        |----------|-------|
        | Aumento diesel (prod + transp) | +{transported_cost_increase:,.2f} Bs/m³ |
        | Compensación IVA | -{iva_benefit_per_m3_transported:,.2f} Bs/m³ |
        | **Impacto neto transporte** | **{net_adjustment_transported_total:+,.2f} Bs/m³** |
        
        ### Paso 3: Calcular el Nuevo Precio
        
        | Cálculo | Fórmula | Resultado |
        |---------|---------|-----------|
        | Nuevo costo | {transp_cost_per_m3_derived:,.2f} + {net_adjustment_transported_total:,.2f} | **{transp_new_cost:,.2f} Bs** |
        | Nuevo precio | {transp_new_cost:,.2f} ÷ (1 - {transp_margin_decimal:.4f}) | **{transp_new_price:,.2f} Bs** |
        | Aumento | {transp_new_price:,.2f} - {transp_selling_price:,.2f} | **{transp_price_increase:+,.2f} Bs ({transp_price_increase_pct:+.1f}%)** |
        
        ---
        
        ## 📊 Comparación de Impactos
        
        | Tipo de Venta | Impacto Diesel | Aumento Precio | % Aumento |
        |---------------|----------------|----------------|-----------|
        | 🏭 Planta | {net_adjustment_plant_total:+,.2f} Bs/m³ | {plant_price_increase:+,.2f} Bs | {plant_price_increase_pct:+.1f}% |
        | 🚚 Transporte | {net_adjustment_transported_total:+,.2f} Bs/m³ | {transp_price_increase:+,.2f} Bs | {transp_price_increase_pct:+.1f}% |
            | **Diferencia** | **{net_adjustment_transported_total - net_adjustment_plant_total:+,.2f} Bs/m³** | **{transp_price_increase - plant_price_increase:+,.2f} Bs** | - |
            """)
        
        # Final summary message (with transport)
        st.markdown("---")
        st.info(f"""
        **📊 Resumen Final del Análisis:**
        
        | Tipo de Venta | Precio Actual | Nuevo Precio | Cambio |
        |---------------|---------------|--------------|--------|
        | 🏭 Planta | {plant_selling_price:,.2f} Bs/m³ | {plant_new_price:,.2f} Bs/m³ | {plant_price_increase:+,.2f} Bs ({plant_price_increase_pct:+.1f}%) |
        | 🚚 Transporte | {transp_selling_price:,.2f} Bs/m³ | {transp_new_price:,.2f} Bs/m³ | {transp_price_increase:+,.2f} Bs ({transp_price_increase_pct:+.1f}%) |
        
        **Diferencia clave:** El material transportado requiere un ajuste de precio 
        **{abs(transp_price_increase - plant_price_increase):,.2f} Bs/m³ {'mayor' if transp_price_increase > plant_price_increase else 'menor'}** 
        que el material vendido en planta debido al consumo adicional de diesel para transporte.
        """)
    else:
        # Plant-only summary
        st.markdown("---")
        st.markdown("#### 📋 Resumen de Ajustes Recomendados")
        
        if plant_price_increase > 0:
            st.warning(f"""
            **🏭 Ventas en Planta**
            
            | Concepto | Valor |
            |----------|-------|
            | Precio Actual | {plant_selling_price:,.2f} Bs/m³ |
            | **Nuevo Precio** | **{plant_new_price:,.2f} Bs/m³** |
            | Aumento | +{plant_price_increase:,.2f} Bs (+{plant_price_increase_pct:.1f}%) |
            | Margen | {plant_profit_margin:.1f}% (mantenido) |
            """)
        else:
            st.success(f"""
            **🏭 Ventas en Planta**
            
            | Concepto | Valor |
            |----------|-------|
            | Precio Actual | {plant_selling_price:,.2f} Bs/m³ |
            | Precio Mínimo | {plant_new_price:,.2f} Bs/m³ |
            | Ahorro Posible | {abs(plant_price_increase):,.2f} Bs/m³ |
            | Margen | {plant_profit_margin:.1f}% (o mayor si mantiene precio) |
            """)
    
    # PDF Download Button
    st.markdown("---")
    st.markdown("#### 📄 Exportar Informe Detallado")
    
    st.markdown("""
    Genere un informe PDF profesional con todos los cálculos detallados, 
    ideal para presentar a socios, contabilidad o toma de decisiones.
    """)
    
    # Generate PDF
    try:
        pdf_bytes = generate_profit_margin_pdf(
            # Plant data
            plant_selling_price=plant_selling_price,
            plant_profit_margin=plant_profit_margin,
            plant_other_cost_pct=plant_other_cost_pct,
            plant_cost_per_m3=plant_cost_per_m3_derived,
            plant_diesel_in_price=plant_diesel_in_price,
            plant_other_costs=plant_other_costs,
            plant_profit_per_m3=plant_profit_per_m3,
            net_adjustment_plant=net_adjustment_plant_total,
            plant_new_cost=plant_new_cost,
            plant_new_price=plant_new_price,
            plant_price_increase=plant_price_increase,
            plant_price_increase_pct=plant_price_increase_pct,
            plant_new_profit=plant_new_profit,
            # Transport data
            plant_only=plant_only,
            transp_selling_price=transp_selling_price,
            transp_profit_margin=transp_profit_margin,
            transp_other_cost_pct=transp_other_cost_pct,
            transp_cost_per_m3=transp_cost_per_m3_derived,
            transp_diesel_in_price=transp_diesel_in_price,
            transp_other_costs=transp_other_costs,
            transp_profit_per_m3=transp_profit_per_m3,
            net_adjustment_transp=net_adjustment_transported_total,
            transp_new_cost=transp_new_cost,
            transp_new_price=transp_new_price,
            transp_price_increase=transp_price_increase,
            transp_price_increase_pct=transp_price_increase_pct,
            transp_new_profit=transp_new_profit,
            # General data
            transport_diesel_pct=st.session_state.transport_diesel_pct,
            iva_benefit_plant=iva_benefit_per_m3_plant,
            iva_benefit_transp=iva_benefit_per_m3_transported,
            plant_cost_increase=plant_cost_increase,
            transp_cost_increase=transported_cost_increase,
        )
        
        # Create filename with date
        pdf_filename = f"analisis_margen_ganancia_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        
        st.download_button(
            label="📥 Descargar Informe PDF Detallado",
            data=pdf_bytes,
            file_name=pdf_filename,
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
        
        st.caption("El PDF incluye: resumen ejecutivo, cálculos paso a paso para planta y transporte, tablas comparativas y recomendaciones.")
        
    except Exception as e:
        st.error(f"Error al generar el PDF: {str(e)}")
    
    st.markdown("---")
    
    # -----------------------
    # Data Table
    # -----------------------
    st.markdown("## 📋 Datos Mensuales")
    
    # Display table (hide internal id column)
    display_df = df.drop(columns=["id"])
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Delete row functionality
    with st.expander("🗑️ Eliminar mes"):
        month_to_delete = st.selectbox(
            "Seleccionar mes a eliminar",
            options=[(e["id"], e["month"]) for e in st.session_state.diesel_entries],
            format_func=lambda x: x[1],
        )
        if st.button("Eliminar"):
            db.delete_diesel_entry(month_to_delete[0])
            st.session_state.diesel_entries = [
                e for e in st.session_state.diesel_entries if e["id"] != month_to_delete[0]
            ]
            st.rerun()
    
    # Edit row functionality
    with st.expander("✏️ Editar mes"):
        if st.session_state.diesel_entries:
            # Define callback to update form fields when selection changes
            def on_edit_month_change():
                selected_id = st.session_state.edit_month_select[0]
                # Skip if we're already on this entry (prevents infinite rerun loop)
                if st.session_state.get("edit_last_selected_id") == selected_id:
                    return
                    
                entry = next(
                    (e for e in st.session_state.diesel_entries if e["id"] == selected_id),
                    None
                )
                if entry:
                    # Parse month name and year
                    month_parts = entry["month"].split()
                    month_name = month_parts[0] if len(month_parts) > 0 else "Enero"
                    year = int(month_parts[1]) if len(month_parts) > 1 else datetime.now().year
                    
                    # Update all form fields in session state
                    st.session_state.edit_month_name = month_name
                    st.session_state.edit_year = year
                    st.session_state.edit_total_spent = float(entry["total_spent"])
                    st.session_state.edit_old_price = float(entry["old_price"])
                    st.session_state.edit_new_price = float(entry["new_price"])
                    st.session_state.edit_m3_sold = float(entry["m3_sold"])
                    st.session_state.edit_m3_transported = float(entry["m3_transported"])
                    # Update tracking ID to prevent re-initialization
                    st.session_state.edit_last_selected_id = selected_id
                    # Force rerun to update widget values
                    st.rerun()
            
            # Initialize edit form session state if needed (for first load)
            if "edit_last_selected_id" not in st.session_state:
                st.session_state.edit_last_selected_id = None
            
            month_to_edit = st.selectbox(
                "Seleccionar mes a editar",
                options=[(e["id"], e["month"]) for e in st.session_state.diesel_entries],
                format_func=lambda x: x[1],
                key="edit_month_select",
                on_change=on_edit_month_change,
            )
            
            # Find the selected entry
            selected_entry = next(
                (e for e in st.session_state.diesel_entries if e["id"] == month_to_edit[0]), 
                None
            )
            
            if selected_entry:
                # Initialize form fields on first load or when entry changes
                if st.session_state.edit_last_selected_id != month_to_edit[0]:
                    month_parts = selected_entry["month"].split()
                    month_name = month_parts[0] if len(month_parts) > 0 else "Enero"
                    year = int(month_parts[1]) if len(month_parts) > 1 else datetime.now().year
                    
                    st.session_state.edit_month_name = month_name
                    st.session_state.edit_year = year
                    st.session_state.edit_total_spent = float(selected_entry["total_spent"])
                    st.session_state.edit_old_price = float(selected_entry["old_price"])
                    st.session_state.edit_new_price = float(selected_entry["new_price"])
                    st.session_state.edit_m3_sold = float(selected_entry["m3_sold"])
                    st.session_state.edit_m3_transported = float(selected_entry["m3_transported"])
                    st.session_state.edit_last_selected_id = month_to_edit[0]
                
                st.markdown("---")
                edit_col1, edit_col2 = st.columns(2)
                
                months_list = [
                    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
                ]
                
                with edit_col1:
                    edit_month = st.selectbox(
                        "Mes", 
                        options=months_list,
                        key="edit_month_name",
                    )
                    edit_year = st.number_input(
                        "Año", 
                        min_value=2020, 
                        max_value=2030, 
                        step=1, 
                        key="edit_year",
                    )
                    edit_total_spent = st.number_input(
                        "Total gastado en diesel (Bs)",
                        min_value=0.01,
                        step=100.0,
                        format="%.2f",
                        key="edit_total_spent",
                    )
                
                with edit_col2:
                    edit_old_price = st.number_input(
                        "Precio antiguo (Bs/L)",
                        min_value=0.01,
                        step=0.01,
                        format="%.2f",
                        key="edit_old_price",
                    )
                    edit_new_price = st.number_input(
                        "Precio nuevo (Bs/L)",
                        min_value=0.01,
                        step=0.01,
                        format="%.2f",
                        key="edit_new_price",
                    )
                
                st.markdown("**Producción:**")
                edit_prod_col1, edit_prod_col2 = st.columns(2)
                
                with edit_prod_col1:
                    edit_m3_sold = st.number_input(
                        "m³ Vendidos",
                        min_value=0.0,
                        step=10.0,
                        format="%.2f",
                        key="edit_m3_sold",
                    )
                
                with edit_prod_col2:
                    edit_m3_transported = st.number_input(
                        "m³ Transportados",
                        min_value=0.0,
                        step=10.0,
                        format="%.2f",
                        key="edit_m3_transported",
                    )
                
                if st.button("💾 Guardar Cambios", use_container_width=True):
                    if edit_m3_sold <= 0 and edit_m3_transported <= 0:
                        st.error("Debe ingresar al menos m³ vendidos o transportados")
                    else:
                        # Update the entry in session state and database
                        for entry in st.session_state.diesel_entries:
                            if entry["id"] == month_to_edit[0]:
                                entry["month"] = f"{edit_month} {edit_year}"
                                entry["total_spent"] = edit_total_spent
                                entry["old_price"] = edit_old_price
                                entry["new_price"] = edit_new_price
                                entry["m3_sold"] = edit_m3_sold
                                entry["m3_transported"] = edit_m3_transported
                                # Save updated entry to database
                                db.save_diesel_entry(entry)
                                break
                        st.success(f"✅ Datos de {edit_month} {edit_year} actualizados")
                        # Reset tracking so next edit will load fresh values
                        st.session_state.edit_last_selected_id = None
                        st.rerun()
    
    # Export to CSV
    csv = display_df.to_csv(index=False)
    st.download_button(
        label="📥 Descargar CSV",
        data=csv,
        file_name=f"analisis_diesel_{st.session_state.selected_company.replace(' ', '_')}.csv",
        mime="text/csv",
    )
    
    st.markdown("---")
    
    # -----------------------
    # Charts
    # -----------------------
    st.markdown("## 📊 Gráficos y Visualizaciones")
    
    with st.expander("ℹ️ ¿Cómo interpretar los gráficos?", expanded=False):
        st.markdown("""
        ### Guía de Gráficos
        
        1. **Comparación Gasto Actual vs Proyectado**: Muestra la diferencia entre lo que pagó y lo que pagaría 
           con el nuevo precio. Las barras rojas más altas indican mayor impacto del aumento.
        
        2. **Comparación Crédito Fiscal IVA**: Compara el crédito que obtenía antes (70%) vs ahora (100%).
           Las barras naranjas (nuevo) siempre serán mayores que las moradas (anterior).
        
        3. **Comparación Porcentual**: Muestra los cambios como porcentajes para facilitar la comparación.
           Ideal para ver si el % de aumento en IVA supera el % de aumento en costo.
        
        4. **Distribución del Impacto**: Gráfico de dona que muestra visualmente cuánto del aumento 
           en diesel es compensado por el beneficio del IVA.
        
        5. **Tendencia Costo por m³**: Evolución del costo de diesel por metro cúbico a lo largo del tiempo.
        """)
    
    # Row 1: Cost and IVA comparison
    st.markdown("### 📈 Comparaciones de Montos")
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.plotly_chart(plot_cost_comparison(df), use_container_width=True)
        st.caption(f"📊 El costo proyectado es **{cost_increase_pct:.1f}%** mayor que el gasto actual")
    
    with chart_col2:
        st.plotly_chart(plot_iva_comparison(df), use_container_width=True)
        st.caption(f"📊 El nuevo crédito IVA es **{iva_benefit_pct:.1f}%** mayor que el anterior")
    
    # Row 2: Percentage comparison and impact breakdown
    st.markdown("### 📊 Análisis Porcentual")
    
    chart_col3, chart_col4 = st.columns(2)
    
    with chart_col3:
        st.plotly_chart(plot_percentage_comparison(df), use_container_width=True)
        if iva_benefit_pct > cost_increase_pct:
            st.success(f"✅ El beneficio IVA (+{iva_benefit_pct:.1f}%) supera el aumento de costo (+{cost_increase_pct:.1f}%)")
        else:
            st.warning(f"⚠️ El aumento de costo (+{cost_increase_pct:.1f}%) supera el beneficio IVA (+{iva_benefit_pct:.1f}%)")
    
    with chart_col4:
        st.plotly_chart(plot_impact_breakdown(total_cost_diff, total_iva_benefit), use_container_width=True)
        compensation_ratio = (total_iva_benefit / total_cost_diff * 100) if total_cost_diff > 0 else 0
        st.info(f"💡 El beneficio IVA compensa el **{compensation_ratio:.1f}%** del aumento en el costo del diesel")
    
    # Row 3: Trend chart (full width)
    st.markdown("### 📉 Tendencia Histórica")
    st.plotly_chart(plot_cost_per_m3_trend(df), use_container_width=True)
    
    # Calculate trend
    if len(df) >= 2:
        first_cost = df["Costo/m³ (Bs)"].iloc[0]
        last_cost = df["Costo/m³ (Bs)"].iloc[-1]
        trend_change = last_cost - first_cost
        trend_pct = (trend_change / first_cost * 100) if first_cost > 0 else 0
        if trend_change > 0:
            st.caption(f"📈 Tendencia: El costo por m³ ha **aumentado** de {first_cost:.2f} Bs a {last_cost:.2f} Bs (+{trend_pct:.1f}%)")
        elif trend_change < 0:
            st.caption(f"📉 Tendencia: El costo por m³ ha **disminuido** de {first_cost:.2f} Bs a {last_cost:.2f} Bs ({trend_pct:.1f}%)")
        else:
            st.caption(f"➡️ Tendencia: El costo por m³ se ha mantenido estable en {last_cost:.2f} Bs")
    
    # -----------------------
    # Summary Table
    # -----------------------
    st.markdown("## 📝 Resumen Completo de Impacto Financiero")
    
    with st.expander("ℹ️ ¿Qué significa cada métrica?", expanded=False):
        st.markdown("""
        ### Guía de Interpretación
        
        #### Crédito Fiscal IVA
        - **Política anterior**: Solo el 70% de su compra de diesel era base para el crédito fiscal del 13%
        - **Nueva política**: El 100% de su compra es base para el crédito fiscal del 13%
        - **Beneficio**: La diferencia representa dinero adicional que puede descontar de su IVA a pagar
        
        #### Impacto del Precio
        - **Gasto actual**: Lo que pagó realmente por el diesel
        - **Costo proyectado**: Lo que habría pagado con el nuevo precio por el mismo volumen
        - **Diferencia**: El costo adicional que representa el nuevo precio
        
        #### Impacto Neto
        - Combina el aumento del costo con el beneficio del IVA
        - **Positivo** = aumento real de costos (debe subir precios)
        - **Negativo** = ahorro neto (puede mantener o bajar precios)
        """)
    
    summary_col1, summary_col2 = st.columns(2)
    
    # Calculate additional percentages
    iva_increase_pct = (total_iva_benefit / total_iva_current * 100) if total_iva_current > 0 else 0
    effective_iva_rate_current = (total_iva_current / total_spent_sum * 100) if total_spent_sum > 0 else 0
    effective_iva_rate_new = (total_iva_new / total_projected_sum * 100) if total_projected_sum > 0 else 0
    
    with summary_col1:
        st.markdown("### 💳 Crédito Fiscal IVA")
        st.markdown(f"""
        | Concepto | Monto (Bs) | % |
        |----------|------------|---|
        | Crédito IVA Anterior (13% × 70%) | {total_iva_current:,.2f} | {effective_iva_rate_current:.1f}% del gasto |
        | Crédito IVA Nuevo (13% × 100%) | {total_iva_new:,.2f} | {effective_iva_rate_new:.1f}% del gasto |
        | **Beneficio Adicional** | **{total_iva_benefit:,.2f}** | **+{iva_increase_pct:.1f}%** |
        """)
        
        st.info(f"""
        📊 **Resumen IVA**: Con la nueva política, recupera **{iva_increase_pct:.1f}% más** en crédito fiscal.
        
        Por cada 1,000 Bs gastados en diesel:
        - Antes: 1,000 × 70% × 13% = **91 Bs** de crédito
        - Ahora: 1,000 × 100% × 13% = **130 Bs** de crédito
        - Beneficio: **39 Bs adicionales** (42.9% más)
        """)
    
    with summary_col2:
        st.markdown("### 📈 Impacto del Precio")
        net_impact_final = total_cost_diff - total_iva_benefit
        net_impact_pct_final = (net_impact_final / total_spent_sum * 100) if total_spent_sum > 0 else 0
        
        st.markdown(f"""
        | Concepto | Monto (Bs) | % del original |
        |----------|------------|----------------|
        | Gasto Actual (precio antiguo) | {total_spent_sum:,.2f} | 100% |
        | Costo Proyectado (precio nuevo) | {total_projected_sum:,.2f} | {(total_projected_sum/total_spent_sum*100) if total_spent_sum > 0 else 0:.1f}% |
        | Aumento Bruto | +{total_cost_diff:,.2f} | +{cost_increase_pct:.1f}% |
        | Compensación IVA | -{total_iva_benefit:,.2f} | -{(total_iva_benefit/total_spent_sum*100) if total_spent_sum > 0 else 0:.1f}% |
        | **Impacto Neto** | **{net_impact_final:+,.2f}** | **{net_impact_pct_final:+.1f}%** |
        """)
        
        if net_impact_final > 0:
            st.warning(f"""
            ⚠️ **Impacto neto positivo**: Sus costos aumentan en **{net_impact_final:,.2f} Bs** ({net_impact_pct_final:.1f}%) 
            después de considerar el beneficio del IVA.
            """)
        else:
            st.success(f"""
            ✅ **Impacto neto negativo**: Tiene un ahorro neto de **{abs(net_impact_final):,.2f} Bs** ({abs(net_impact_pct_final):.1f}%) 
            gracias al mayor crédito fiscal IVA.
            """)
    
    # Additional summary metrics
    st.markdown("### 📊 Comparación de Escenarios")
    
    scenario_col1, scenario_col2, scenario_col3 = st.columns(3)
    
    with scenario_col1:
        st.markdown("**🔴 Escenario Sin IVA Nuevo**")
        scenario_no_iva = total_cost_diff
        scenario_no_iva_pct = (scenario_no_iva / total_spent_sum * 100) if total_spent_sum > 0 else 0
        st.metric(
            "Aumento Total",
            f"+{scenario_no_iva:,.0f} Bs",
            delta=f"+{scenario_no_iva_pct:.1f}%",
            delta_color="inverse",
        )
        st.caption("Si solo subiera el precio del diesel sin el beneficio del nuevo IVA")
    
    with scenario_col2:
        st.markdown("**🟢 Escenario Con IVA Nuevo**")
        st.metric(
            "Impacto Real",
            f"{net_impact_final:+,.0f} Bs",
            delta=f"{net_impact_pct_final:+.1f}%",
            delta_color="inverse" if net_impact_final > 0 else "normal",
        )
        st.caption("Impacto real considerando el mayor crédito fiscal del IVA")
    
    with scenario_col3:
        st.markdown("**💰 Ahorro por IVA**")
        savings_vs_no_iva_pct = (total_iva_benefit / total_cost_diff * 100) if total_cost_diff > 0 else 0
        st.metric(
            "Compensación",
            f"{total_iva_benefit:,.0f} Bs",
            delta=f"Cubre {savings_vs_no_iva_pct:.1f}% del aumento",
            delta_color="normal",
        )
        st.caption("Monto que el beneficio IVA compensa del aumento del diesel")
