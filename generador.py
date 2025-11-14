import os
import random
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from openpyxl import Workbook

# ===============================
# CONFIGURACIÓN
# ===============================
NUM_INVOICES = 20  # cantidad de PDFs a generar
OUTPUT_FOLDER = "facturas_pdf"

# Crear carpeta si no existe
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ===============================
# FUNCIONES PARA GENERAR DATOS
# ===============================

def random_date(start, end):
    """Fecha aleatoria entre start y end."""
    return start + timedelta(days=random.randint(0, (end - start).days))

def random_company_name():
    empresas = [
        "Comercial ABC Ltda", "Distribuciones El Roble SAS", "Servicios Omega",
        "Industrias Altavista", "Logística Norte SA", "Insumos y Partes Medellín",
        "TecnoProyectos SAS", "Electrocomercial Andina"
    ]
    return random.choice(empresas)

def random_items():
    productos = [
        "Producto A", "Producto B", "Servicio Técnico", "Consultoría",
        "Repuesto Industrial", "Material de Construcción", "Software Licencia"
    ]
    return random.choice(productos), random.randint(1, 10), random.randint(10000, 150000)

# ===============================
# FUNCIÓN PARA CREAR PDF DE FACTURA
# ===============================

def generar_pdf_factura(num):
    factura_id = f"F-{1000 + num}"
    nombre_pdf = f"{OUTPUT_FOLDER}/factura_{factura_id}.pdf"
    c = canvas.Canvas(nombre_pdf, pagesize=letter)

    # Datos base
    fecha = random_date(datetime(2023, 1, 1), datetime(2023, 12, 31)).strftime("%Y-%m-%d")
    cliente = random_company_name()
    producto, cantidad, precio = random_items()
    subtotal = cantidad * precio
    iva = subtotal * 0.19
    total = subtotal + iva

    # ===============================
    # DISEÑO DEL PDF
    # ===============================
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, f"Factura {factura_id}")

    c.setFont("Helvetica", 12)
    c.drawString(50, 720, f"Fecha: {fecha}")
    c.drawString(50, 700, f"Cliente: {cliente}")

    c.drawString(50, 660, f"Descripción: {producto}")
    c.drawString(50, 640, f"Cantidad: {cantidad}")
    c.drawString(50, 620, f"Precio unitario: ${precio:,.0f}")

    c.drawString(50, 580, f"Subtotal: ${subtotal:,.0f}")
    c.drawString(50, 560, f"IVA (19%): ${iva:,.0f}")
    c.drawString(50, 540, f"TOTAL: ${total:,.0f}")

    c.save()

    return {
        "Factura": factura_id,
        "Fecha": fecha,
        "Cliente": cliente,
        "Producto": producto,
        "Cantidad": cantidad,
        "Precio Unitario": precio,
        "Subtotal": subtotal,
        "IVA": iva,
        "Total": total
    }

# ===============================
# GENERAR EXCEL
# ===============================

def generar_excel(resumen):
    wb = Workbook()
    ws = wb.active
    ws.title = "Facturas"

    headers = [
        "Factura", "Fecha", "Cliente", "Producto", "Cantidad",
        "Precio Unitario", "Subtotal", "IVA", "Total"
    ]
    ws.append(headers)

    for r in resumen:
        ws.append([
            r["Factura"], r["Fecha"], r["Cliente"], r["Producto"],
            r["Cantidad"], r["Precio Unitario"], r["Subtotal"],
            r["IVA"], r["Total"]
        ])

    wb.save("facturas_resumen.xlsx")

# ===============================
# EJECUCIÓN
# ===============================

if __name__ == "__main__":
    resumen = []

    for i in range(NUM_INVOICES):
        info = generar_pdf_factura(i)
        resumen.append(info)

    generar_excel(resumen)

    print("Generación completa:")
    print(f"- {NUM_INVOICES} PDFs creados en la carpeta '{OUTPUT_FOLDER}'")
    print("- Archivo Excel 'facturas_resumen.xlsx' creado")
