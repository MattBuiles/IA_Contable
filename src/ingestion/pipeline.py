from pathlib import Path
from typing import Iterable, List, Optional
from datetime import datetime

import pandas as pd
from langchain_core.documents import Document

from src.db.database import get_connection
from src.ingestion.loaders import read_excel, read_pdf
from src.ai.vectorstore import index_documents
from src.ai.client import get_embeddings


def store_document(filepath: Path, doc_type: str, raw_text: Optional[str], doc_number: Optional[str] = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO documents (filename, doc_type, doc_number, raw_text)
            VALUES (?, ?, ?, ?)
            """,
            (filepath.name, doc_type, doc_number, raw_text),
        )
        conn.commit()
        return cur.lastrowid


def bulk_insert_transactions(rows: Iterable[dict]) -> None:
    """Inserta transacciones (facturas, compras, etc)"""
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO transactions
            (document_id, transaction_date, transaction_type, transaction_number, 
             counterparty, description, amount, currency, status)
            VALUES (:document_id, :transaction_date, :transaction_type, :transaction_number,
                    :counterparty, :description, :amount, :currency, :status)
            """,
            rows,
        )
        conn.commit()


def bulk_insert_transaction_lines(rows: Iterable[dict]) -> None:
    """Inserta líneas de detalle de transacciones"""
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO transaction_lines
            (transaction_id, line_number, account_code, account_name, debit, credit, 
             description, quantity, unit_price, subtotal, tax_rate, tax_amount, category)
            VALUES (:transaction_id, :line_number, :account_code, :account_name, 
                    :debit, :credit, :description, :quantity, :unit_price, :subtotal, 
                    :tax_rate, :tax_amount, :category)
            """,
            rows,
        )
        conn.commit()


def bulk_insert_journal_entries(rows: Iterable[dict]) -> None:
    """Inserta asientos contables (journal entries)"""
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO journal_entries
            (transaction_id, entry_date, account_code, debit, credit, description)
            VALUES (:transaction_id, :entry_date, :account_code, 
                    :debit, :credit, :description)
            """,
            rows,
        )
        conn.commit()


def ensure_account_exists(account_code: str, account_name: str, account_type: str) -> None:
    """Crea una cuenta si no existe"""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO accounts (code, name, account_type, balance, is_active)
            VALUES (?, ?, ?, 0, 1)
            """,
            (account_code, account_name, account_type)
        )
        conn.commit()


def ensure_default_accounts() -> None:
    """Asegura que existan las cuentas contables básicas necesarias"""
    default_accounts = [
        ("1105", "Caja", "Activo"),
        ("4135", "Ingresos por ventas", "Ingreso"),
        ("2408", "IVA", "Pasivo"),
        ("6205", "Gastos de operación", "Gasto"),
    ]
    
    for code, name, acc_type in default_accounts:
        ensure_account_exists(code, name, acc_type)


def generate_journal_entries_for_transaction(
    transaction_id: int, 
    transaction_date: str, 
    transaction_type: str, 
    amount: float, 
    subtotal: float, 
    tax_amount: float,
    description: str
) -> List[dict]:
    """
    Genera asientos contables (partida doble) para una transacción.
    
    Para venta (sales_invoice):
        Débito: 1105 - Caja (activo)
        Crédito: 4135 - Ingresos por ventas
        Crédito: 2408 - IVA por pagar (si hay impuesto)
    
    Para compra (purchase_invoice):
        Débito: 6205 - Gastos/Compras
        Débito: 2408 - IVA descontable (si hay impuesto)
        Crédito: 1105 - Caja (activo)
    """
    entries = []
    
    if transaction_type == "sales_invoice":
        # Débito: Caja (activo aumenta)
        entries.append({
            "transaction_id": transaction_id,
            "entry_date": transaction_date,
            "account_code": "1105",
            "debit": amount,
            "credit": 0,
            "description": f"Ingreso por venta - {description}"
        })
        
        # Crédito: Ingresos
        entries.append({
            "transaction_id": transaction_id,
            "entry_date": transaction_date,
            "account_code": "4135",
            "debit": 0,
            "credit": subtotal,
            "description": f"Venta - {description}"
        })
        
        # Crédito: IVA por pagar (si hay impuesto)
        if tax_amount > 0:
            entries.append({
                "transaction_id": transaction_id,
                "entry_date": transaction_date,
                "account_code": "2408",
                "debit": 0,
                "credit": tax_amount,
                "description": f"IVA venta - {description}"
            })
    
    elif transaction_type == "purchase_invoice":
        # Débito: Gastos/Compras
        entries.append({
            "transaction_id": transaction_id,
            "entry_date": transaction_date,
            "account_code": "6205",
            "debit": subtotal,
            "credit": 0,
            "description": f"Compra - {description}"
        })
        
        # Débito: IVA descontable (si hay impuesto)
        if tax_amount > 0:
            entries.append({
                "transaction_id": transaction_id,
                "entry_date": transaction_date,
                "account_code": "2408",
                "debit": tax_amount,
                "credit": 0,
                "description": f"IVA compra - {description}"
            })
        
        # Crédito: Caja (activo disminuye)
        entries.append({
            "transaction_id": transaction_id,
            "entry_date": transaction_date,
            "account_code": "1105",
            "debit": 0,
            "credit": amount,
            "description": f"Pago compra - {description}"
        })
    
    return entries


def ingest_excel(filepath: Path) -> int:
    """Ingesta un Excel de facturas/transacciones con estructura robusta"""
    df: pd.DataFrame = read_excel(filepath)
    
    # Detectar si es factura de ventas o compras
    doc_type = "sales_invoice" if "Cliente" in df.columns or "cliente" in [c.lower() for c in df.columns] else "purchase_invoice"
    
    # Normalizar columnas
    df.columns = [col.lower().strip() for col in df.columns]
    
    # Mapeo flexible de columnas
    col_map = {
        "factura": "transaction_number",
        "fecha": "transaction_date",
        "cliente": "counterparty",
        "proveedor": "counterparty",
        "producto": "description",
        "cantidad": "quantity",
        "precio unitario": "unit_price",
        "subtotal": "subtotal",
        "iva": "tax_amount",
        "total": "amount",
    }
    
    # Aplicar mapeo
    for old_col, new_col in col_map.items():
        if old_col in df.columns:
            df.rename(columns={old_col: new_col}, inplace=True)
    
    doc_id = store_document(filepath, doc_type, None)
    
    transactions: List[dict] = []
    transaction_lines: List[dict] = []
    docs_to_index: List[Document] = []
    
    # Rastrear números de transacción únicos
    existing_tx_numbers = set()
    with get_connection() as conn:
        existing = conn.execute("SELECT transaction_number FROM transactions").fetchall()
        existing_tx_numbers = {row[0] for row in existing}
    
    for idx, row in df.iterrows():
        # Extraer valores principales
        transaction_number = str(row.get("transaction_number", f"AUTO-{idx}")).strip()
        
        # Asegurar unicidad - si hay duplicado, agregar sufijo
        original_tx_number = transaction_number
        counter = 1
        while transaction_number in existing_tx_numbers or any(t["transaction_number"] == transaction_number for t in transactions):
            transaction_number = f"{original_tx_number}-DUP{counter}"
            counter += 1
        
        existing_tx_numbers.add(transaction_number)
        
        transaction_date = str(row.get("transaction_date", datetime.now().date())).strip()
        counterparty = str(row.get("counterparty", "N/A")).strip()
        description = str(row.get("description", "Venta/Compra")).strip()
        
        # Montos
        try:
            quantity = float(row.get("quantity", 1)) if row.get("quantity") else 1
            unit_price = float(row.get("unit_price", 0)) if row.get("unit_price") else 0
            subtotal = float(row.get("subtotal", quantity * unit_price)) if row.get("subtotal") else quantity * unit_price
            tax_amount = float(row.get("tax_amount", 0)) if row.get("tax_amount") else 0
            amount = float(row.get("amount", subtotal + tax_amount)) if row.get("amount") else subtotal + tax_amount
        except (ValueError, TypeError):
            quantity, unit_price, subtotal, tax_amount, amount = 1, 0, 0, 0, 0
        
        # Insertar transacción
        tx_payload = {
            "document_id": doc_id,
            "transaction_date": transaction_date,
            "transaction_type": doc_type,
            "transaction_number": transaction_number,
            "counterparty": counterparty,
            "description": description,
            "amount": amount,
            "currency": "COP",
            "status": "completed"
        }
        transactions.append(tx_payload)
        
        # Insertar línea de detalle (para este MVP, guardamos como una línea)
        tx_line_payload = {
            "transaction_id": None,  # Se asignará después
            "line_number": 1,
            "account_code": "1000" if doc_type == "sales_invoice" else "2000",
            "account_name": "Ventas" if doc_type == "sales_invoice" else "Compras",
            "debit": amount if doc_type == "purchase_invoice" else 0,
            "credit": amount if doc_type == "sales_invoice" else 0,
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
            "tax_rate": 0.19 if tax_amount > 0 else 0,
            "tax_amount": tax_amount,
            "category": str(row.get("category", "General")).strip() if row.get("category") else "General"
        }
        transaction_lines.append(tx_line_payload)
        
        # Vectorizar
        docs_to_index.append(
            Document(
                page_content=f"{transaction_number} - {counterparty} - {description} - ${amount:,.2f}",
                metadata={"doc_id": doc_id, "type": "transaction", "date": transaction_date}
            )
        )
    
    # Insertar transacciones
    bulk_insert_transactions(transactions)
    
    # Obtener IDs de transacciones y actualizar líneas
    journal_entries_to_insert = []
    with get_connection() as conn:
        tx_ids = conn.execute(
            "SELECT id, transaction_date, transaction_type, amount, description FROM transactions WHERE document_id = ? ORDER BY rowid",
            (doc_id,)
        ).fetchall()
        
        for i, tx_row in enumerate(transaction_lines):
            if i < len(tx_ids):
                tx_id, tx_date, tx_type, tx_amount, tx_desc = tx_ids[i]
                tx_row["transaction_id"] = tx_id
                
                # Generar asientos contables para esta transacción
                entries = generate_journal_entries_for_transaction(
                    transaction_id=tx_id,
                    transaction_date=tx_date,
                    transaction_type=tx_type,
                    amount=tx_amount,
                    subtotal=tx_row["subtotal"],
                    tax_amount=tx_row["tax_amount"],
                    description=tx_desc
                )
                journal_entries_to_insert.extend(entries)
        
        bulk_insert_transaction_lines(transaction_lines)
        
        # Asegurar que existan las cuentas contables necesarias
        ensure_default_accounts()
        
        # Insertar asientos contables
        if journal_entries_to_insert:
            bulk_insert_journal_entries(journal_entries_to_insert)
            print(f"✅ Generados {len(journal_entries_to_insert)} asientos contables")
    
    # Indexar vectores
    try:
        index_documents(docs_to_index, get_embeddings())
        print(f"✅ Cargadas {len(transactions)} transacciones")
    except Exception as e:
        print(f"⚠️ Error indexando: {e}")
    
    return doc_id


def ingest_pdf(filepath: Path) -> int:
    """Ingesta un PDF para extracción de texto"""
    pages = read_pdf(filepath)
    raw_text = "\n\n".join(pages)
    doc_id = store_document(filepath, "pdf", raw_text)
    
    # Indexar páginas como documentos
    docs_to_index = [
        Document(
            page_content=page,
            metadata={"doc_id": doc_id, "type": "pdf", "page": i}
        )
        for i, page in enumerate(pages)
    ]
    
    try:
        index_documents(docs_to_index, get_embeddings())
        print(f"✅ PDF cargado: {len(pages)} páginas")
    except Exception as e:
        print(f"⚠️ Error indexando PDF: {e}")
    
    return doc_id