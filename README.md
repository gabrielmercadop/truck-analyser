# 📘 Truck Investment Analyzer  
A financial modeling and decision-support tool built with **Streamlit**, **Python**, and **Plotly** to evaluate the profitability and viability of investing in a **truck + trailer** operation in Bolivia.

This application provides a complete financial analysis including:

- Monthly cashflow  
- Operating and tax breakdown  
- Payback period  
- Loan amortization  
- ROI & DSCR scoring  
- Sensitivity analysis  
- Scenario comparison  
- Optional better-client revenue modeling  
- Full PDF report generation  

Designed specifically for aggregate transportation (stone, sand, gravel) but adaptable to any logistics business with similar cost structures.

---

## 🚀 Features

### 🔧 1. Investment Inputs
Adjust all key variables from the sidebar:

- Truck and trailer cost  
- Available capital & reserve  
- Loan amount, interest rate, and term  
- Operating parameters (m³ per trip, rate, trips per month)  
- Diesel, tolls, driver salary, maintenance, other expenses  
- IVA & IT tax rates  
- Optional better-client scenario (higher tariff trips)

---

### 💰 2. Monthly Cashflow and KPIs
The app calculates:

- Monthly revenue  
- Detailed taxes (IVA, IT)  
- Operating costs  
- Profit before and after debt  
- Payback period  
- Annual net profit  

---

### 🧾 3. Crédito Fiscal Modeling
Automatically calculates:

- IVA paid on asset purchase  
- How many months your credit covers your IVA obligations  
- Monthly savings and annual advantage  
- Side-by-side comparison: **With vs Without Crédito Fiscal**

---

### 🤝 4. Better Client Scenario
Simulate obtaining a higher tariff:

- Extra trips at a better rate  
- Revenue & profit increases  
- Impact on payback  
- Visual breakdown and a line-chart of profit vs better-rate trips  

---

### 📈 5. Investment Viability Score
A complete scoring system (0–100 points) based on:

- Profit margin  
- Payback period  
- DSCR (debt coverage)  
- ROI  
- Funding gap  

Final recommendation categories:

- **Altamente Recomendada**  
- **Recomendada**  
- **Aceptable con Reservas**  
- **Riesgosa**  
- **No Recomendada**

Includes strengths, warnings, and tailored recommendations.

---

### 📊 6. Sensitivity Analysis
See how results change as you adjust:

- Trips per month from low to high  
- Profit progression  
- Break-even point  
- Investment score at each trip level  
- Detailed comparison table  
- Interactive slider for manual scenario comparison  

---

### 📄 7. PDF Report Generator
Generates a full professional multi-page PDF including:

- Summary metrics  
- Credit details  
- Monthly cashflow  
- Taxes, costs, and profitability  
- Investment score section  
- Strengths & warnings  
- Sensitivity analysis table  
- Operating parameters breakdown  
- Mixed scenarios (better client)  

Perfect for presentations, clients, banks, and internal decision-making.

---

### 📅 8. Loan Amortization Table
Automatically calculates monthly amortization, including:

- Interest  
- Principal amortization  
- New balance  

---

## 🛠️ Tech Stack

| Component | Technology |
|----------|------------|
| Frontend UI | **Streamlit** |
| Charts | **Plotly** |
| PDF Reports | **FPDF** |
| Data Handling | **Pandas** |
| Core Logic | **Python** |
| Deployment | Streamlit Cloud / local server |

---

## 📂 Project Structure

```bash
analyser/
│
├── investment_app.py       # Main Streamlit application
├── requirements.txt        # Project dependencies
├── README.md               # Documentation
└── venv/                   # (Ignored) Python virtual environment