"""
SQLite database module for persistent storage of:
- Diesel entries
- Investment analyses
- Generator scenarios
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# Database file path (same directory as the app)
DB_PATH = Path(__file__).parent / "investment_data.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory for dict-like access."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Diesel entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diesel_entries (
            id TEXT PRIMARY KEY,
            month TEXT NOT NULL,
            total_spent REAL,
            old_price REAL,
            new_price REAL,
            m3_sold REAL,
            m3_transported REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Investment analyses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS investment_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            truck_name TEXT,
            inputs_json TEXT,
            results_json TEXT,
            analysis_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Generator scenarios table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generator_scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            inputs_json TEXT,
            results_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


# -----------------------
# Diesel Entries CRUD
# -----------------------
def save_diesel_entry(entry: dict) -> None:
    """Save a diesel entry to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO diesel_entries 
        (id, month, total_spent, old_price, new_price, m3_sold, m3_transported)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        entry["id"],
        entry["month"],
        entry["total_spent"],
        entry["old_price"],
        entry["new_price"],
        entry["m3_sold"],
        entry["m3_transported"],
    ))
    conn.commit()
    conn.close()


def get_diesel_entries() -> list[dict]:
    """Get all diesel entries from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diesel_entries ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "month": row["month"],
            "total_spent": row["total_spent"],
            "old_price": row["old_price"],
            "new_price": row["new_price"],
            "m3_sold": row["m3_sold"],
            "m3_transported": row["m3_transported"],
        }
        for row in rows
    ]


def delete_diesel_entry(entry_id: str) -> None:
    """Delete a diesel entry by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM diesel_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def clear_all_diesel_entries() -> None:
    """Delete all diesel entries."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM diesel_entries")
    conn.commit()
    conn.close()


# -----------------------
# Investment Analyses CRUD
# -----------------------
def save_investment_analysis(
    name: str,
    truck_name: str,
    inputs: dict,
    results: dict,
    analysis: dict
) -> int:
    """Save an investment analysis to the database. Returns the new ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO investment_analyses 
        (name, truck_name, inputs_json, results_json, analysis_json)
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        truck_name,
        json.dumps(inputs),
        json.dumps(results),
        json.dumps(analysis),
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_investment_analyses() -> list[dict]:
    """Get all saved investment analyses."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, truck_name, inputs_json, results_json, analysis_json, created_at 
        FROM investment_analyses 
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "truck_name": row["truck_name"],
            "inputs": json.loads(row["inputs_json"]) if row["inputs_json"] else {},
            "results": json.loads(row["results_json"]) if row["results_json"] else {},
            "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else {},
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_investment_analysis(analysis_id: int) -> Optional[dict]:
    """Get a single investment analysis by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, truck_name, inputs_json, results_json, analysis_json, created_at 
        FROM investment_analyses 
        WHERE id = ?
    """, (analysis_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row is None:
        return None
    
    return {
        "id": row["id"],
        "name": row["name"],
        "truck_name": row["truck_name"],
        "inputs": json.loads(row["inputs_json"]) if row["inputs_json"] else {},
        "results": json.loads(row["results_json"]) if row["results_json"] else {},
        "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else {},
        "created_at": row["created_at"],
    }


def delete_investment_analysis(analysis_id: int) -> None:
    """Delete an investment analysis by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM investment_analyses WHERE id = ?", (analysis_id,))
    conn.commit()
    conn.close()


# -----------------------
# Generator Scenarios CRUD
# -----------------------
def save_generator_scenario(name: str, inputs: dict, results: dict) -> int:
    """Save a generator scenario to the database. Returns the new ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Convert results - remove DataFrame which isn't JSON serializable
    results_to_save = {k: v for k, v in results.items() if k != "daily_table"}
    if "daily_table" in results:
        # Convert DataFrame to list of dicts
        results_to_save["daily_table"] = results["daily_table"].to_dict(orient="records")
    
    cursor.execute("""
        INSERT INTO generator_scenarios 
        (name, inputs_json, results_json)
        VALUES (?, ?, ?)
    """, (
        name,
        json.dumps(inputs),
        json.dumps(results_to_save),
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_generator_scenarios() -> list[dict]:
    """Get all saved generator scenarios."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, inputs_json, results_json, created_at 
        FROM generator_scenarios 
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "inputs": json.loads(row["inputs_json"]) if row["inputs_json"] else {},
            "results": json.loads(row["results_json"]) if row["results_json"] else {},
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_generator_scenario(scenario_id: int) -> Optional[dict]:
    """Get a single generator scenario by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, inputs_json, results_json, created_at 
        FROM generator_scenarios 
        WHERE id = ?
    """, (scenario_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row is None:
        return None
    
    return {
        "id": row["id"],
        "name": row["name"],
        "inputs": json.loads(row["inputs_json"]) if row["inputs_json"] else {},
        "results": json.loads(row["results_json"]) if row["results_json"] else {},
        "created_at": row["created_at"],
    }


def delete_generator_scenario(scenario_id: int) -> None:
    """Delete a generator scenario by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM generator_scenarios WHERE id = ?", (scenario_id,))
    conn.commit()
    conn.close()


# Initialize database on module import
init_db()
