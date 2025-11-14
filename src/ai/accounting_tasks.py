"""
Tareas contables disponibles que el agente puede ejecutar automáticamente.
"""

from typing import Dict, Any
from src.db.database import get_connection
from src.utils.logger import log_info


class AccountingTasks:
    """Colección de tareas contables que el agente puede ejecutar."""
    
    @staticmethod
    def balance_sheet(start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        Genera el balance general.
        Retorna activos, pasivos y patrimonio.
        
        Args:
            start_date: Fecha de inicio (YYYY-MM-DD), opcional
            end_date: Fecha de fin (YYYY-MM-DD), opcional
        """
        with get_connection() as conn:
            date_filter = ""
            params_activos = []
            params_pasivos = []
            params_patrimonio = []
            
            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append("date >= ?")
                    params_activos.append(start_date)
                    params_pasivos.append(start_date)
                    params_patrimonio.append(start_date)
                if end_date:
                    conditions.append("date <= ?")
                    params_activos.append(end_date)
                    params_pasivos.append(end_date)
                    params_patrimonio.append(end_date)
                date_filter = " AND " + " AND ".join(conditions)
            
            # Activos
            activos = conn.execute(f"""
                SELECT SUM(debit - credit) as total
                FROM journal_entries
                WHERE account_code LIKE '1%'{date_filter}
            """, params_activos).fetchone()[0] or 0
            
            # Pasivos
            pasivos = conn.execute(f"""
                SELECT SUM(credit - debit) as total
                FROM journal_entries
                WHERE account_code LIKE '2%'{date_filter}
            """, params_pasivos).fetchone()[0] or 0
            
            # Patrimonio
            patrimonio = conn.execute(f"""
                SELECT SUM(credit - debit) as total
                FROM journal_entries
                WHERE account_code LIKE '3%'{date_filter}
            """, params_patrimonio).fetchone()[0] or 0
            
            return {
                "activos": activos,
                "pasivos": pasivos,
                "patrimonio": patrimonio,
                "total_pasivo_patrimonio": pasivos + patrimonio
            }
    
    @staticmethod
    def income_statement(start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        Genera el estado de resultados.
        Retorna ingresos, gastos y utilidad neta.
        
        Args:
            start_date: Fecha de inicio (YYYY-MM-DD), opcional
            end_date: Fecha de fin (YYYY-MM-DD), opcional
        """
        with get_connection() as conn:
            date_filter = ""
            params_ingresos = []
            params_costos = []
            params_gastos = []
            
            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append("date >= ?")
                    params_ingresos.append(start_date)
                    params_costos.append(start_date)
                    params_gastos.append(start_date)
                if end_date:
                    conditions.append("date <= ?")
                    params_ingresos.append(end_date)
                    params_costos.append(end_date)
                    params_gastos.append(end_date)
                date_filter = " AND " + " AND ".join(conditions)
            
            # Ingresos (cuenta 4000)
            ingresos = conn.execute(f"""
                SELECT SUM(credit - debit) as total
                FROM journal_entries
                WHERE account_code LIKE '4%'{date_filter}
            """, params_ingresos).fetchone()[0] or 0
            
            # Costos (cuenta 5000)
            costos = conn.execute(f"""
                SELECT SUM(debit - credit) as total
                FROM journal_entries
                WHERE account_code LIKE '5%'{date_filter}
            """, params_costos).fetchone()[0] or 0
            
            # Gastos operacionales (cuenta 6000)
            gastos = conn.execute(f"""
                SELECT SUM(debit - credit) as total
                FROM journal_entries
                WHERE account_code LIKE '6%'{date_filter}
            """, params_gastos).fetchone()[0] or 0
            
            utilidad_bruta = ingresos - costos
            utilidad_neta = utilidad_bruta - gastos
            
            return {
                "ingresos": ingresos,
                "costos": costos,
                "utilidad_bruta": utilidad_bruta,
                "gastos_operacionales": gastos,
                "utilidad_neta": utilidad_neta
            }
    
    @staticmethod
    def sales_summary(year: int = None, month: int = None) -> Dict[str, Any]:
        """
        Resumen de ventas por período.
        """
        with get_connection() as conn:
            query = """
                SELECT 
                    COUNT(*) as total_facturas,
                    SUM(amount) as total_vendido,
                    AVG(amount) as promedio_factura,
                    MIN(amount) as factura_minima,
                    MAX(amount) as factura_maxima,
                    COUNT(DISTINCT counterparty) as clientes_unicos
                FROM transactions
                WHERE transaction_type = 'sales_invoice'
            """
            
            result = conn.execute(query).fetchone()
            
            return {
                "total_facturas": result[0] or 0,
                "total_vendido": result[1] or 0,
                "promedio_factura": result[2] or 0,
                "factura_minima": result[3] or 0,
                "factura_maxima": result[4] or 0,
                "clientes_unicos": result[5] or 0
            }
    
    @staticmethod
    def purchase_summary(year: int = None, month: int = None) -> Dict[str, Any]:
        """
        Resumen de compras por período.
        """
        with get_connection() as conn:
            query = """
                SELECT 
                    COUNT(*) as total_compras,
                    SUM(amount) as total_comprado,
                    AVG(amount) as promedio_compra,
                    MIN(amount) as compra_minima,
                    MAX(amount) as compra_maxima,
                    COUNT(DISTINCT counterparty) as proveedores_unicos
                FROM transactions
                WHERE transaction_type = 'purchase_invoice'
            """
            
            result = conn.execute(query).fetchone()
            
            return {
                "total_compras": result[0] or 0,
                "total_comprado": result[1] or 0,
                "promedio_compra": result[2] or 0,
                "compra_minima": result[3] or 0,
                "compra_maxima": result[4] or 0,
                "proveedores_unicos": result[5] or 0
            }
    
    @staticmethod
    def expenses_by_category(start_date: str = None, end_date: str = None) -> Dict[str, float]:
        """
        Desglose de gastos por categoría.
        
        Args:
            start_date: Fecha de inicio (YYYY-MM-DD), opcional
            end_date: Fecha de fin (YYYY-MM-DD), opcional
        """
        with get_connection() as conn:
            query = """
                SELECT 
                    category,
                    SUM(credit) as total
                FROM transaction_lines
                WHERE credit > 0
            """
            
            params = []
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += """
                GROUP BY category
                ORDER BY total DESC
            """
            
            results = conn.execute(query, params).fetchall()
            return {row[0]: row[1] for row in results}
    
    @staticmethod
    def cash_flow(start_date: str = None, end_date: str = None) -> Dict[str, float]:
        """
        Análisis de flujo de caja.
        
        Args:
            start_date: Fecha de inicio (YYYY-MM-DD), opcional
            end_date: Fecha de fin (YYYY-MM-DD), opcional
        """
        with get_connection() as conn:
            date_filter = ""
            params_ingresos = []
            params_egresos = []
            
            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append("date >= ?")
                    params_ingresos.append(start_date)
                    params_egresos.append(start_date)
                if end_date:
                    conditions.append("date <= ?")
                    params_ingresos.append(end_date)
                    params_egresos.append(end_date)
                date_filter = " AND " + " AND ".join(conditions)
            
            ingresos = conn.execute(f"""
                SELECT SUM(amount) FROM transactions 
                WHERE transaction_type = 'sales_invoice'{date_filter}
            """, params_ingresos).fetchone()[0] or 0
            
            egresos = conn.execute(f"""
                SELECT SUM(amount) FROM transactions 
                WHERE transaction_type = 'purchase_invoice'{date_filter}
            """, params_egresos).fetchone()[0] or 0
            
            return {
                "ingresos_totales": ingresos,
                "egresos_totales": egresos,
                "flujo_neto": ingresos - egresos
            }
    
    @staticmethod
    def aging_analysis() -> Dict[str, Any]:
        """
        Análisis de antigüedad de cuentas por cobrar.
        """
        with get_connection() as conn:
            query = """
                SELECT 
                    counterparty,
                    COUNT(*) as cantidad_facturas,
                    SUM(amount) as saldo_pendiente,
                    MAX(transaction_date) as ultima_transaccion
                FROM transactions
                WHERE transaction_type = 'sales_invoice' AND status = 'pending'
                GROUP BY counterparty
                ORDER BY saldo_pendiente DESC
            """
            
            results = conn.execute(query).fetchall()
            return [
                {
                    "cliente": row[0],
                    "facturas": row[1],
                    "saldo": row[2],
                    "ultima_transaccion": row[3]
                }
                for row in results
            ]
    
    @staticmethod
    def tax_summary() -> Dict[str, float]:
        """
        Resumen de impuestos (IVA, retenciones, etc).
        """
        with get_connection() as conn:
            iva_total = conn.execute("""
                SELECT SUM(tax_amount) FROM transaction_lines
            """).fetchone()[0] or 0
            
            ventas_iva = conn.execute("""
                SELECT SUM(tax_amount) FROM transaction_lines tl
                JOIN transactions t ON tl.transaction_id = t.id
                WHERE t.transaction_type = 'sales_invoice'
            """).fetchone()[0] or 0
            
            compras_iva = conn.execute("""
                SELECT SUM(tax_amount) FROM transaction_lines tl
                JOIN transactions t ON tl.transaction_id = t.id
                WHERE t.transaction_type = 'purchase_invoice'
            """).fetchone()[0] or 0
            
            return {
                "iva_total": iva_total,
                "iva_ventas": ventas_iva,
                "iva_compras": compras_iva,
                "iva_a_pagar": ventas_iva - compras_iva
            }
    
    @staticmethod
    def profit_margin_analysis() -> Dict[str, float]:
        """
        Análisis de márgenes de ganancia.
        """
        from src.ai.accounting_tasks import AccountingTasks
        
        income = AccountingTasks.income_statement()
        
        if income["ingresos"] == 0:
            return {
                "margen_bruto": 0,
                "margen_neto": 0
            }
        
        return {
            "margen_bruto": (income["utilidad_bruta"] / income["ingresos"]) * 100,
            "margen_neto": (income["utilidad_neta"] / income["ingresos"]) * 100
        }
    
    @staticmethod
    def trend_analysis(months: int = 6) -> Dict[str, Any]:
        """
        Análisis de tendencias en los últimos N meses.
        """
        with get_connection() as conn:
            query = f"""
                SELECT 
                    strftime('%Y-%m', transaction_date) as mes,
                    transaction_type,
                    SUM(amount) as total
                FROM transactions
                WHERE transaction_date >= date('now', '-{months} months')
                GROUP BY mes, transaction_type
                ORDER BY mes DESC
            """
            
            results = conn.execute(query).fetchall()
            return [
                {
                    "mes": row[0],
                    "tipo": row[1],
                    "monto": row[2]
                }
                for row in results
            ]


# Mapeo de tareas disponibles
AVAILABLE_TASKS = {
    "balance_sheet": AccountingTasks.balance_sheet,
    "income_statement": AccountingTasks.income_statement,
    "sales_summary": AccountingTasks.sales_summary,
    "purchase_summary": AccountingTasks.purchase_summary,
    "expenses_by_category": AccountingTasks.expenses_by_category,
    "cash_flow": AccountingTasks.cash_flow,
    "aging_analysis": AccountingTasks.aging_analysis,
    "tax_summary": AccountingTasks.tax_summary,
    "profit_margin": AccountingTasks.profit_margin_analysis,
    "trend_analysis": AccountingTasks.trend_analysis,
}
