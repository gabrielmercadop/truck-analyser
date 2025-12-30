import math
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path for db import
sys.path.insert(0, str(Path(__file__).parent.parent))
import db


@dataclass(frozen=True)
class ScenarioInputs:
    outage_days: int
    production_per_day: float
    price_per_unit: float
    non_power_variable_cost_per_unit: float
    fixed_costs_per_day: float
    stop_penalty_per_day: float
    fuel_method: str  # "per_day" | "per_unit"
    diesel_price_per_liter: float
    liters_per_day: float
    liters_per_unit: float
    rental_cost_per_day: float
    mobilization_cost: float
    minimum_rental_days: int


def _clamp_non_negative(value: float) -> float:
    return max(0.0, float(value))


def _safe_int(value: int) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _compute_fuel_cost_per_day(inputs: ScenarioInputs) -> float:
    diesel_price = _clamp_non_negative(inputs.diesel_price_per_liter)

    if inputs.outage_days <= 0:
        return 0.0

    if inputs.fuel_method == "per_unit":
        liters = _clamp_non_negative(inputs.liters_per_unit) * _clamp_non_negative(inputs.production_per_day)
        return liters * diesel_price

    liters = _clamp_non_negative(inputs.liters_per_day)
    return liters * diesel_price


def compute_stop_vs_rent(inputs: ScenarioInputs) -> dict:
    outage_days = max(0, _safe_int(inputs.outage_days))
    min_rental_days = max(0, _safe_int(inputs.minimum_rental_days))

    # If there is no outage, renting is irrelevant; model billed days as 0.
    billed_days = 0 if outage_days == 0 else max(outage_days, min_rental_days)
    horizon_days = max(outage_days, billed_days)

    fixed_costs = _clamp_non_negative(inputs.fixed_costs_per_day)
    stop_penalty = _clamp_non_negative(inputs.stop_penalty_per_day)

    production = _clamp_non_negative(inputs.production_per_day)
    price = _clamp_non_negative(inputs.price_per_unit)
    non_power_var = _clamp_non_negative(inputs.non_power_variable_cost_per_unit)

    rental_daily = _clamp_non_negative(inputs.rental_cost_per_day)
    mobilization = _clamp_non_negative(inputs.mobilization_cost)

    revenue_per_day = production * price
    non_power_variable_per_day = production * non_power_var
    fuel_cost_per_day = _compute_fuel_cost_per_day(inputs)

    mobilization_per_billed_day = (mobilization / billed_days) if billed_days > 0 else 0.0

    stop_profit_daily = []
    rent_profit_daily = []

    for day in range(1, horizon_days + 1):
        in_outage = day <= outage_days
        in_billing = day <= billed_days

        # STOP: during outage you keep paying fixed costs (and any penalties). After outage, incremental effect is 0.
        if in_outage:
            stop_profit = -(fixed_costs + stop_penalty)
        else:
            stop_profit = 0.0

        # RENT: during outage you operate (revenue - costs). If minimum rental days exceed outage days,
        # remaining billed days are modeled as pure rental cost (no operational benefit).
        rent_profit = 0.0
        if in_outage:
            rent_profit = (
                revenue_per_day
                - non_power_variable_per_day
                - fuel_cost_per_day
                - fixed_costs
                - (rental_daily if in_billing else 0.0)
                - (mobilization_per_billed_day if in_billing else 0.0)
            )
        else:
            # Outage resolved: only count remaining billed rental costs as incremental.
            if in_billing:
                rent_profit = -(rental_daily + mobilization_per_billed_day)

        stop_profit_daily.append(float(stop_profit))
        rent_profit_daily.append(float(rent_profit))

    def _cumulative(values: list[float]) -> list[float]:
        total = 0.0
        out = []
        for v in values:
            total += v
            out.append(total)
        return out

    stop_cum = _cumulative(stop_profit_daily)
    rent_cum = _cumulative(rent_profit_daily)
    diff_cum = [r - s for r, s in zip(rent_cum, stop_cum)]

    total_stop = stop_cum[-1] if stop_cum else 0.0
    total_rent = rent_cum[-1] if rent_cum else 0.0
    incremental_total = total_rent - total_stop

    # Break-even: earliest day where cumulative rent >= cumulative stop.
    break_even_day = None
    for i, d in enumerate(diff_cum, start=1):
        if d >= 0:
            break_even_day = i
            break

    # Stable break-even: earliest day after which diff_cum never goes negative.
    stable_break_even_day = None
    if diff_cum:
        min_suffix = math.inf
        stable_index_from_end = [0] * len(diff_cum)
        for i in range(len(diff_cum) - 1, -1, -1):
            min_suffix = min(min_suffix, diff_cum[i])
            stable_index_from_end[i] = min_suffix
        for i, suffix_min in enumerate(stable_index_from_end, start=1):
            if suffix_min >= 0:
                stable_break_even_day = i
                break

    # Maximum daily rental cost you can pay and still be indifferent (based on billed days).
    max_rental_cost_per_day = None
    if billed_days > 0:
        total_rent_without_daily_rental = total_rent + rental_daily * billed_days
        max_rental_cost_per_day = (total_rent_without_daily_rental - total_stop) / billed_days

    df = pd.DataFrame(
        {
            "Day": list(range(1, horizon_days + 1)),
            "Profit_Stop": stop_profit_daily,
            "Profit_Rent": rent_profit_daily,
            "Cumulative_Stop": stop_cum,
            "Cumulative_Rent": rent_cum,
            "Cumulative_Diff(Rent-Stop)": diff_cum,
        }
    )

    return {
        "outage_days": outage_days,
        "billed_days": billed_days,
        "horizon_days": horizon_days,
        "revenue_per_day": revenue_per_day,
        "non_power_variable_per_day": non_power_variable_per_day,
        "fuel_cost_per_day": fuel_cost_per_day,
        "mobilization_per_billed_day": mobilization_per_billed_day,
        "total_stop": total_stop,
        "total_rent": total_rent,
        "incremental_total": incremental_total,
        "break_even_day": break_even_day,
        "stable_break_even_day": stable_break_even_day,
        "max_rental_cost_per_day": max_rental_cost_per_day,
        "daily_table": df,
    }


def _plot_cumulative(df: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["Day"],
            y=df["Cumulative_Stop"],
            mode="lines",
            name="Stop production",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["Day"],
            y=df["Cumulative_Rent"],
            mode="lines",
            name="Rent generator",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Day",
        yaxis_title="Cumulative profit (Bs)",
        legend_title="Scenario",
        margin=dict(l=30, r=30, t=50, b=30),
    )
    return fig


def _plot_sensitivity_rental_cost(inputs: ScenarioInputs, base_results: dict) -> go.Figure:
    billed_days = base_results["billed_days"]
    if billed_days <= 0:
        fig = go.Figure()
        fig.update_layout(
            title="Sensitivity (rental cost): not applicable",
            xaxis_title="Rental cost (Bs/day)",
            yaxis_title="Incremental benefit (Bs)",
            margin=dict(l=30, r=30, t=50, b=30),
        )
        return fig

    current = _clamp_non_negative(inputs.rental_cost_per_day)
    max_rental = base_results.get("max_rental_cost_per_day")

    upper = max(2.0 * current, 1.0)
    if max_rental is not None and math.isfinite(max_rental):
        upper = max(upper, 1.5 * max(0.0, float(max_rental)))

    # Keep a reasonable chart span even if numbers are tiny.
    if upper < 100:
        upper = 100.0

    steps = 60
    rental_values = [upper * i / (steps - 1) for i in range(steps)]
    incremental_values = []

    for v in rental_values:
        tmp_inputs = ScenarioInputs(
            **{**inputs.__dict__, "rental_cost_per_day": float(v)}
        )
        tmp = compute_stop_vs_rent(tmp_inputs)
        incremental_values.append(tmp["incremental_total"])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=rental_values,
            y=incremental_values,
            mode="lines",
            name="Incremental benefit (Rent-Stop)",
        )
    )
    fig.update_layout(
        title="Sensitivity: incremental benefit vs rental cost",
        xaxis_title="Rental cost (Bs/day)",
        yaxis_title="Incremental benefit over the horizon (Bs)",
        margin=dict(l=30, r=30, t=50, b=30),
    )

    # Reference line at 0
    fig.add_hline(y=0, line_dash="dot")
    return fig


st.set_page_config(page_title="Generator Decision", layout="wide")

st.title("⚡ Generator Decision: Rent vs Stop Production")
st.markdown(
    """
This page compares two outage responses for an aggregates production plant:

- **Stop production** (fixed costs continue)
- **Rent a generator** to keep producing

All calculations are **per-day**, and the model includes **minimum rental days** and **one-time mobilization cost**.
"""
)

# -----------------------
# Sidebar inputs
# -----------------------
st.sidebar.header("🔧 Inputs")

unit = st.sidebar.selectbox("Production unit", options=["tons", "m³"], index=0)
unit_label = "ton" if unit == "tons" else "m³"

outage_days = st.sidebar.slider("Outage duration (days)", min_value=0, max_value=60, value=7, step=1)

st.sidebar.subheader("🏭 Plant economics (when running)")
production_per_day = st.sidebar.number_input(
    f"Production per day ({unit_label}/day)",
    min_value=0.0,
    value=800.0,
    step=50.0,
    format="%.2f",
)
price_per_unit = st.sidebar.number_input(
    f"Selling price (Bs per {unit_label})",
    min_value=0.0,
    value=65.0,
    step=1.0,
    format="%.2f",
)
non_power_variable_cost_per_unit = st.sidebar.number_input(
    f"Non-power variable cost (Bs per {unit_label})",
    min_value=0.0,
    value=20.0,
    step=1.0,
    format="%.2f",
    help="Costs that scale with production (excluding generator diesel), e.g. loader wear, consumables, etc.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("🧾 Costs that continue (even if stopped)")
fixed_costs_per_day = st.sidebar.number_input(
    "Fixed costs per day (Bs/day)",
    min_value=0.0,
    value=6_000.0,
    step=250.0,
    format="%.2f",
    help="Payroll/admin/security/leases/etc. that continue during a stoppage.",
)
stop_penalty_per_day = st.sidebar.number_input(
    "Stop penalty / lost margin per day (Bs/day)",
    min_value=0.0,
    value=0.0,
    step=250.0,
    format="%.2f",
    help="Optional: contract penalties or client-loss cost if you stop production.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("⛽ Generator fuel")
fuel_method_ui = st.sidebar.radio(
    "Fuel modeling method",
    options=["Liters per day", f"Liters per {unit_label}"],
    index=0,
)

diesel_price_per_liter = st.sidebar.number_input(
    "Diesel price (Bs/liter)",
    min_value=0.0,
    value=3.72,
    step=0.05,
    format="%.3f",
)

liters_per_day = 0.0
liters_per_unit = 0.0
if fuel_method_ui == "Liters per day":
    liters_per_day = st.sidebar.number_input(
        "Diesel consumption (liters/day)",
        min_value=0.0,
        value=700.0,
        step=25.0,
        format="%.2f",
    )
    fuel_method = "per_day"
else:
    liters_per_unit = st.sidebar.number_input(
        f"Diesel consumption (liters per {unit_label})",
        min_value=0.0,
        value=0.9,
        step=0.05,
        format="%.3f",
    )
    fuel_method = "per_unit"

st.sidebar.markdown("---")
st.sidebar.subheader("🔌 Rental terms")
rental_cost_per_day = st.sidebar.number_input(
    "Rental cost (Bs/day)",
    min_value=0.0,
    value=8_000.0,
    step=250.0,
    format="%.2f",
)
mobilization_cost = st.sidebar.number_input(
    "Mobilization / installation (one-time, Bs)",
    min_value=0.0,
    value=0.0,
    step=500.0,
    format="%.2f",
)
minimum_rental_days = st.sidebar.number_input(
    "Minimum rental days",
    min_value=0,
    value=0,
    step=1,
    help="If the vendor requires a minimum number of billed days (even if the outage is shorter).",
)

# ------------- Saved Scenarios Section -------------
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Escenarios Guardados")

# Load saved scenarios
saved_scenarios = db.get_generator_scenarios()

# Display saved scenarios list
if saved_scenarios:
    st.sidebar.caption(f"{len(saved_scenarios)} escenarios guardados")
    
    for saved in saved_scenarios:
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            created = saved["created_at"][:10] if saved["created_at"] else ""
            st.sidebar.text(f"⚡ {saved['name']}\n   {created}")
        with col2:
            if st.sidebar.button("🗑️", key=f"del_gen_{saved['id']}", help="Eliminar"):
                db.delete_generator_scenario(saved['id'])
                st.rerun()
    
    # Load scenario selector
    scenario_options = [(s["id"], s["name"]) for s in saved_scenarios]
    selected_scenario = st.sidebar.selectbox(
        "Cargar escenario",
        options=scenario_options,
        format_func=lambda x: x[1],
        key="load_scenario_select"
    )
    
    if st.sidebar.button("📂 Cargar Escenario", use_container_width=True):
        loaded = db.get_generator_scenario(selected_scenario[0])
        if loaded and loaded["inputs"]:
            st.session_state.loaded_scenario = loaded["inputs"]
            st.sidebar.success(f"✅ Escenario '{loaded['name']}' cargado")
            st.rerun()
else:
    st.sidebar.caption("No hay escenarios guardados")

# Apply loaded scenario values (if any)
if "loaded_scenario" in st.session_state:
    st.sidebar.info("ℹ️ Valores cargados del escenario guardado. Modifique los inputs en la barra lateral para aplicar.")
    del st.session_state.loaded_scenario

inputs = ScenarioInputs(
    outage_days=int(outage_days),
    production_per_day=float(production_per_day),
    price_per_unit=float(price_per_unit),
    non_power_variable_cost_per_unit=float(non_power_variable_cost_per_unit),
    fixed_costs_per_day=float(fixed_costs_per_day),
    stop_penalty_per_day=float(stop_penalty_per_day),
    fuel_method=fuel_method,
    diesel_price_per_liter=float(diesel_price_per_liter),
    liters_per_day=float(liters_per_day),
    liters_per_unit=float(liters_per_unit),
    rental_cost_per_day=float(rental_cost_per_day),
    mobilization_cost=float(mobilization_cost),
    minimum_rental_days=int(minimum_rental_days),
)

results = compute_stop_vs_rent(inputs)
df = results["daily_table"]

# -----------------------
# Results UI
# -----------------------
if results["outage_days"] == 0:
    st.info("Outage duration is 0 days. The comparison is shown for completeness, but renting is typically unnecessary.")

if results["billed_days"] > results["outage_days"]:
    st.warning(
        f"Minimum rental days exceed outage duration: you will be billed for {results['billed_days']} days "
        f"even though the outage is {results['outage_days']} days. The model includes the extra billed days as cost-only."
    )

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric("Total profit (Stop)", f"{results['total_stop']:,.0f} Bs")
with kpi2:
    st.metric("Total profit (Rent)", f"{results['total_rent']:,.0f} Bs")
with kpi3:
    st.metric("Incremental benefit (Rent-Stop)", f"{results['incremental_total']:,.0f} Bs")
with kpi4:
    st.metric("Billed days", f"{results['billed_days']} days")

if results["incremental_total"] > 0:
    st.success("Recommendation: **Rent the generator** (higher total profit over the modeled horizon).")
elif results["incremental_total"] < 0:
    st.error("Recommendation: **Stop production** (renting reduces total profit over the modeled horizon).")
else:
    st.info("Recommendation: **Indifferent** (both scenarios are approximately equal over the modeled horizon).")

meta_col1, meta_col2, meta_col3 = st.columns(3)
with meta_col1:
    st.write("**Daily economics during outage (Rent)**")
    st.write(f"Revenue/day: {results['revenue_per_day']:,.0f} Bs")
    st.write(f"Non-power variable/day: {results['non_power_variable_per_day']:,.0f} Bs")
    st.write(f"Fuel/day: {results['fuel_cost_per_day']:,.0f} Bs")
with meta_col2:
    st.write("**Break-even**")
    if results["break_even_day"] is None:
        st.write("Break-even day: N/A")
    else:
        st.write(f"Break-even day (first crossing): Day {results['break_even_day']}")

    if results["stable_break_even_day"] is None:
        st.write("Stable break-even: N/A")
    else:
        st.write(f"Stable break-even (stays better): Day {results['stable_break_even_day']}")
with meta_col3:
    st.write("**Rental price limit**")
    max_rental = results.get("max_rental_cost_per_day")
    if max_rental is None or not math.isfinite(float(max_rental)):
        st.write("Max rental cost/day: N/A")
    else:
        st.write(f"Max rental cost/day (indifferent): {max(0.0, float(max_rental)):,.0f} Bs/day")

st.markdown("---")

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.plotly_chart(_plot_cumulative(df, title="Cumulative profit by day"), use_container_width=True)
with chart_col2:
    st.plotly_chart(_plot_sensitivity_rental_cost(inputs, results), use_container_width=True)

with st.expander("Daily table (debug / audit)"):
    st.dataframe(df, use_container_width=True)

# Save Scenario Section
st.markdown("---")
st.subheader("💾 Guardar Escenario")

save_col1, save_col2 = st.columns([2, 1])

with save_col1:
    scenario_name = st.text_input(
        "Nombre del escenario",
        value=f"Escenario {outage_days} días - {datetime.now().strftime('%d/%m/%Y')}",
        placeholder="Ej: Corte programado - Enero 2025",
        key="save_scenario_name"
    )

with save_col2:
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing to align with input
    if st.button("💾 Guardar Escenario", use_container_width=True):
        if scenario_name.strip():
            # Convert dataclass to dict for saving
            inputs_dict = asdict(inputs)
            
            # Prepare results for saving (exclude DataFrame)
            results_to_save = {k: v for k, v in results.items() if k != "daily_table"}
            
            db.save_generator_scenario(
                name=scenario_name.strip(),
                inputs=inputs_dict,
                results=results_to_save
            )
            st.success(f"✅ Escenario '{scenario_name}' guardado exitosamente")
            st.rerun()
        else:
            st.error("Por favor ingresa un nombre para el escenario")











