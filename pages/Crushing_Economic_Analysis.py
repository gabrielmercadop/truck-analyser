"""
Crushing Economic Analysis - Análisis Económico de Servicios de Trituración
Para proyectos carreteros
"""

import io
import sys
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from fpdf import FPDF

# Add parent directory to path for db import
sys.path.insert(0, str(Path(__file__).parent.parent))
import db


# -----------------------
# Persistence (SQLite) - Scenario Storage
# -----------------------
SCENARIOS_DB_PATH = Path(__file__).parent.parent / "scenarios.sqlite3"


def init_scenarios_db() -> None:
    """Initialize SQLite DB for saved scenarios."""
    SCENARIOS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(SCENARIOS_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_saved_scenarios_created_at ON saved_scenarios(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_saved_scenarios_name ON saved_scenarios(name)"
        )


def save_scenario_to_db(name: str, payload: dict) -> None:
    """Save a scenario payload to SQLite."""
    created_at = datetime.now().isoformat(timespec="seconds")
    payload_json = json.dumps(payload, ensure_ascii=False)
    with sqlite3.connect(SCENARIOS_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO saved_scenarios (created_at, name, payload_json) VALUES (?, ?, ?)",
            (created_at, name.strip(), payload_json),
        )


def list_saved_scenarios() -> pd.DataFrame:
    """List saved scenarios (metadata) ordered by newest first."""
    init_scenarios_db()
    with sqlite3.connect(SCENARIOS_DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT id, created_at, name FROM saved_scenarios ORDER BY created_at DESC",
            conn,
        )
    return df


def load_scenario_payload(scenario_id: int) -> dict:
    """Load a saved scenario payload by id."""
    init_scenarios_db()
    with sqlite3.connect(SCENARIOS_DB_PATH) as conn:
        row = conn.execute(
            "SELECT payload_json FROM saved_scenarios WHERE id = ?",
            (int(scenario_id),),
        ).fetchone()
    if not row:
        return {}
    return json.loads(row[0])


# -----------------------
# Data Classes
# -----------------------
@dataclass
class PlantEquipmentConfig:
    """Configuration for plant equipment powered by generator (no direct diesel)."""
    name: str
    enabled: bool = True
    quantity: int = 1
    operation_hours_day: float = 8.0
    maintenance_cost_ph: float = 0.0  # Cost per hour
    wear_cost_ph: float = 0.0  # Wear/parts cost per hour
    
    @property
    def daily_maintenance_cost(self) -> float:
        if not self.enabled:
            return 0.0
        return self.maintenance_cost_ph * self.operation_hours_day * self.quantity
    
    @property
    def daily_wear_cost(self) -> float:
        if not self.enabled:
            return 0.0
        return self.wear_cost_ph * self.operation_hours_day * self.quantity


@dataclass
class MobileEquipmentConfig:
    """Configuration for mobile equipment that uses diesel directly."""
    name: str
    enabled: bool = True
    quantity: int = 1
    diesel_consumption_lph: float = 0.0  # Liters per hour per unit
    operation_hours_day: float = 8.0
    maintenance_cost_ph: float = 0.0  # Cost per hour per unit
    wear_cost_ph: float = 0.0  # Wear/parts cost per hour per unit
    
    @property
    def daily_diesel_liters(self) -> float:
        if not self.enabled:
            return 0.0
        return self.diesel_consumption_lph * self.operation_hours_day * self.quantity
    
    @property
    def daily_maintenance_cost(self) -> float:
        if not self.enabled:
            return 0.0
        return self.maintenance_cost_ph * self.operation_hours_day * self.quantity
    
    @property
    def daily_wear_cost(self) -> float:
        if not self.enabled:
            return 0.0
        return self.wear_cost_ph * self.operation_hours_day * self.quantity


@dataclass
class GeneratorConfig:
    """Configuration for the generator that powers plant equipment."""
    enabled: bool = True
    quantity: int = 1
    diesel_consumption_lph: float = 80.0  # Liters per hour
    operation_hours_day: float = 8.0
    maintenance_cost_ph: float = 30.0
    wear_cost_ph: float = 20.0

    @property
    def daily_diesel_liters(self) -> float:
        if not self.enabled:
            return 0.0
        return self.diesel_consumption_lph * self.operation_hours_day * self.quantity

    @property
    def daily_maintenance_cost(self) -> float:
        if not self.enabled:
            return 0.0
        return self.maintenance_cost_ph * self.operation_hours_day * self.quantity

    @property
    def daily_wear_cost(self) -> float:
        if not self.enabled:
            return 0.0
        return self.wear_cost_ph * self.operation_hours_day * self.quantity


@dataclass
class PersonnelConfig:
    """Configuration for personnel costs."""
    operators_count: int = 4
    operators_daily_wage: float = 200.0
    helpers_count: int = 6
    helpers_daily_wage: float = 130.0
    supervisors_count: int = 1
    supervisors_daily_wage: float = 300.0
    social_benefits_pct: float = 30.0  # Percentage over base salaries
    
    @property
    def base_daily_cost(self) -> float:
        return (
            self.operators_count * self.operators_daily_wage +
            self.helpers_count * self.helpers_daily_wage +
            self.supervisors_count * self.supervisors_daily_wage
        )
    
    @property
    def total_daily_cost(self) -> float:
        return self.base_daily_cost * (1 + self.social_benefits_pct / 100)


@dataclass
class LogisticsConfig:
    """Configuration for logistics and transport costs."""
    mobilization_cost: float = 50000.0  # One-time cost
    demobilization_cost: float = 30000.0  # One-time cost
    support_vehicles_fuel_daily: float = 500.0
    consumables_daily: float = 300.0  # Lubricants, filters, etc.
    
    @property
    def daily_cost(self) -> float:
        return self.support_vehicles_fuel_daily + self.consumables_daily
    
    def total_mobilization_cost(self) -> float:
        return self.mobilization_cost + self.demobilization_cost


@dataclass
class ProjectConfig:
    """Configuration for the project."""
    name: str = "Proyecto Carretero"
    duration_days: int = 143
    daily_production: float = 500.0
    material_type: str = "Grava"
    unit: str = "m³"  # m³ or tonelada
    
    @property
    def total_production(self) -> float:
        return self.duration_days * self.daily_production


@dataclass
class EconomicConfig:
    """Economic variables."""
    diesel_price: float = 9.8  # Bs/L
    selling_price_per_unit: float = 50  # Bs per m³ or ton
    target_margin_pct: float = 40


# -----------------------
# Default Equipment Configurations
# -----------------------
def get_default_plant_equipment() -> dict[str, PlantEquipmentConfig]:
    """Return default plant equipment configurations (powered by generator)."""
    return {
        "primary_crusher": PlantEquipmentConfig(
            name="Trituradora Primaria (Mandíbulas)",
            enabled=True,
            operation_hours_day=8.0,
            maintenance_cost_ph=30.0,
            wear_cost_ph=60.0,
        ),
        "secondary_crusher": PlantEquipmentConfig(
            name="Trituradora Secundaria (Cono)",
            enabled=True,
            operation_hours_day=8.0,
            maintenance_cost_ph=30.0,
            wear_cost_ph=55.0,
        ),
        "screens": PlantEquipmentConfig(
            name="Cribas/Zarandas",
            enabled=True,
            quantity=2,
            operation_hours_day=8.0,
            maintenance_cost_ph=12.0,
            wear_cost_ph=20.0,
        ),
        "feeders": PlantEquipmentConfig(
            name="Alimentadores",
            enabled=True,
            operation_hours_day=8.0,
            maintenance_cost_ph=5.0,
            wear_cost_ph=8.0,
        ),
        "conveyors": PlantEquipmentConfig(
            name="Bandas Transportadoras",
            enabled=True,
            operation_hours_day=8.0,
            maintenance_cost_ph=10.0,
            wear_cost_ph=18.0,
        ),
        "tertiary_crusher_hsi": PlantEquipmentConfig(
            name="Trituradora Terciaria Horizontal (Impacto)",
            enabled=True,
            operation_hours_day=8.0,
            maintenance_cost_ph=25.0,
            wear_cost_ph=70.0,
        ),
        "screw_washer": PlantEquipmentConfig(
            name="Lavadora de Tornillo (Screw Washer)",
            enabled=True,
            operation_hours_day=8.0,
            maintenance_cost_ph=12.0,
            wear_cost_ph=18.0,
        ),
    }


def get_default_mobile_equipment() -> dict[str, MobileEquipmentConfig]:
    """Return default mobile equipment configurations (uses diesel directly)."""
    return {
        "loader": MobileEquipmentConfig(
            name="Cargador Frontal",
            enabled=True,
            quantity=2,
            diesel_consumption_lph=25.0,
            operation_hours_day=6.0,
            maintenance_cost_ph=20.0,
            wear_cost_ph=30.0,
        ),
        "excavator": MobileEquipmentConfig(
            name="Excavadora",
            enabled=True,
            quantity=1,
            diesel_consumption_lph=30.0,
            operation_hours_day=8.0,
            maintenance_cost_ph=25.0,
            wear_cost_ph=35.0,
        ),
        "dump_trucks": MobileEquipmentConfig(
            name="Volquetas",
            enabled=True,
            quantity=3,
            diesel_consumption_lph=18.0,
            operation_hours_day=8.0,
            maintenance_cost_ph=12.0,
            wear_cost_ph=15.0,
        ),
    }


def get_default_generator() -> GeneratorConfig:
    """Return default generator configuration."""
    return GeneratorConfig(
        enabled=True,
        quantity=2,
        diesel_consumption_lph=80.0,
        operation_hours_day=8.0,
        maintenance_cost_ph=40.0,
        wear_cost_ph=35.0,
    )


# -----------------------
# Calculation Functions
# -----------------------
def calculate_all_equipment_costs(
    plant_equipment: dict[str, PlantEquipmentConfig],
    mobile_equipment: dict[str, MobileEquipmentConfig],
    generator: GeneratorConfig,
    diesel_price: float
) -> dict:
    """Calculate total equipment costs including generator, plant, and mobile equipment."""
    total_diesel_liters = 0.0
    total_maintenance = 0.0
    total_wear = 0.0
    equipment_details = []

    # Generator costs (powers plant equipment)
    if generator.enabled:
        gen_diesel = generator.daily_diesel_liters
        gen_diesel_cost = gen_diesel * diesel_price
        gen_maintenance = generator.daily_maintenance_cost
        gen_wear = generator.daily_wear_cost

        total_diesel_liters += gen_diesel
        total_maintenance += gen_maintenance
        total_wear += gen_wear

        equipment_details.append({
            "Equipo": "Generador (Planta)",
            "Cantidad": generator.quantity,
            "Diésel (L/día)": gen_diesel,
            "Costo Diésel (Bs)": gen_diesel_cost,
            "Mantenimiento (Bs)": gen_maintenance,
            "Desgaste (Bs)": gen_wear,
            "Total (Bs)": gen_diesel_cost + gen_maintenance + gen_wear,
        })

    # Plant equipment costs (no diesel, powered by generator)
    for key, eq in plant_equipment.items():
        if eq.enabled:
            maintenance = eq.daily_maintenance_cost
            wear = eq.daily_wear_cost

            total_maintenance += maintenance
            total_wear += wear

            equipment_details.append({
                "Equipo": eq.name,
                "Cantidad": eq.quantity,
                "Diésel (L/día)": 0.0,  # Powered by generator
                "Costo Diésel (Bs)": 0.0,
                "Mantenimiento (Bs)": maintenance,
                "Desgaste (Bs)": wear,
                "Total (Bs)": maintenance + wear,
            })

    # Mobile equipment costs (uses diesel directly)
    for key, eq in mobile_equipment.items():
        if eq.enabled:
            diesel_liters = eq.daily_diesel_liters
            diesel_cost = diesel_liters * diesel_price
            maintenance = eq.daily_maintenance_cost
            wear = eq.daily_wear_cost

            total_diesel_liters += diesel_liters
            total_maintenance += maintenance
            total_wear += wear

            equipment_details.append({
                "Equipo": eq.name,
                "Cantidad": eq.quantity,
                "Diésel (L/día)": diesel_liters,
                "Costo Diésel (Bs)": diesel_cost,
                "Mantenimiento (Bs)": maintenance,
                "Desgaste (Bs)": wear,
                "Total (Bs)": diesel_cost + maintenance + wear,
            })

    total_diesel_cost = total_diesel_liters * diesel_price

    return {
        "total_diesel_liters": total_diesel_liters,
        "total_diesel_cost": total_diesel_cost,
        "total_maintenance": total_maintenance,
        "total_wear": total_wear,
        "total_equipment_cost": total_diesel_cost + total_maintenance + total_wear,
        "details": equipment_details,
    }


def calculate_total_daily_cost(
    equipment_costs: dict,
    personnel: PersonnelConfig,
    logistics: LogisticsConfig,
) -> dict:
    """Calculate total daily operational cost."""
    equipment_total = equipment_costs["total_equipment_cost"]
    personnel_total = personnel.total_daily_cost
    logistics_total = logistics.daily_cost
    
    total = equipment_total + personnel_total + logistics_total
    
    return {
        "equipment": equipment_total,
        "diesel": equipment_costs["total_diesel_cost"],
        "maintenance": equipment_costs["total_maintenance"],
        "wear": equipment_costs["total_wear"],
        "personnel": personnel_total,
        "logistics": logistics_total,
        "total": total,
    }


def calculate_unit_cost(
    daily_costs: dict,
    daily_production: float,
    project_duration: int,
    mobilization_cost: float,
) -> dict:
    """Calculate cost per unit (m³ or ton)."""
    if daily_production <= 0:
        return {"cost_per_unit": 0, "breakdown": {}}
    
    # Amortize mobilization over total production
    total_production = daily_production * project_duration
    mobilization_per_unit = mobilization_cost / total_production if total_production > 0 else 0
    
    # Direct cost per unit
    direct_cost_per_unit = daily_costs["total"] / daily_production
    
    # Total cost per unit including mobilization amortization
    total_cost_per_unit = direct_cost_per_unit + mobilization_per_unit
    
    breakdown = {
        "Diésel": daily_costs["diesel"] / daily_production,
        "Mantenimiento": daily_costs["maintenance"] / daily_production,
        "Desgaste": daily_costs["wear"] / daily_production,
        "Personal": daily_costs["personnel"] / daily_production,
        "Logística": daily_costs["logistics"] / daily_production,
        "Movilización (amort.)": mobilization_per_unit,
    }
    
    return {
        "cost_per_unit": total_cost_per_unit,
        "direct_cost_per_unit": direct_cost_per_unit,
        "mobilization_per_unit": mobilization_per_unit,
        "breakdown": breakdown,
    }


def calculate_margins(
    cost_per_unit: float,
    selling_price: float,
) -> dict:
    """Calculate profit margins."""
    if selling_price <= 0:
        return {
            "gross_profit": 0,
            "margin_pct": 0,
            "markup_pct": 0,
        }
    
    gross_profit = selling_price - cost_per_unit
    margin_pct = (gross_profit / selling_price) * 100
    markup_pct = (gross_profit / cost_per_unit) * 100 if cost_per_unit > 0 else 0
    
    return {
        "gross_profit": gross_profit,
        "margin_pct": margin_pct,
        "markup_pct": markup_pct,
    }


def calculate_scenario(
    base_daily_costs: dict,
    base_production: float,
    production_adjustment: float,
    cost_adjustment: float,
    project_duration: int,
    mobilization_cost: float,
    selling_price: float,
) -> dict:
    """Calculate a scenario with adjusted production and costs.

    Notes:
    - `base_daily_costs` comes from `calculate_total_daily_cost()` and contains both an
      aggregated `equipment` key and the component keys `diesel`, `maintenance`, `wear`.
      If we sum *all* of those we would double-count equipment.
    - For scenarios we scale the component costs, rebuild `equipment`, and then rebuild
      `total` as: equipment + personnel + logistics.
    """

    # Adjust production
    adjusted_production = base_production * (1 + production_adjustment)

    # Scale the component costs (avoid double counting the aggregated 'equipment')
    component_keys = ["diesel", "maintenance", "wear", "personnel", "logistics"]
    adjusted_costs: dict[str, float] = {}

    for k in component_keys:
        if k in base_daily_costs:
            adjusted_costs[k] = float(base_daily_costs[k]) * (1 + cost_adjustment)

    # Rebuild equipment as the sum of its components
    adjusted_costs["equipment"] = (
        adjusted_costs.get("diesel", 0.0)
        + adjusted_costs.get("maintenance", 0.0)
        + adjusted_costs.get("wear", 0.0)
    )

    # Rebuild total daily cost (equipment + personnel + logistics)
    adjusted_costs["total"] = (
        adjusted_costs.get("equipment", 0.0)
        + adjusted_costs.get("personnel", 0.0)
        + adjusted_costs.get("logistics", 0.0)
    )

    # Calculate unit cost
    unit_cost_data = calculate_unit_cost(
        adjusted_costs,
        adjusted_production,
        project_duration,
        mobilization_cost,
    )

    # Calculate margins
    margins = calculate_margins(unit_cost_data["cost_per_unit"], selling_price)

    return {
        "daily_production": adjusted_production,
        "daily_cost": adjusted_costs["total"],
        "cost_per_unit": unit_cost_data["cost_per_unit"],
        "selling_price": selling_price,
        "gross_profit": margins["gross_profit"],
        "margin_pct": margins["margin_pct"],
        "total_project_revenue": adjusted_production * project_duration * selling_price,
        "total_project_cost": adjusted_costs["total"] * project_duration + mobilization_cost,
        "total_project_profit": (adjusted_production * project_duration * selling_price)
        - (adjusted_costs["total"] * project_duration + mobilization_cost),
    }


def calculate_diesel_sensitivity(
    plant_equipment: dict[str, PlantEquipmentConfig],
    mobile_equipment: dict[str, MobileEquipmentConfig],
    generator: GeneratorConfig,
    personnel: PersonnelConfig,
    logistics: LogisticsConfig,
    project: ProjectConfig,
    economic: EconomicConfig,
    diesel_variations: list[float],
) -> pd.DataFrame:
    """Calculate sensitivity analysis for diesel price variations."""
    results = []
    base_diesel_price = economic.diesel_price
    
    for variation in diesel_variations:
        adjusted_diesel = base_diesel_price * (1 + variation)
        
        # Recalculate equipment costs with new diesel price
        eq_costs = calculate_all_equipment_costs(
            plant_equipment, mobile_equipment, generator, adjusted_diesel
        )
        daily_costs = calculate_total_daily_cost(eq_costs, personnel, logistics)
        
        unit_cost = calculate_unit_cost(
            daily_costs,
            project.daily_production,
            project.duration_days,
            logistics.total_mobilization_cost(),
        )
        
        margins = calculate_margins(
            unit_cost["cost_per_unit"],
            economic.selling_price_per_unit,
        )
        
        results.append({
            "Variación Diésel": f"{variation*100:+.0f}%",
            "Precio Diésel (Bs/L)": adjusted_diesel,
            "Costo por Unidad (Bs)": unit_cost["cost_per_unit"],
            "Margen (%)": margins["margin_pct"],
            "Ganancia por Unidad (Bs)": margins["gross_profit"],
        })
    
    return pd.DataFrame(results)


# -----------------------
# PDF Generation Class
# -----------------------
class CrushingAnalysisPDF(FPDF):
    """Custom PDF class for Crushing Economic Analysis reports."""
    
    def __init__(self, project_name: str = "Proyecto"):
        super().__init__()
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=15)
        self.effective_width = 143
        self.project_name = project_name
    
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Analisis Economico de Trituracion", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, self.project_name, align="C", new_x="LMARGIN", new_y="NEXT")
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
    
    def add_key_value(self, key: str, value: str):
        self.set_x(self.l_margin)
        key_width = 70
        value_width = self.effective_width - key_width
        
        self.set_font("Helvetica", "B", 9)
        self.cell(key_width, 6, key + ":", align="L")
        self.set_font("Helvetica", "", 9)
        self.cell(value_width, 6, value, align="L", new_x="LMARGIN", new_y="NEXT")
    
    def add_table(self, headers: list, data: list, col_widths: list = None):
        if col_widths is None:
            col_widths = [self.effective_width // len(headers)] * len(headers)
            col_widths[-1] = self.effective_width - sum(col_widths[:-1])
        
        total_width = sum(col_widths)
        if total_width > self.effective_width:
            scale = self.effective_width / total_width
            col_widths = [int(w * scale) for w in col_widths]
        
        # Header
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(236, 240, 241)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, border=1, fill=True, align="C")
        self.ln()
        
        # Data rows
        self.set_font("Helvetica", "", 8)
        for row in data:
            self.set_x(self.l_margin)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 6, str(cell), border=1, align="C")
            self.ln()
        self.ln(2)
    
    def add_highlight_box(self, text: str, box_type: str = "info"):
        if box_type == "success":
            self.set_fill_color(212, 237, 218)
            self.set_text_color(21, 87, 36)
        elif box_type == "warning":
            self.set_fill_color(255, 243, 205)
            self.set_text_color(133, 100, 4)
        elif box_type == "danger":
            self.set_fill_color(248, 215, 218)
            self.set_text_color(114, 28, 36)
        else:  # info
            self.set_fill_color(209, 236, 241)
            self.set_text_color(12, 84, 96)
        
        self.set_font("Helvetica", "", 9)
        self.multi_cell(self.effective_width, 5, text, fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)


def generate_pdf_report(
    project: ProjectConfig,
    personnel: PersonnelConfig,
    logistics: LogisticsConfig,
    economic: EconomicConfig,
    equipment_costs: dict,
    daily_costs: dict,
    unit_cost_data: dict,
    margins: dict,
    scenarios: dict,
    sensitivity_df: pd.DataFrame,
    materials: list[dict],
    material_margin_df: pd.DataFrame,
) -> bytes:
    """Generate a comprehensive PDF report."""
    pdf = CrushingAnalysisPDF(project.name)
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Project Summary
    pdf.section_title("Resumen del Proyecto")
    pdf.add_key_value("Nombre del Proyecto", project.name)
    pdf.add_key_value("Duracion", f"{project.duration_days} dias")
    pdf.add_key_value("Produccion Diaria", f"{project.daily_production:,.0f} {project.unit}")
    pdf.add_key_value("Produccion Total", f"{project.total_production:,.0f} {project.unit}")
    pdf.add_key_value("Tipo de Material", project.material_type)
    pdf.ln(3)
    
    # Economic Parameters
    pdf.section_title("Parametros Economicos")
    pdf.add_key_value("Precio del Diesel", f"{economic.diesel_price:,.2f} Bs/L")
    pdf.add_key_value("Precio de Venta", f"{economic.selling_price_per_unit:,.2f} Bs/{project.unit}")
    pdf.add_key_value("Margen Objetivo", f"{economic.target_margin_pct:.1f}%")
    pdf.ln(3)
    
    # Equipment Costs Table
    pdf.section_title("Costos de Equipos (Diario)")
    if equipment_costs["details"]:
        headers = ["Equipo", "Diesel (L)", "Diesel (Bs)", "Mant. (Bs)", "Desg. (Bs)", "Total (Bs)"]
        data = []
        for eq in equipment_costs["details"]:
            data.append([
                eq["Equipo"][:25],  # Truncate long names
                f"{eq['Diésel (L/día)']:,.1f}",
                f"{eq['Costo Diésel (Bs)']:,.0f}",
                f"{eq['Mantenimiento (Bs)']:,.0f}",
                f"{eq['Desgaste (Bs)']:,.0f}",
                f"{eq['Total (Bs)']:,.0f}",
            ])
        pdf.add_table(headers, data, col_widths=[50, 22, 25, 25, 25, 25])
    
    # Daily Cost Summary
    pdf.section_title("Resumen de Costos Diarios")
    pdf.add_key_value("Diésel Total", f"{daily_costs['diesel']:,.2f} Bs")
    pdf.add_key_value("Mantenimiento", f"{daily_costs['maintenance']:,.2f} Bs")
    pdf.add_key_value("Desgaste", f"{daily_costs['wear']:,.2f} Bs")
    pdf.add_key_value("Personal", f"{daily_costs['personnel']:,.2f} Bs")
    pdf.add_key_value("Logística", f"{daily_costs['logistics']:,.2f} Bs")
    pdf.add_key_value("TOTAL DIARIO", f"{daily_costs['total']:,.2f} Bs")
    pdf.ln(2)

    # Table: Daily cost breakdown (Bs/day)
    headers = ["Categoría", "Costo Diario (Bs)"]
    data = [
        ["Diésel", f"{daily_costs['diesel']:,.2f}"],
        ["Mantenimiento", f"{daily_costs['maintenance']:,.2f}"],
        ["Desgaste", f"{daily_costs['wear']:,.2f}"],
        ["Personal", f"{daily_costs['personnel']:,.2f}"],
        ["Logística", f"{daily_costs['logistics']:,.2f}"],
        ["TOTAL", f"{daily_costs['total']:,.2f}"],
    ]
    pdf.add_table(headers, data, col_widths=[70, 73])
    
    # Cost per Unit
    pdf.section_title(f"Costo por {project.unit}")
    pdf.add_key_value("Costo Directo", f"{unit_cost_data['direct_cost_per_unit']:,.2f} Bs/{project.unit}")
    pdf.add_key_value("Movilizacion (amort.)", f"{unit_cost_data['mobilization_per_unit']:,.2f} Bs/{project.unit}")
    pdf.add_key_value("COSTO TOTAL", f"{unit_cost_data['cost_per_unit']:,.2f} Bs/{project.unit}")
    pdf.ln(3)

    # Unit cost breakdown table
    pdf.subsection_title(f"Desglose de costo por {project.unit}")
    try:
        b = unit_cost_data.get("breakdown", {}) or {}
        headers = ["Componente", f"Bs/{project.unit}"]
        data = []
        for k, v in b.items():
            try:
                data.append([str(k), f"{float(v):,.2f}"])
            except Exception:
                data.append([str(k), str(v)])
        # Ensure TOTAL appears as last row
        data.append(["TOTAL", f"{unit_cost_data.get('cost_per_unit', 0):,.2f}"])
        pdf.add_table(headers, data, col_widths=[70, 73])
    except Exception:
        pass
    
    # Margins
    pdf.section_title("Margenes")
    pdf.add_key_value("Precio de Venta", f"{economic.selling_price_per_unit:,.2f} Bs/{project.unit}")
    pdf.add_key_value("Ganancia Bruta", f"{margins['gross_profit']:,.2f} Bs/{project.unit}")
    pdf.add_key_value("Margen (%)", f"{margins['margin_pct']:.1f}%")
    
    if margins['margin_pct'] >= economic.target_margin_pct:
        pdf.add_highlight_box(
            f"El margen actual ({margins['margin_pct']:.1f}%) cumple o supera el objetivo ({economic.target_margin_pct:.1f}%)",
            "success"
        )
    else:
        pdf.add_highlight_box(
            f"ATENCION: El margen actual ({margins['margin_pct']:.1f}%) esta por debajo del objetivo ({economic.target_margin_pct:.1f}%)",
            "warning"
        )

    # Personnel details
    pdf.section_title("Detalle de Personal")
    headers = ["Rol", "Cant.", "Bs/día", "Costo Día (Bs)"]
    base_ops = personnel.operators_count * personnel.operators_daily_wage
    base_helpers = personnel.helpers_count * personnel.helpers_daily_wage
    base_sup = personnel.supervisors_count * personnel.supervisors_daily_wage
    base_total = base_ops + base_helpers + base_sup
    benefits = base_total * (personnel.social_benefits_pct / 100)
    data = [
        ["Operadores", personnel.operators_count, f"{personnel.operators_daily_wage:,.0f}", f"{base_ops:,.0f}"],
        ["Ayudantes", personnel.helpers_count, f"{personnel.helpers_daily_wage:,.0f}", f"{base_helpers:,.0f}"],
        ["Supervisores", personnel.supervisors_count, f"{personnel.supervisors_daily_wage:,.0f}", f"{base_sup:,.0f}"],
        [f"Beneficios ({personnel.social_benefits_pct:.0f}%)", "-", "-", f"{benefits:,.0f}"],
        ["TOTAL PERSONAL", "-", "-", f"{personnel.total_daily_cost:,.0f}"],
    ]
    pdf.add_table(headers, data, col_widths=[55, 18, 28, 42])

    # Logistics details
    pdf.section_title("Detalle de Logística")
    pdf.add_key_value("Movilización (único)", f"{logistics.mobilization_cost:,.2f} Bs")
    pdf.add_key_value("Desmovilización (único)", f"{logistics.demobilization_cost:,.2f} Bs")
    pdf.add_key_value("Combustible Veh. Apoyo (Bs/día)", f"{logistics.support_vehicles_fuel_daily:,.2f} Bs")
    pdf.add_key_value("Insumos varios (Bs/día)", f"{logistics.consumables_daily:,.2f} Bs")
    pdf.add_key_value("TOTAL Logística (Bs/día)", f"{logistics.daily_cost:,.2f} Bs")
    pdf.add_key_value("TOTAL Movilización+Desmov.", f"{logistics.total_mobilization_cost():,.2f} Bs")
    pdf.ln(2)

    # Margins per material (multi-material)
    pdf.section_title("Margen por Material")
    if materials and material_margin_df is not None and not material_margin_df.empty:
        pdf.subsection_title("Resultados por material (costo unitario compartido)")
        pdf.add_key_value(
            f"Costo unitario usado",
            f"{unit_cost_data['cost_per_unit']:,.2f} Bs/{project.unit}",
        )
        headers = [
            "Material",
            f"Prod/día ({project.unit})",
            f"Precio (Bs/{project.unit})",
            "Margen %",
            f"Gan./{project.unit} (Bs)",
            "Ingreso día (Bs)",
            "Ganancia día (Bs)",
        ]
        data = []
        for _, r in material_margin_df.iterrows():
            data.append([
                str(r.get("Material", ""))[:18],
                f"{float(r.get('Producción diaria', 0)):,.0f}",
                f"{float(r.get('Precio', 0)):,.2f}",
                f"{float(r.get('Margen (%)', 0)):.1f}%",
                f"{float(r.get('Ganancia por unidad', 0)):,.2f}",
                f"{float(r.get('Ingreso diario', 0)):,.0f}",
                f"{float(r.get('Ganancia diaria', 0)):,.0f}",
            ])
        pdf.add_table(headers, data, col_widths=[30, 22, 22, 14, 20, 17, 18])

        # Warn if any material is below target or negative
        try:
            below_target = material_margin_df[material_margin_df["Margen (%)"] < economic.target_margin_pct]
            negative = material_margin_df[material_margin_df["Margen (%)"] < 0]
            if not negative.empty:
                worst = negative.sort_values("Margen (%)").iloc[0]
                pdf.add_highlight_box(
                    f"ALERTA: Hay materiales con margen NEGATIVO. Peor caso: {worst['Material']} ({float(worst['Margen (%)']):.1f}%).",
                    "danger",
                )
            elif not below_target.empty:
                worst = below_target.sort_values("Margen (%)").iloc[0]
                pdf.add_highlight_box(
                    f"ATENCIÓN: Hay materiales por debajo del margen objetivo ({economic.target_margin_pct:.1f}%). Peor caso: {worst['Material']} ({float(worst['Margen (%)']):.1f}%).",
                    "warning",
                )
            else:
                pdf.add_highlight_box(
                    "✅ Todos los materiales cumplen o superan el margen objetivo.",
                    "success",
                )
        except Exception:
            pass
        # Project totals per material (compact)
        try:
            pdf.subsection_title("Totales por material (proyecto)")
            headers2 = ["Material", "Ingreso Proy. (Bs)", "Ganancia Proy. (Bs)"]
            data2 = []
            for _, r in material_margin_df.iterrows():
                data2.append([
                    str(r.get("Material", ""))[:22],
                    f"{float(r.get('Ingreso proyecto', 0)):,.0f}",
                    f"{float(r.get('Ganancia proyecto', 0)):,.0f}",
                ])
            pdf.add_table(headers2, data2, col_widths=[55, 44, 44])
        except Exception:
            pass
    else:
        pdf.add_highlight_box("No hay datos suficientes para calcular margen por material.", "warning")
    
    # Project totals
    pdf.section_title("Totales del Proyecto")
    total_revenue = project.total_production * economic.selling_price_per_unit
    total_cost = (daily_costs["total"] * project.duration_days) + logistics.total_mobilization_cost()
    total_profit = total_revenue - total_cost
    pdf.add_key_value("Ingresos Totales", f"{total_revenue:,.0f} Bs")
    pdf.add_key_value("Costos Totales", f"{total_cost:,.0f} Bs")
    pdf.add_key_value("Ganancia Total", f"{total_profit:,.0f} Bs")
    if total_revenue > 0:
        pdf.add_key_value("Margen del Proyecto", f"{(total_profit/total_revenue)*100:.1f}%")
    pdf.ln(2)

    # Scenarios - New Page
    pdf.add_page()
    pdf.section_title("Analisis de Escenarios")
    
    scenario_headers = ["Escenario", f"Prod. ({project.unit}/dia)", f"Costo/{project.unit}", "Margen %", "Ganancia Total"]
    scenario_data = []
    for name, data in scenarios.items():
        scenario_data.append([
            name,
            f"{data['daily_production']:,.0f}",
            f"{data['cost_per_unit']:,.2f} Bs",
            f"{data['margin_pct']:.1f}%",
            f"{data['total_project_profit']:,.0f} Bs",
        ])
    pdf.add_table(scenario_headers, scenario_data, col_widths=[35, 35, 35, 30, 45])
    
    # Sensitivity Analysis
    pdf.section_title("Sensibilidad al Precio del Diesel")
    sens_headers = ["Variacion", "Precio Diesel", f"Costo/{project.unit}", "Margen %"]
    sens_data = []
    for _, row in sensitivity_df.iterrows():
        sens_data.append([
            row["Variación Diésel"],
            f"{row['Precio Diésel (Bs/L)']:,.2f} Bs",
            f"{row['Costo por Unidad (Bs)']:,.2f} Bs",
            f"{row['Margen (%)']:.1f}%",
        ])
    pdf.add_table(sens_headers, sens_data, col_widths=[40, 45, 50, 45])
    
    return bytes(pdf.output())


# -----------------------
# BUSINESS PROPOSAL PDF
# -----------------------
class CrushingBusinessProposalPDF(FPDF):
    """Client-facing business proposal PDF."""

    def __init__(self, project_name: str = "Proyecto"):
        super().__init__()
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=15)
        self.effective_width = 183  # A4 width minus margins for portrait
        self.project_name = project_name

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, "PROPUESTA COMERCIAL", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 7, "SERVICIO DE TRITURACIÓN Y PRODUCCIÓN DE ÁRIDOS", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, self.project_name, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        # Ensure there is enough vertical space for a new section header
        # A4 height is 297mm; with 15mm bottom margin, avoid writing past ~282mm
        if self.get_y() > 270:
            self.add_page()

        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_fill_color(52, 73, 94)
        self.set_text_color(255, 255, 255)
        self.cell(self.effective_width, 7, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def add_paragraph(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(self.effective_width, 5, text)
        self.ln(1)

    def add_key_value(self, key: str, value: str):
        self.set_x(self.l_margin)
        key_width = 70
        value_width = self.effective_width - key_width
        self.set_font("Helvetica", "B", 9)
        self.cell(key_width, 6, key + ":", align="L")
        self.set_font("Helvetica", "", 9)
        self.cell(value_width, 6, value, align="L", new_x="LMARGIN", new_y="NEXT")

    def add_table(self, headers: list, data: list, col_widths: list | None = None):
        if col_widths is None:
            col_widths = [self.effective_width // len(headers)] * len(headers)
            col_widths[-1] = self.effective_width - sum(col_widths[:-1])

        total_width = sum(col_widths)
        if total_width > self.effective_width:
            scale = self.effective_width / total_width
            col_widths = [int(w * scale) for w in col_widths]

        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(236, 240, 241)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, border=1, fill=True, align="C")
        self.ln()

        self.set_font("Helvetica", "", 8)
        for row in data:
            self.set_x(self.l_margin)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 6, str(cell), border=1, align="C")
            self.ln()
        self.ln(2)


def generate_business_proposal_pdf(
    project: ProjectConfig,
    generator: GeneratorConfig,
    plant_equipment: dict[str, PlantEquipmentConfig],
    mobile_equipment: dict[str, MobileEquipmentConfig],
    proposal_materials: list[dict],
    company_name: str,
    company_tagline: str,
    client_name: str = "",
    payment_terms: str = "",
    validity_days: int = 7,
    notes: str = "",
) -> bytes:
    """Generate a client-facing proposal PDF.

    proposal_materials items must include:
      - name
      - total_quantity
      - unit_price
    """

    pdf = CrushingBusinessProposalPDF(project.name)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Intro
    pdf.section_title("Datos de la Propuesta")
    pdf.add_key_value("Empresa", company_name)
    if company_tagline.strip():
        pdf.add_key_value("Servicio", company_tagline)
    if client_name.strip():
        pdf.add_key_value("Cliente", client_name.strip())
    pdf.add_key_value("Proyecto", project.name)
    pdf.add_key_value("Unidad", project.unit)
    pdf.add_key_value("Validez", f"{int(validity_days)} días")
    pdf.ln(2)

    # Materials
    pdf.section_title("Materiales y Precios")
    headers = ["Material", f"Cantidad ({project.unit})", f"Precio (Bs/{project.unit})", "Total (Bs)"]
    rows = []
    grand_total = 0.0
    for m in proposal_materials:
        name = str(m.get("name", "")).strip() or "Material"
        qty = float(m.get("total_quantity", 0.0) or 0.0)
        price = float(m.get("unit_price", 0.0) or 0.0)
        line_total = qty * price
        grand_total += line_total
        rows.append([
            name[:30],
            f"{qty:,.0f}",
            f"{price:,.2f}",
            f"{line_total:,.0f}",
        ])

    pdf.add_table(headers, rows, col_widths=[70, 40, 40, 33])
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(pdf.l_margin)
    pdf.cell(pdf.effective_width, 7, f"TOTAL PROPUESTA: {grand_total:,.0f} Bs", border=1, align="C")
    pdf.ln(8)

    # Equipment list
    pdf.section_title("Equipos a Desplegar en el Proyecto")

    eq_headers = ["Equipo", "Cantidad", "Notas"]
    eq_rows = []

    if generator.enabled and generator.quantity > 0:
        eq_rows.append(["Generador (alimenta la planta)", str(int(generator.quantity)), "Diésel según horas de operación"]) 

    for _, eq in plant_equipment.items():
        if getattr(eq, "enabled", False) and int(getattr(eq, "quantity", 0) or 0) > 0:
            eq_rows.append([str(eq.name)[:45], str(int(eq.quantity)), "Equipo de planta"]) 

    for _, eq in mobile_equipment.items():
        if getattr(eq, "enabled", False) and int(getattr(eq, "quantity", 0) or 0) > 0:
            eq_rows.append([str(eq.name)[:45], str(int(eq.quantity)), "Equipo móvil"]) 

    if not eq_rows:
        eq_rows.append(["(Sin equipos seleccionados)", "-", ""]) 

    pdf.add_table(eq_headers, eq_rows, col_widths=[110, 25, 48])

    # Terms
    pdf.section_title("Condiciones")
    if payment_terms.strip():
        pdf.add_paragraph(f"Condiciones de pago: {payment_terms.strip()}")
    else:
        pdf.add_paragraph("Condiciones de pago: A convenir.")

    pdf.add_paragraph(
        "Alcance del servicio: movilización de planta móvil de trituración, instalación, operación, "
        "producción de materiales según especificación del proyecto y desmovilización al finalizar." 
    )

    if notes.strip():
        pdf.add_paragraph(f"Notas: {notes.strip()}")

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(
        pdf.effective_width,
        5,
        "Atentamente,\n\n______________________________\nRepresentante\n" + company_name,
    )

    return bytes(pdf.output())


def generate_excel_report(
    project: ProjectConfig,
    personnel: PersonnelConfig,
    logistics: LogisticsConfig,
    economic: EconomicConfig,
    equipment_costs: dict,
    daily_costs: dict,
    unit_cost_data: dict,
    margins: dict,
    scenarios: dict,
    sensitivity_df: pd.DataFrame,
    materials: list[dict],
    material_margin_df: pd.DataFrame,
) -> bytes:
    """Generate Excel report with multiple sheets."""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: Resumen
        summary_data = {
            "Concepto": [
                "Nombre del Proyecto",
                "Duración (días)",
                f"Producción Diaria ({project.unit})",
                f"Producción Total ({project.unit})",
                "Tipo de Material",
                "Precio Diésel (Bs/L)",
                f"Precio Venta (Bs/{project.unit})",
                "Margen Objetivo (%)",
                "---",
                f"Costo Total Diario (Bs)",
                f"Costo por {project.unit} (Bs)",
                "Ganancia por Unidad (Bs)",
                "Margen Real (%)",
            ],
            "Valor": [
                project.name,
                project.duration_days,
                project.daily_production,
                project.total_production,
                project.material_type,
                economic.diesel_price,
                economic.selling_price_per_unit,
                economic.target_margin_pct,
                "---",
                daily_costs["total"],
                unit_cost_data["cost_per_unit"],
                margins["gross_profit"],
                margins["margin_pct"],
            ],
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Resumen", index=False)
        # Sheet: Materiales (margen por material)
        if materials and material_margin_df is not None and not material_margin_df.empty:
            material_margin_df.to_excel(writer, sheet_name="Materiales", index=False)
        
        # Sheet 2: Costos Detallados por Equipo
        if equipment_costs["details"]:
            pd.DataFrame(equipment_costs["details"]).to_excel(
                writer, sheet_name="Costos Equipos", index=False
            )
        
        # Sheet 3: Desglose de Costos Diarios
        cost_breakdown = {
            "Categoría": ["Diésel", "Mantenimiento", "Desgaste", "Personal", "Logística", "TOTAL"],
            "Costo Diario (Bs)": [
                daily_costs["diesel"],
                daily_costs["maintenance"],
                daily_costs["wear"],
                daily_costs["personnel"],
                daily_costs["logistics"],
                daily_costs["total"],
            ],
            f"Costo por {project.unit} (Bs)": [
                unit_cost_data["breakdown"].get("Diésel", 0),
                unit_cost_data["breakdown"].get("Mantenimiento", 0),
                unit_cost_data["breakdown"].get("Desgaste", 0),
                unit_cost_data["breakdown"].get("Personal", 0),
                unit_cost_data["breakdown"].get("Logística", 0),
                unit_cost_data["cost_per_unit"],
            ],
        }
        pd.DataFrame(cost_breakdown).to_excel(writer, sheet_name="Desglose Costos", index=False)
        
        # Sheet 4: Escenarios
        scenarios_data = []
        for name, data in scenarios.items():
            scenarios_data.append({
                "Escenario": name,
                f"Producción Diaria ({project.unit})": data["daily_production"],
                "Costo Diario (Bs)": data["daily_cost"],
                f"Costo por {project.unit} (Bs)": data["cost_per_unit"],
                f"Precio Venta (Bs/{project.unit})": data["selling_price"],
                f"Ganancia por {project.unit} (Bs)": data["gross_profit"],
                "Margen (%)": data["margin_pct"],
                "Ingresos Totales (Bs)": data["total_project_revenue"],
                "Costos Totales (Bs)": data["total_project_cost"],
                "Ganancia Total (Bs)": data["total_project_profit"],
            })
        pd.DataFrame(scenarios_data).to_excel(writer, sheet_name="Escenarios", index=False)
        
        # Sheet 5: Sensibilidad Diésel
        sensitivity_df.to_excel(writer, sheet_name="Sensibilidad Diesel", index=False)
        
        # Sheet 6: Personal
        personnel_data = {
            "Rol": ["Operadores", "Ayudantes", "Supervisores", "Beneficios Sociales", "TOTAL"],
            "Cantidad": [
                personnel.operators_count,
                personnel.helpers_count,
                personnel.supervisors_count,
                "-",
                personnel.operators_count + personnel.helpers_count + personnel.supervisors_count,
            ],
            "Salario/día (Bs)": [
                personnel.operators_daily_wage,
                personnel.helpers_daily_wage,
                personnel.supervisors_daily_wage,
                f"{personnel.social_benefits_pct}%",
                "-",
            ],
            "Costo Diario (Bs)": [
                personnel.operators_count * personnel.operators_daily_wage,
                personnel.helpers_count * personnel.helpers_daily_wage,
                personnel.supervisors_count * personnel.supervisors_daily_wage,
                personnel.base_daily_cost * (personnel.social_benefits_pct / 100),
                personnel.total_daily_cost,
            ],
        }
        pd.DataFrame(personnel_data).to_excel(writer, sheet_name="Personal", index=False)
    
    return output.getvalue()


# -----------------------
# Streamlit App
# -----------------------
def main():
    st.set_page_config(
        page_title="Análisis Económico de Trituración",
        page_icon="🪨",
        layout="wide",
    )
    init_scenarios_db()
    st.title("🪨 Análisis Económico de Servicios de Trituración")
    st.markdown("**Para proyectos carreteros**")
    st.divider()
    
    # -----------------------
    # SIDEBAR - Inputs
    # -----------------------
    with st.sidebar:
        st.header("⚙️ Configuración del Proyecto")
        
        # Project Data
        with st.expander("📋 Datos del Proyecto", expanded=True):
            project_name = st.text_input("Nombre del Proyecto", value="Proyecto Carretero ABC")
            duration_days = st.number_input("Duración (días)", min_value=1, value=143, step=1)
            # Remove single-material input for daily_production
            # daily_production = st.number_input("Producción Diaria", min_value=1.0, value=500.0, step=10.0)
            unit = st.selectbox("Unidad de Medida", ["m³", "tonelada"])

            st.divider()
            st.subheader("🧱 Materiales (múltiples)")
            st.caption(
                "Ingresa los materiales que producirás en el día (capacidad en un día perfecto). "
                "Luego aplica un factor de disponibilidad para simular paradas por mantenimiento y problemas."
            )

            availability_pct = st.slider(
                "Disponibilidad operativa del día (%)",
                min_value=50,
                max_value=100,
                value=85,
                step=1,
                help=(
                    "100% = día perfecto sin paradas. Valores menores simulan tiempo perdido por mantenimiento, "
                    "clima, atascos, falta de volquetas, etc. La producción efectiva se reduce, pero los costos diarios "
                    "se mantienen (en general), por lo que sube el costo por unidad."
                ),
            )
            availability_factor = availability_pct / 100.0
            st.caption(
                f"Producción efectiva = Producción ideal × {availability_pct}% (disponibilidad)."
            )

            n_materials = st.number_input(
                "Cantidad de materiales",
                min_value=1,
                max_value=10,
                value=5,
                step=1,
                key="n_materials",
            )

            materials = []

            # Compact header row (prevents long labels from wrapping in the sidebar)
            h1, h2, h3 = st.columns([2.2, 1, 1])
            with h1:
                st.markdown("**Nombre**")
            with h2:
                st.markdown(f"**Prod ({unit}/día)**")
            with h3:
                st.markdown(f"**Precio (Bs/{unit})**")

            default_materials = [
                {"name": "Sub base", "prod": 500.0, "price": 45.0},
                {"name": "Capa base 1", "prod": 350.0, "price": 65.0},
                {"name": "Arena lavada", "prod": 150.0, "price": 90.0},
                {"name": "Grava chancada 3/8", "prod": 150.0, "price": 90.0},
                {"name": "Chip 3/8 - 1/2 - 3/4 CARPETA", "prod": 300.0, "price": 130.0},
            ]

            for i in range(int(n_materials)):
                with st.expander(f"Material {i+1}", expanded=(i < 2)):
                    c1, c2, c3 = st.columns([2.2, 1, 1])
                    defaults = default_materials[i] if i < len(default_materials) else {
                        "name": f"Material {i+1}",
                        "prod": 0.0,
                        "price": 0.0,
                    }
                    with c1:
                        m_name = st.text_input(
                            "Nombre",
                            value=defaults["name"],
                            key=f"mat_{i}_name",
                            label_visibility="collapsed",
                            placeholder="Ej: Grava 3/4",
                        )
                    with c2:
                        m_prod = st.number_input(
                            "Producción",
                            min_value=0.0,
                            value=defaults["prod"],
                            step=10.0,
                            key=f"mat_{i}_prod",
                            label_visibility="collapsed",
                        )
                    with c3:
                        m_price = st.number_input(
                            "Precio",
                            min_value=0.0,
                            value=defaults["price"],
                            step=1.0,
                            format="%.2f",
                            key=f"mat_{i}_price",
                            label_visibility="collapsed",
                        )

                    materials.append({
                        "name": (m_name or f"Material {i+1}").strip(),
                        "daily_production": float(m_prod),
                        "selling_price": float(m_price),
                    })
            # Filter invalid rows
            materials = [m for m in materials if m["daily_production"] > 0 and m["selling_price"] > 0 and m["name"]]

            # Derive a project material label from the entered materials
            material_names = [m["name"] for m in materials]
            material_type = ", ".join(material_names)
            if len(material_type) > 80:
                material_type = material_type[:77] + "..."

            if not materials:
                st.error("Agrega al menos 1 material con producción > 0 y precio > 0.")
                st.stop()

            total_daily_production_ideal = sum(m["daily_production"] for m in materials)

            # Apply availability factor: effective production is lower than the "perfect day" inputs
            materials_effective = []
            for m in materials:
                materials_effective.append({
                    "name": m["name"],
                    "daily_production": float(m["daily_production"]) * availability_factor,
                    "selling_price": float(m["selling_price"]),
                })

            total_daily_production = sum(m["daily_production"] for m in materials_effective)

            weighted_avg_price = (
                sum(m["daily_production"] * m["selling_price"] for m in materials_effective) / total_daily_production
                if total_daily_production > 0
                else 0.0
            )

            st.info(
                f"**Producción ideal:** {total_daily_production_ideal:,.0f} {unit}/día  |  "
                f"**Disponibilidad:** {availability_pct}%  |  "
                f"**Producción efectiva:** {total_daily_production:,.0f} {unit}/día  |  "
                f"**Precio promedio ponderado:** {weighted_avg_price:,.2f} Bs/{unit}"
            )

            st.dataframe(
                pd.DataFrame(materials_effective).rename(columns={
                    "name": "Material",
                    "daily_production": f"Producción ({unit}/día)",
                    "selling_price": f"Precio (Bs/{unit})",
                }),
                use_container_width=True,
                hide_index=True,
            )

            # Backwards-compatible variables for the rest of the app (for now)
            daily_production = total_daily_production
            selling_price = weighted_avg_price
            materials_for_calc = materials_effective

            # -----------------------
            # Proposal Inputs (client-facing)
            # -----------------------
            st.divider()
            st.subheader("🧾 Propuesta Comercial")
            st.caption(
                "Define la **cantidad total** por material para el proyecto y el **precio unitario** que ofrecerás al cliente. "
                "Estos valores se usarán para generar un PDF de propuesta comercial."
            )

            client_name = st.text_input("Cliente (opcional)", value="", key="proposal_client")
            validity_days = st.number_input("Validez de la oferta (días)", min_value=1, value=7, step=1, key="proposal_validity")
            payment_terms = st.text_input("Condiciones de pago (opcional)", value="", key="proposal_payment_terms")
            proposal_notes = st.text_area("Notas / Alcance adicional (opcional)", value="", height=90, key="proposal_notes")

            st.markdown("**Materiales para la propuesta**")
            proposal_materials = []
            for i, m in enumerate(materials):
                # Use the original (ideal) materials list so the user can define contractual quantities
                m_name = str(m.get("name", "")).strip() or f"Material {i+1}"
                # Default to effective daily production * duration (a reasonable starting point)
                default_qty = float(m.get("daily_production", 0.0)) * float(duration_days) * availability_factor
                default_price = float(m.get("selling_price", 0.0))

                with st.expander(f"Propuesta: {m_name}", expanded=(i < 2)):
                    pc1, pc2 = st.columns([1.2, 1])
                    with pc1:
                        total_qty = st.number_input(
                            f"Cantidad total ({unit})",
                            min_value=0.0,
                            value=max(0.0, default_qty),
                            step=100.0,
                            key=f"proposal_qty_{i}",
                        )
                    with pc2:
                        unit_price = st.number_input(
                            f"Precio unitario (Bs/{unit})",
                            min_value=0.0,
                            value=max(0.0, default_price),
                            step=1.0,
                            format="%.2f",
                            key=f"proposal_price_{i}",
                        )

                    proposal_materials.append({
                        "name": m_name,
                        "total_quantity": float(total_qty),
                        "unit_price": float(unit_price),
                    })

            # Remove empty rows
            proposal_materials = [pm for pm in proposal_materials if pm["total_quantity"] > 0 and pm["unit_price"] > 0]
            if proposal_materials:
                proposal_total = sum(pm["total_quantity"] * pm["unit_price"] for pm in proposal_materials)
                st.info(f"Total estimado propuesta: **{proposal_total:,.0f} Bs**")
            else:
                st.warning("Agrega al menos 1 material con cantidad total > 0 y precio unitario > 0 para generar la propuesta.")
        
        # Economic Variables
        with st.expander("💰 Variables Económicas", expanded=True):
            diesel_price = st.number_input(
                "Precio del Diésel (Bs/L)",
                min_value=0.01,
                value=9.8,
                step=0.01,
                format="%.2f"
            )
            default_selling_price = st.number_input(
                f"Precio de Venta (referencia) (Bs/{unit})",
                min_value=0.01,
                value=50.0,
                step=1.0,
                format="%.2f"
            )
            st.caption("Nota: el precio real usado en los cálculos viene del promedio ponderado de los materiales.")
            target_margin = st.number_input(
                "Margen Objetivo (%)",
                min_value=0.0,
                max_value=100.0,
                value=40.0,
                step=1.0
            )
        
        # Personnel
        with st.expander("👷 Personal", expanded=False):
            operators_count = st.number_input("Operadores (cantidad)", min_value=0, value=4, step=1)
            operators_wage = st.number_input("Salario Operador (Bs/día)", min_value=0.0, value=200.0, step=10.0)
            helpers_count = st.number_input("Ayudantes (cantidad)", min_value=0, value=6, step=1)
            helpers_wage = st.number_input("Salario Ayudante (Bs/día)", min_value=0.0, value=130.0, step=10.0)
            supervisors_count = st.number_input("Supervisores (cantidad)", min_value=0, value=1, step=1)
            supervisors_wage = st.number_input("Salario Supervisor (Bs/día)", min_value=0.0, value=300.0, step=10.0)
            social_benefits = st.number_input("Beneficios Sociales (%)", min_value=0.0, value=30.0, step=5.0)
        
        # Logistics
        with st.expander("🚚 Logística y Transporte", expanded=False):
            mobilization_cost = st.number_input(
                "Costo Movilización (Bs)", min_value=0.0, value=50000.0, step=1000.0
            )
            demobilization_cost = st.number_input(
                "Costo Desmovilización (Bs)", min_value=0.0, value=30000.0, step=1000.0
            )
            support_fuel = st.number_input(
                "Combustible Vehículos Apoyo (Bs/día)", min_value=0.0, value=500.0, step=50.0
            )
            consumables = st.number_input(
                "Insumos Varios (Bs/día)", min_value=0.0, value=300.0, step=50.0
            )
    
    # -----------------------
    # MAIN AREA - Equipment Configuration
    # -----------------------
    st.header("🔧 Configuración de Equipos")
    
    # Get defaults
    default_plant = get_default_plant_equipment()
    default_mobile = get_default_mobile_equipment()
    default_gen = get_default_generator()
    
    # ======================
    # GENERATOR SECTION
    # ======================
    st.subheader("⚡ Generador (Alimenta la Planta)")
    st.caption("El generador provee energía eléctrica a todos los equipos de la planta de trituración.")
    
    with st.expander("**Configuración del Generador**", expanded=True):
        gen_enabled = st.checkbox("Generador Habilitado", value=True, key="gen_enabled")

        if gen_enabled:
            gc1, gc2, gc3, gc4, gc5 = st.columns(5)
            with gc1:
                gen_qty = st.number_input(
                    "Cantidad de Generadores",
                    min_value=1,
                    value=default_gen.quantity,
                    step=1,
                    key="gen_qty"
                )
            with gc2:
                gen_diesel = st.number_input(
                    "Consumo Diésel (L/h)",
                    min_value=0.0,
                    value=default_gen.diesel_consumption_lph,
                    step=5.0,
                    key="gen_diesel"
                )
            with gc3:
                gen_hours = st.number_input(
                    "Horas Operación/día",
                    min_value=0.0,
                    max_value=24.0,
                    value=default_gen.operation_hours_day,
                    step=0.5,
                    key="gen_hours"
                )
            with gc4:
                gen_maint = st.number_input(
                    "Mantenimiento (Bs/h)",
                    min_value=0.0,
                    value=default_gen.maintenance_cost_ph,
                    step=5.0,
                    key="gen_maint"
                )
            with gc5:
                gen_wear = st.number_input(
                    "Desgaste (Bs/h)",
                    min_value=0.0,
                    value=default_gen.wear_cost_ph,
                    step=5.0,
                    key="gen_wear"
                )
        else:
            gen_qty = 0
            gen_diesel = 0.0
            gen_hours = 0.0
            gen_maint = 0.0
            gen_wear = 0.0

    generator = GeneratorConfig(
        enabled=gen_enabled,
        quantity=gen_qty if gen_enabled else 0,
        diesel_consumption_lph=gen_diesel,
        operation_hours_day=gen_hours,
        maintenance_cost_ph=gen_maint,
        wear_cost_ph=gen_wear,
    )
    
    # ======================
    # PLANT EQUIPMENT (Powered by Generator)
    # ======================
    st.subheader("🏭 Equipos de Planta (Alimentados por Generador)")
    st.caption("Estos equipos NO consumen diésel directamente - son alimentados por el generador.")
    
    plant_equipment = {}
    cols = st.columns(2)
    
    for idx, (key, default_eq) in enumerate(default_plant.items()):
        col = cols[idx % 2]
        with col:
            with st.expander(f"**{default_eq.name}**", expanded=True):
                enabled = st.checkbox("Habilitado", value=True, key=f"plant_{key}_enabled")
                
                if enabled:
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        quantity = st.number_input(
                            "Cantidad",
                            min_value=1,
                            value=default_eq.quantity,
                            step=1,
                            key=f"plant_{key}_qty"
                        )
                        hours = st.number_input(
                            "Horas Operación/día",
                            min_value=0.0,
                            max_value=24.0,
                            value=default_eq.operation_hours_day,
                            step=0.5,
                            key=f"plant_{key}_hours"
                        )
                    with c2:
                        maintenance = st.number_input(
                            "Mantenimiento (Bs/h)",
                            min_value=0.0,
                            value=default_eq.maintenance_cost_ph,
                            step=1.0,
                            key=f"plant_{key}_maint"
                        )
                    with c3:
                        wear = st.number_input(
                            "Desgaste (Bs/h)",
                            min_value=0.0,
                            value=default_eq.wear_cost_ph,
                            step=1.0,
                            key=f"plant_{key}_wear"
                        )
                    # c4 is unused
                else:
                    quantity = 0
                    hours = 0.0
                    maintenance = 0.0
                    wear = 0.0
                
                plant_equipment[key] = PlantEquipmentConfig(
                    name=default_eq.name,
                    enabled=enabled,
                    quantity=quantity if enabled else 0,
                    operation_hours_day=hours,
                    maintenance_cost_ph=maintenance,
                    wear_cost_ph=wear,
                )
    
    # ======================
    # MOBILE EQUIPMENT (Uses Diesel Directly)
    # ======================
    st.subheader("🚜 Equipos Móviles (Consumen Diésel)")
    st.caption("Estos equipos consumen diésel directamente para su operación.")
    
    mobile_equipment = {}
    cols = st.columns(2)
    
    for idx, (key, default_eq) in enumerate(default_mobile.items()):
        col = cols[idx % 2]
        with col:
            with st.expander(f"**{default_eq.name}**", expanded=True):
                enabled = st.checkbox("Habilitado", value=True, key=f"mobile_{key}_enabled")
                
                if enabled:
                    # First row: quantity and diesel
                    mc1, mc2 = st.columns(2)
                    with mc1:
                        quantity = st.number_input(
                            "Cantidad",
                            min_value=1,
                            value=default_eq.quantity,
                            step=1,
                            key=f"mobile_{key}_qty"
                        )
                    with mc2:
                        diesel = st.number_input(
                            "Consumo Diésel (L/h c/u)",
                            min_value=0.0,
                            value=default_eq.diesel_consumption_lph,
                            step=1.0,
                            key=f"mobile_{key}_diesel"
                        )
                    
                    # Second row: hours, maintenance, wear
                    mc3, mc4, mc5 = st.columns(3)
                    with mc3:
                        hours = st.number_input(
                            "Horas Operación/día",
                            min_value=0.0,
                            max_value=24.0,
                            value=default_eq.operation_hours_day,
                            step=0.5,
                            key=f"mobile_{key}_hours"
                        )
                    with mc4:
                        maintenance = st.number_input(
                            "Mantenimiento (Bs/h c/u)",
                            min_value=0.0,
                            value=default_eq.maintenance_cost_ph,
                            step=1.0,
                            key=f"mobile_{key}_maint"
                        )
                    with mc5:
                        wear = st.number_input(
                            "Desgaste (Bs/h c/u)",
                            min_value=0.0,
                            value=default_eq.wear_cost_ph,
                            step=1.0,
                            key=f"mobile_{key}_wear"
                        )
                else:
                    quantity = 0
                    diesel = 0.0
                    hours = 0.0
                    maintenance = 0.0
                    wear = 0.0
                
                mobile_equipment[key] = MobileEquipmentConfig(
                    name=default_eq.name,
                    enabled=enabled,
                    quantity=quantity if enabled else 0,
                    diesel_consumption_lph=diesel,
                    operation_hours_day=hours,
                    maintenance_cost_ph=maintenance,
                    wear_cost_ph=wear,
                )
    
    # Create config objects
    project = ProjectConfig(
        name=project_name,
        duration_days=duration_days,
        daily_production=daily_production,
        material_type=material_type,
        unit=unit,
    )
    
    personnel = PersonnelConfig(
        operators_count=operators_count,
        operators_daily_wage=operators_wage,
        helpers_count=helpers_count,
        helpers_daily_wage=helpers_wage,
        supervisors_count=supervisors_count,
        supervisors_daily_wage=supervisors_wage,
        social_benefits_pct=social_benefits,
    )
    
    logistics = LogisticsConfig(
        mobilization_cost=mobilization_cost,
        demobilization_cost=demobilization_cost,
        support_vehicles_fuel_daily=support_fuel,
        consumables_daily=consumables,
    )
    
    economic = EconomicConfig(
        diesel_price=diesel_price,
        selling_price_per_unit=selling_price,
        target_margin_pct=target_margin,
    )
    
    # -----------------------
    # CALCULATIONS
    # -----------------------
    st.divider()
    st.header("📊 Resultados del Análisis")
    
    # Calculate all costs
    equipment_costs = calculate_all_equipment_costs(
        plant_equipment, mobile_equipment, generator, diesel_price
    )
    daily_costs = calculate_total_daily_cost(equipment_costs, personnel, logistics)
    unit_cost_data = calculate_unit_cost(
        daily_costs,
        daily_production,
        duration_days,
        logistics.total_mobilization_cost(),
    )
    margins = calculate_margins(unit_cost_data["cost_per_unit"], selling_price)

    # -----------------------
    # Per-material margins (multi-material)
    # Note: cost per unit is shared across materials because costs are shared;
    # the margin differs by each material's selling price.
    cost_per_unit_shared = float(unit_cost_data.get("cost_per_unit", 0.0))
    mat_rows = []
    for m in materials_for_calc:
        m_name = str(m.get("name", "")).strip() or "Material"
        m_prod = float(m.get("daily_production", 0.0))
        m_price = float(m.get("selling_price", 0.0))
        if m_prod <= 0 or m_price <= 0:
            continue
        m_profit_unit = m_price - cost_per_unit_shared
        m_margin_pct = (m_profit_unit / m_price) * 100 if m_price > 0 else 0.0
        mat_rows.append({
            "Material": m_name,
            "Producción diaria": m_prod,
            "Precio": m_price,
            f"Costo por {unit}": cost_per_unit_shared,
            "Ganancia por unidad": m_profit_unit,
            "Margen (%)": m_margin_pct,
            "Ingreso diario": m_price * m_prod,
            "Ganancia diaria": m_profit_unit * m_prod,
            "Ingreso proyecto": (m_price * m_prod) * duration_days,
            "Ganancia proyecto": (m_profit_unit * m_prod) * duration_days,
        })

    material_margin_df = pd.DataFrame(mat_rows)
    if not material_margin_df.empty:
        # Order by worst margin first to surface problems
        material_margin_df = material_margin_df.sort_values("Margen (%)").reset_index(drop=True)
    
    # Display Results in Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Resumen", 
        "🎯 Escenarios", 
        "⛽ Sensibilidad Diésel",
        "📋 Detalles"
    ])
    
    # -----------------------
    # TAB 1: Summary
    # -----------------------
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Costo Total Diario",
                f"{daily_costs['total']:,.2f} Bs"
            )
        with col2:
            st.metric(
                f"Costo por {unit}",
                f"{unit_cost_data['cost_per_unit']:,.2f} Bs"
            )
        with col3:
            margin_delta = margins["margin_pct"] - target_margin
            st.metric(
                "Margen de Ganancia",
                f"{margins['margin_pct']:.1f}%",
                delta=f"{margin_delta:+.1f}% vs objetivo"
            )
        with col4:
            st.metric(
                f"Ganancia por {unit}",
                f"{margins['gross_profit']:,.2f} Bs"
            )

        # --- Per-material margin reporting ---
        st.subheader("🧱 Margen por material")
        st.caption(
            "El **costo por unidad** se calcula con el costo total del día dividido entre la producción total (incluye movilización amortizada). "
            "Luego se calcula el margen individual usando el precio de cada material."
        )

        if material_margin_df is None or material_margin_df.empty:
            st.warning("No se pudo calcular el margen por material.")
        else:
            worst = material_margin_df.iloc[0]
            if float(worst["Margen (%)"]) < 0:
                st.error(
                    f"❌ Hay un material con **margen negativo**. Peor caso: **{worst['Material']}** "
                    f"({float(worst['Margen (%)']):.1f}%)."
                )
            elif float(worst["Margen (%)"]) < target_margin:
                st.warning(
                    f"⚠️ Hay materiales por debajo del margen objetivo ({target_margin}%). Peor caso: **{worst['Material']}** "
                    f"({float(worst['Margen (%)']):.1f}%)."
                )
            else:
                st.success("✅ Todos los materiales cumplen o superan el margen objetivo.")

            st.dataframe(
                material_margin_df.style.format({
                    "Producción diaria": "{:,.0f}",
                    "Precio": "{:,.2f}",
                    f"Costo por {unit}": "{:,.2f}",
                    "Ganancia por unidad": "{:,.2f}",
                    "Margen (%)": "{:.1f}",
                    "Ingreso diario": "{:,.0f}",
                    "Ganancia diaria": "{:,.0f}",
                    "Ingreso proyecto": "{:,.0f}",
                    "Ganancia proyecto": "{:,.0f}",
                }),
                use_container_width=True,
                hide_index=True,
            )
        st.divider()

        # Cost Breakdown Chart
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Desglose de Costos Diarios")
            cost_data = {
                "Categoría": ["Diésel", "Mantenimiento", "Desgaste", "Personal", "Logística"],
                "Costo (Bs)": [
                    daily_costs["diesel"],
                    daily_costs["maintenance"],
                    daily_costs["wear"],
                    daily_costs["personnel"],
                    daily_costs["logistics"],
                ]
            }
            fig_pie = px.pie(
                cost_data,
                values="Costo (Bs)",
                names="Categoría",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            st.subheader(f"Composición del Costo por {unit}")
            breakdown_data = {
                "Componente": list(unit_cost_data["breakdown"].keys()),
                "Bs": list(unit_cost_data["breakdown"].values())
            }
            fig_bar = px.bar(
                breakdown_data,
                x="Componente",
                y="Bs",
                color="Componente",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Project Totals
        st.subheader("Resumen del Proyecto Completo")
        total_revenue = project.total_production * selling_price
        total_cost = (daily_costs["total"] * duration_days) + logistics.total_mobilization_cost()
        total_profit = total_revenue - total_cost
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Ingresos Totales", f"{total_revenue:,.0f} Bs")
        with col2:
            st.metric("Costos Totales", f"{total_cost:,.0f} Bs")
        with col3:
            st.metric(
                "Ganancia Total",
                f"{total_profit:,.0f} Bs",
                delta=f"{(total_profit/total_revenue)*100:.1f}% del ingreso" if total_revenue > 0 else "N/A"
            )
    
    # -----------------------
    # TAB 2: Scenarios
    # -----------------------
    with tab2:
        st.subheader("Análisis de Escenarios")
        
        scenarios = {
            "Optimista": calculate_scenario(
                daily_costs, daily_production, 0.15, -0.10,
                duration_days, logistics.total_mobilization_cost(), selling_price
            ),
            "Real": calculate_scenario(
                daily_costs, daily_production, 0.0, 0.0,
                duration_days, logistics.total_mobilization_cost(), selling_price
            ),
            "Pesimista": calculate_scenario(
                daily_costs, daily_production, -0.20, 0.15,
                duration_days, logistics.total_mobilization_cost(), selling_price
            ),
        }

        st.divider()
        st.subheader("💾 Guardar / Cargar Escenarios")

        # Build a payload that captures inputs + computed scenarios
        payload = {
            "project": {
                "name": project.name,
                "duration_days": int(project.duration_days),
                "daily_production": float(project.daily_production),
                "unit": project.unit,
                "material_type": project.material_type,
                "availability_pct": int(availability_pct),
                "materials_ideal": materials,
                "materials": materials_for_calc,
            },
            "economic": {
                "diesel_price": float(economic.diesel_price),
                "selling_price_per_unit": float(economic.selling_price_per_unit),
                "target_margin_pct": float(economic.target_margin_pct),
            },
            "personnel": {
                "operators_count": int(personnel.operators_count),
                "operators_daily_wage": float(personnel.operators_daily_wage),
                "helpers_count": int(personnel.helpers_count),
                "helpers_daily_wage": float(personnel.helpers_daily_wage),
                "supervisors_count": int(personnel.supervisors_count),
                "supervisors_daily_wage": float(personnel.supervisors_daily_wage),
                "social_benefits_pct": float(personnel.social_benefits_pct),
            },
            "logistics": {
                "mobilization_cost": float(logistics.mobilization_cost),
                "demobilization_cost": float(logistics.demobilization_cost),
                "support_vehicles_fuel_daily": float(logistics.support_vehicles_fuel_daily),
                "consumables_daily": float(logistics.consumables_daily),
            },
            "results": {
                "scenarios": scenarios,
            },
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }

        c_save, c_load = st.columns([1, 2])
        with c_save:
            default_name = f"{project.name} - {datetime.now().strftime('%d/%m %H:%M')}"
            scenario_name = st.text_input("Nombre para guardar", value=default_name)
            if st.button("Guardar escenarios", type="primary"):
                if not scenario_name.strip():
                    st.error("Pon un nombre válido.")
                else:
                    save_scenario_to_db(scenario_name, payload)
                    st.success("Escenarios guardados ✅")

        with c_load:
            saved_df = list_saved_scenarios()
            if saved_df.empty:
                st.info("Aún no hay escenarios guardados.")
            else:
                # Create a human-friendly label
                saved_df["label"] = saved_df.apply(
                    lambda r: f"#{int(r['id'])} — {r['name']} ({r['created_at']})",
                    axis=1,
                )
                selected_label = st.selectbox("Cargar escenario guardado", saved_df["label"].tolist())
                selected_id = int(saved_df.loc[saved_df["label"] == selected_label, "id"].iloc[0])
                loaded = load_scenario_payload(selected_id)

                with st.expander("Ver datos guardados", expanded=False):
                    st.json(loaded)

                # Quick compare table if present
                try:
                    loaded_scen = loaded.get("results", {}).get("scenarios", {})
                    if loaded_scen:
                        compare_rows = []
                        for name, data in loaded_scen.items():
                            compare_rows.append({
                                "Escenario": name,
                                f"Prod. ({loaded.get('project', {}).get('unit', unit)}/día)": data.get("daily_production"),
                                "Costo/Unidad (Bs)": data.get("cost_per_unit"),
                                "Margen (%)": data.get("margin_pct"),
                                "Ganancia Total (Bs)": data.get("total_project_profit"),
                            })
                        st.dataframe(pd.DataFrame(compare_rows), use_container_width=True)
                except Exception:
                    st.warning("No se pudo construir la tabla de comparación para este escenario guardado.")

        # Scenario Cards
        cols = st.columns(3)
        for idx, (name, data) in enumerate(scenarios.items()):
            with cols[idx]:
                if name == "Optimista":
                    st.success(f"### {name}")
                elif name == "Pesimista":
                    st.error(f"### {name}")
                else:
                    st.info(f"### {name}")
                
                st.write(f"**Producción:** {data['daily_production']:,.0f} {unit}/día")
                st.write(f"**Costo por {unit}:** {data['cost_per_unit']:,.2f} Bs")
                st.write(f"**Margen:** {data['margin_pct']:.1f}%")
                st.write(f"**Ganancia Total:** {data['total_project_profit']:,.0f} Bs")
        
        # Scenario Comparison Chart
        st.divider()
        scenario_df = pd.DataFrame([
            {"Escenario": name, "Ganancia Total (Bs)": data["total_project_profit"], "Margen (%)": data["margin_pct"]}
            for name, data in scenarios.items()
        ])
        
        fig_scenario = go.Figure()
        fig_scenario.add_trace(go.Bar(
            x=scenario_df["Escenario"],
            y=scenario_df["Ganancia Total (Bs)"],
            name="Ganancia Total",
            marker_color=["#2ecc71", "#3498db", "#e74c3c"]
        ))
        fig_scenario.update_layout(
            title="Comparación de Ganancias por Escenario",
            xaxis_title="Escenario",
            yaxis_title="Ganancia Total (Bs)",
        )
        st.plotly_chart(fig_scenario, use_container_width=True)
    
    # -----------------------
    # TAB 3: Diesel Sensitivity
    # -----------------------
    with tab3:
        st.subheader("Sensibilidad al Precio del Diésel")
        
        diesel_variations = [-0.20, -0.10, 0.0, 0.10, 0.20, 0.30]
        sensitivity_df = calculate_diesel_sensitivity(
            plant_equipment, mobile_equipment, generator,
            personnel, logistics, project, economic, diesel_variations
        )
        
        # Display table
        st.dataframe(
            sensitivity_df.style.format({
                "Precio Diésel (Bs/L)": "{:.2f}",
                "Costo por Unidad (Bs)": "{:.2f}",
                "Margen (%)": "{:.1f}",
                "Ganancia por Unidad (Bs)": "{:.2f}",
            }),
            use_container_width=True
        )
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            fig_cost = go.Figure()
            fig_cost.add_trace(go.Scatter(
                x=sensitivity_df["Precio Diésel (Bs/L)"],
                y=sensitivity_df["Costo por Unidad (Bs)"],
                mode="lines+markers",
                name=f"Costo por {unit}",
                line=dict(color="#e74c3c", width=3)
            ))
            fig_cost.update_layout(
                title=f"Costo por {unit} vs Precio Diésel",
                xaxis_title="Precio Diésel (Bs/L)",
                yaxis_title=f"Costo por {unit} (Bs)",
            )
            st.plotly_chart(fig_cost, use_container_width=True)
        
        with col2:
            fig_margin = go.Figure()
            fig_margin.add_trace(go.Scatter(
                x=sensitivity_df["Precio Diésel (Bs/L)"],
                y=sensitivity_df["Margen (%)"],
                mode="lines+markers",
                name="Margen",
                line=dict(color="#2ecc71", width=3)
            ))
            # Add target margin line
            fig_margin.add_hline(
                y=target_margin,
                line_dash="dash",
                line_color="orange",
                annotation_text=f"Objetivo: {target_margin}%"
            )
            fig_margin.update_layout(
                title="Margen vs Precio Diésel",
                xaxis_title="Precio Diésel (Bs/L)",
                yaxis_title="Margen (%)",
            )
            st.plotly_chart(fig_margin, use_container_width=True)
        
        # Break-even diesel price
        st.divider()
        st.subheader("Punto de Equilibrio del Diésel")
        
        # Find diesel price where margin = 0
        # This is an approximation based on linear interpolation
        for i in range(len(sensitivity_df) - 1):
            m1 = sensitivity_df.iloc[i]["Margen (%)"]
            m2 = sensitivity_df.iloc[i + 1]["Margen (%)"]
            if m1 >= 0 and m2 < 0:
                d1 = sensitivity_df.iloc[i]["Precio Diésel (Bs/L)"]
                d2 = sensitivity_df.iloc[i + 1]["Precio Diésel (Bs/L)"]
                # Linear interpolation
                breakeven_diesel = d1 + (0 - m1) * (d2 - d1) / (m2 - m1)
                st.warning(
                    f"⚠️ Si el precio del diésel sube a **{breakeven_diesel:.2f} Bs/L** "
                    f"(+{((breakeven_diesel/diesel_price)-1)*100:.0f}%), el margen llega a **0%**."
                )
                break
        else:
            if sensitivity_df["Margen (%)"].min() > 0:
                st.success("✅ Incluso con +30% en el precio del diésel, el margen se mantiene positivo.")
            else:
                st.error("❌ El margen ya es negativo con el precio actual del diésel.")
    
    # -----------------------
    # TAB 4: Details
    # -----------------------
    with tab4:
        st.subheader("Detalles de Costos por Equipo")
        
        if equipment_costs["details"]:
            df_equipment = pd.DataFrame(equipment_costs["details"])
            st.dataframe(
                df_equipment.style.format({
                    "Diésel (L/día)": "{:.1f}",
                    "Costo Diésel (Bs)": "{:,.2f}",
                    "Mantenimiento (Bs)": "{:,.2f}",
                    "Desgaste (Bs)": "{:,.2f}",
                    "Total (Bs)": "{:,.2f}",
                }),
                use_container_width=True
            )
        
        st.divider()
        st.subheader("Resumen de Personal")
        
        personnel_table = pd.DataFrame({
            "Rol": ["Operadores", "Ayudantes", "Supervisores"],
            "Cantidad": [operators_count, helpers_count, supervisors_count],
            "Salario/día (Bs)": [operators_wage, helpers_wage, supervisors_wage],
            "Costo Diario (Bs)": [
                operators_count * operators_wage,
                helpers_count * helpers_wage,
                supervisors_count * supervisors_wage,
            ]
        })
        st.dataframe(personnel_table, use_container_width=True)
        st.info(f"**Total Personal (con {social_benefits}% beneficios):** {personnel.total_daily_cost:,.2f} Bs/día")
        
        st.divider()
        st.subheader("Logística")
        st.write(f"- **Movilización:** {mobilization_cost:,.2f} Bs")
        st.write(f"- **Desmovilización:** {demobilization_cost:,.2f} Bs")
        st.write(f"- **Combustible vehículos apoyo:** {support_fuel:,.2f} Bs/día")
        st.write(f"- **Insumos varios:** {consumables:,.2f} Bs/día")
    
    # -----------------------
    # EXPORT BUTTONS
    # -----------------------
    st.divider()
    st.header("📥 Exportar Resultados")
    
    col1, col2, col3 = st.columns(3)

    with col1:
        # Generate Excel
        excel_data = generate_excel_report(
            project, personnel, logistics, economic,
            equipment_costs, daily_costs, unit_cost_data, margins,
            scenarios, sensitivity_df,
            materials, material_margin_df,
        )
        st.download_button(
            label="📊 Descargar Excel",
            data=excel_data,
            file_name=f"analisis_trituracion_{project_name.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col2:
        # Generate PDF
        pdf_data = generate_pdf_report(
            project, personnel, logistics, economic,
            equipment_costs, daily_costs, unit_cost_data, margins,
            scenarios, sensitivity_df,
            materials, material_margin_df,
        )
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_data,
            file_name=f"analisis_trituracion_{project_name.replace(' ', '_')}.pdf",
            mime="application/pdf",
        )

    with col3:
        # Generate Business Proposal PDF (client-facing)
        if "proposal_materials" not in locals() or not proposal_materials:
            st.info("🧾 Para generar la propuesta, completa cantidades y precios en la sección 'Propuesta Comercial' del sidebar.")
        else:
            proposal_pdf_data = generate_business_proposal_pdf(
                project=project,
                generator=generator,
                plant_equipment=plant_equipment,
                mobile_equipment=mobile_equipment,
                proposal_materials=proposal_materials,
                company_name="Agremaq Ltda",
                company_tagline="Servicio de trituración móvil y producción de áridos",
                client_name=client_name if "client_name" in locals() else "",
                payment_terms=payment_terms if "payment_terms" in locals() else "",
                validity_days=int(validity_days) if "validity_days" in locals() else 7,
                notes=proposal_notes if "proposal_notes" in locals() else "",
            )
            st.download_button(
                label="🧾 Descargar Propuesta (PDF)",
                data=proposal_pdf_data,
                file_name=f"propuesta_{project_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
            )


if __name__ == "__main__":
    main()

