import math
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path for db import
sys.path.insert(0, str(Path(__file__).parent.parent))
import db


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
    """Calculate diesel cost per cubic meter."""
    total_m3 = m3_sold + m3_transported
    if total_m3 <= 0:
        return 0.0
    return total_spent / total_m3


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

        # Calculate price adjustment per m3
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
            "Viajes": trips,
            "Km Totales": round(total_km, 1),
            "Costo/m³-km (Bs)": round(cost_per_m3_km, 4),
            "Costo Proy/m³-km (Bs)": round(projected_cost_per_m3_km, 4),
            "Crédito IVA Actual (Bs)": round(iva["current_iva_credit"], 2),
            "Crédito IVA Nuevo (Bs)": round(iva["new_iva_credit"], 2),
            "Beneficio IVA (Bs)": round(iva["iva_benefit"], 2),
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

# -----------------------
# Session state initialization
# -----------------------
if "diesel_entries" not in st.session_state:
    # Load existing entries from database
    st.session_state.diesel_entries = db.get_diesel_entries()

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

st.sidebar.markdown("---")

if st.sidebar.button("➕ Agregar Mes", use_container_width=True):
    if m3_sold <= 0 and m3_transported <= 0:
        st.sidebar.error("Debe ingresar al menos m³ vendidos o transportados")
    else:
        new_entry = {
            "id": str(uuid.uuid4()),
            "month": month_label,
            "total_spent": total_spent,
            "old_price": old_price,
            "new_price": new_price,
            "m3_sold": m3_sold,
            "m3_transported": m3_transported,
        }
        # Save to database and update session state
        db.save_diesel_entry(new_entry)
        st.session_state.diesel_entries.append(new_entry)
        st.sidebar.success(f"✅ Datos de {month_label} agregados")
        st.rerun()

# Sidebar - Clear all data
st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Limpiar Todos los Datos", use_container_width=True):
    db.clear_all_diesel_entries()
    st.session_state.diesel_entries = []
    st.rerun()

# -----------------------
# Main content area
# -----------------------
if not st.session_state.diesel_entries:
    st.info("👈 Agregue datos mensuales usando el formulario en la barra lateral para comenzar el análisis.")
else:
    # Process data
    df = process_monthly_data(
        st.session_state.diesel_entries,
        truck_capacity=st.session_state.truck_capacity,
        distance_km=st.session_state.distance_km,
        transport_pct=st.session_state.transport_diesel_pct
    )
    
    # -----------------------
    # KPI Metrics Row
    # -----------------------
    st.markdown("## 📈 Resumen")
    
    total_spent_sum = df["Gasto Diesel (Bs)"].sum()
    total_projected_sum = df["Costo Proyectado (Bs)"].sum()
    total_cost_diff = df["Diferencia Costo (Bs)"].sum()
    total_iva_benefit = df["Beneficio IVA (Bs)"].sum()
    total_m3_sum = df["Total m³"].sum()
    avg_cost_per_m3 = total_spent_sum / total_m3_sum if total_m3_sum > 0 else 0
    
    # Price adjustment calculations
    cost_increase_per_m3 = total_cost_diff / total_m3_sum if total_m3_sum > 0 else 0
    iva_benefit_per_m3 = total_iva_benefit / total_m3_sum if total_m3_sum > 0 else 0
    net_price_increase_needed = cost_increase_per_m3 - iva_benefit_per_m3
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.metric(
            "Total Gasto Diesel",
            f"{total_spent_sum:,.0f} Bs",
        )
    
    with kpi2:
        st.metric(
            "Costo Proyectado (Precio Nuevo)",
            f"{total_projected_sum:,.0f} Bs",
            delta=f"{total_cost_diff:+,.0f} Bs",
            delta_color="inverse",
        )
    
    with kpi3:
        st.metric(
            "Beneficio Total IVA",
            f"{total_iva_benefit:,.0f} Bs",
            help="Diferencia entre crédito IVA nuevo (13% de 100%) vs actual (13% de 70%)",
        )
    
    with kpi4:
        st.metric(
            "Costo Promedio por m³",
            f"{avg_cost_per_m3:,.2f} Bs/m³",
        )
    
    # Second row of KPIs
    kpi5, kpi6, kpi7, kpi8 = st.columns(4)
    
    with kpi5:
        st.metric("Total m³ Vendidos", f"{df['m³ Vendidos'].sum():,.0f}")
    
    with kpi6:
        st.metric("Total m³ Transportados", f"{df['m³ Transportados'].sum():,.0f}")
    
    with kpi7:
        st.metric("Total Litros Consumidos", f"{df['Litros Consumidos'].sum():,.0f} L")
    
    with kpi8:
        st.metric("Meses Registrados", f"{len(df)}")
    
    # Third row of KPIs - Transport metrics
    st.markdown("### 🚚 Métricas de Transporte")
    
    total_trips = df["Viajes"].sum()
    total_km_traveled = df["Km Totales"].sum()
    total_m3_transported = df["m³ Transportados"].sum()
    
    # Calculate average cost per m3-km (weighted by m3 transported)
    # Apply transport percentage to get estimated transport diesel cost
    transport_pct_decimal = st.session_state.transport_diesel_pct / 100
    if total_m3_transported > 0:
        transport_spent_total = df["Gasto Diesel (Bs)"].sum() * transport_pct_decimal
        transport_projected_total = df["Costo Proyectado (Bs)"].sum() * transport_pct_decimal
        avg_cost_per_m3_km = transport_spent_total / (total_m3_transported * st.session_state.distance_km)
        avg_projected_cost_per_m3_km = transport_projected_total / (total_m3_transported * st.session_state.distance_km)
    else:
        avg_cost_per_m3_km = 0
        avg_projected_cost_per_m3_km = 0
    
    kpi9, kpi10, kpi11, kpi12 = st.columns(4)
    
    with kpi9:
        st.metric(
            "Total Viajes",
            f"{total_trips:,.0f}",
            help=f"Viajes necesarios con camión de {st.session_state.truck_capacity:.0f} m³",
        )
    
    with kpi10:
        st.metric(
            "Km Totales Recorridos",
            f"{total_km_traveled:,.0f} km",
            help=f"Distancia total (ida y vuelta de {st.session_state.distance_km:.0f} km)",
        )
    
    with kpi11:
        st.metric(
            "Costo Actual por m³-km",
            f"{avg_cost_per_m3_km:,.4f} Bs",
            help=f"Costo de diesel por m³-km (usando {st.session_state.transport_diesel_pct:.0f}% del diesel total)",
        )
    
    with kpi12:
        cost_per_m3_km_diff = avg_projected_cost_per_m3_km - avg_cost_per_m3_km
        st.metric(
            "Costo Proyectado por m³-km",
            f"{avg_projected_cost_per_m3_km:,.4f} Bs",
            delta=f"{cost_per_m3_km_diff:+,.4f} Bs",
            delta_color="inverse",
            help=f"Costo proyectado por m³-km (usando {st.session_state.transport_diesel_pct:.0f}% del diesel total)",
        )
    
    st.markdown("---")
    
    # -----------------------
    # Price Adjustment Recommendation
    # -----------------------
    st.markdown("## 💰 Ajuste de Precio Recomendado")
    
    rec_col1, rec_col2, rec_col3 = st.columns(3)
    
    with rec_col1:
        st.metric(
            "Aumento Costo por m³",
            f"{cost_increase_per_m3:+,.2f} Bs/m³",
            help="Incremento en costo de diesel por m³ debido al nuevo precio",
        )
    
    with rec_col2:
        st.metric(
            "Beneficio IVA por m³",
            f"{iva_benefit_per_m3:,.2f} Bs/m³",
            help="Ahorro por m³ debido al nuevo crédito fiscal (13% de 100% vs 70%)",
        )
    
    with rec_col3:
        st.metric(
            "Aumento Neto Necesario",
            f"{net_price_increase_needed:+,.2f} Bs/m³",
            help="Aumento de precio por m³ necesario después de considerar el beneficio IVA",
        )
    
    # Recommendation box
    if net_price_increase_needed > 0:
        st.warning(f"""
        **📊 Recomendación:** Para mantener su margen de ganancia, debe aumentar el precio de venta en 
        **{net_price_increase_needed:,.2f} Bs por m³**.
        
        - Aumento bruto por costo diesel: +{cost_increase_per_m3:,.2f} Bs/m³
        - Compensación por beneficio IVA: -{iva_benefit_per_m3:,.2f} Bs/m³
        - **Aumento neto requerido: {net_price_increase_needed:,.2f} Bs/m³**
        """)
    elif net_price_increase_needed < 0:
        st.success(f"""
        **📊 Buenas noticias:** El beneficio adicional del IVA compensa el aumento en el precio del diesel.
        
        - Aumento bruto por costo diesel: +{cost_increase_per_m3:,.2f} Bs/m³
        - Compensación por beneficio IVA: -{iva_benefit_per_m3:,.2f} Bs/m³
        - **Beneficio neto: {abs(net_price_increase_needed):,.2f} Bs/m³** (no necesita aumentar precios)
        """)
    else:
        st.info("""
        **📊 Neutral:** El aumento en el costo del diesel es exactamente compensado por el beneficio del IVA.
        No necesita ajustar sus precios.
        """)
    
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
        file_name="analisis_diesel.csv",
        mime="text/csv",
    )
    
    st.markdown("---")
    
    # -----------------------
    # Charts
    # -----------------------
    st.markdown("## 📊 Gráficos")
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.plotly_chart(plot_cost_comparison(df), use_container_width=True)
    
    with chart_col2:
        st.plotly_chart(plot_iva_comparison(df), use_container_width=True)
    
    # Full width chart for trend
    st.plotly_chart(plot_cost_per_m3_trend(df), use_container_width=True)
    
    # -----------------------
    # Summary Table
    # -----------------------
    st.markdown("## 📝 Resumen de Beneficios")
    
    summary_col1, summary_col2 = st.columns(2)
    
    with summary_col1:
        st.markdown("### Crédito Fiscal IVA")
        st.markdown(f"""
        | Concepto | Monto (Bs) |
        |----------|------------|
        | Crédito IVA Actual (13% de 70%) | {df['Crédito IVA Actual (Bs)'].sum():,.2f} |
        | Crédito IVA Nuevo (13% de 100%) | {df['Crédito IVA Nuevo (Bs)'].sum():,.2f} |
        | **Beneficio Adicional** | **{total_iva_benefit:,.2f}** |
        """)
    
    with summary_col2:
        st.markdown("### Impacto del Precio")
        price_impact_pct = (total_cost_diff / total_spent_sum * 100) if total_spent_sum > 0 else 0
        st.markdown(f"""
        | Concepto | Monto |
        |----------|-------|
        | Gasto Total Actual | {total_spent_sum:,.2f} Bs |
        | Costo Proyectado (Precio Nuevo) | {total_projected_sum:,.2f} Bs |
        | Diferencia | {total_cost_diff:+,.2f} Bs |
        | Incremento Porcentual | {price_impact_pct:+.1f}% |
        """)
