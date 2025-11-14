import sqlite3
from pathlib import Path
from src.config import DB_PATH, DEFAULT_CURRENCY

# Crear directorio si no existe
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """
    Obtiene conexión a SQLite con configuración estándar.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # Habilitar claves foráneas
    return conn


def init_db() -> None:
    """
    Inicializa esquema de BD con estructura contable robusta.
    """
    schema = f"""
    -- Documentos fuente (facturas, recibos, etc)
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        doc_number TEXT,
        source TEXT,
        raw_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Tabla de transacciones: ventas, compras, servicios, etc
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        transaction_date DATE NOT NULL,
        transaction_type TEXT NOT NULL,
        transaction_number TEXT,
        counterparty TEXT,
        description TEXT,
        amount REAL NOT NULL,
        currency TEXT DEFAULT '{DEFAULT_CURRENCY}',
        payment_method TEXT,
        status TEXT DEFAULT 'pending',
        tags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(document_id) REFERENCES documents(id)
    );

    -- Tabla de línea de transacciones (detalles)
    CREATE TABLE IF NOT EXISTS transaction_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id INTEGER NOT NULL,
        line_number INTEGER,
        account_code TEXT,
        account_name TEXT,
        debit REAL DEFAULT 0,
        credit REAL DEFAULT 0,
        description TEXT,
        quantity REAL DEFAULT 1,
        unit_price REAL DEFAULT 0,
        subtotal REAL DEFAULT 0,
        tax_rate REAL DEFAULT 0,
        tax_amount REAL DEFAULT 0,
        category TEXT,
        FOREIGN KEY(transaction_id) REFERENCES transactions(id)
    );

    -- Tabla de cuentas (chart of accounts)
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        account_type TEXT,
        balance REAL DEFAULT 0,
        currency TEXT DEFAULT '{DEFAULT_CURRENCY}',
        is_active INTEGER DEFAULT 1
    );

    -- Tabla de movimientos diarios (book)
    CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date DATE NOT NULL,
        entry_number TEXT,
        transaction_id INTEGER,
        account_code TEXT NOT NULL,
        debit REAL DEFAULT 0,
        credit REAL DEFAULT 0,
        description TEXT,
        reference TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(transaction_id) REFERENCES transactions(id),
        FOREIGN KEY(account_code) REFERENCES accounts(code)
    );

    -- Índices para mejor rendimiento
    CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
    CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
    CREATE INDEX IF NOT EXISTS idx_transactions_number ON transactions(transaction_number);
    CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(entry_date);
    CREATE INDEX IF NOT EXISTS idx_journal_account ON journal_entries(account_code);
    CREATE INDEX IF NOT EXISTS idx_transaction_lines_tx ON transaction_lines(transaction_id);
    """
    
    with get_connection() as conn:
        conn.executescript(schema)
        conn.commit()