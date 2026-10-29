# bot.py - CON COMISIÓN POR OTORGAMIENTO
import os
import sqlite3

DB = "creditos.db"

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS creditos (
        codigo TEXT PRIMARY KEY,
        monto REAL,
        total_sin_comision REAL,
        cuota REAL,
        dias INTEGER,
        comision_otorg REAL,
        saldo_total REAL,
        saldo_pendiente REAL
    )""")
    con.commit()
    con.close()

def nuevo_credito(codigo, monto, total_sin, cuota, dias):
    comision = round(monto * 0.04, 2)  # 4% por otorgamiento
    saldo_total = round(total_sin + comision, 2)
    
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("INSERT OR REPLACE INTO creditos VALUES (?,?,?,?,?,?,?,?)",
                (codigo, monto, total_sin, cuota, dias, comision, saldo_total, saldo_total))
    con.commit()
    con.close()
    return comision, saldo_total

def abonar(codigo, monto_abono):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT saldo_pendiente FROM creditos WHERE codigo=?", (codigo,))
    row = cur.fetchone()
    if not row:
        con.close()
        return None
    nuevo_saldo = round(row[0] - monto_abono, 2)
    cur.execute("UPDATE creditos SET saldo_pendiente=? WHERE codigo=?", (nuevo_saldo, codigo))
    con.commit()
    con.close()
    return nuevo_saldo

def get_credito(codigo):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT * FROM creditos WHERE codigo=?", (codigo,))
    row = cur.fetchone()
    con.close()
    return row

def diario():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT codigo, saldo_pendiente, cuota, comision_otorg, total_sin_comision, saldo_total FROM creditos WHERE saldo_pendiente > 0")
    rows = cur.fetchall()
    con.close()
    return rows

# --- HANDLERS PARA TELEGRAM (ejemplo con python-telegram-bot) ---
# En tu comando /nuevo
# /nuevo FMGM0230 150 209.65 5.99 35
# monto=150, total_sin=209.65, cuota=5.99, dias=35

# Mensaje de respuesta para /nuevo:
# f"✅ Crédito {codigo} guardado\nMonto: {monto}\nTotal s/comisión: {total_sin}\nComisión otorg (4%): {comision}\nSALDO TOTAL A COBRAR: {saldo_total}\nCuota: {cuota}"

# Mensaje para /saldo FMGM0230:
# f"{codigo}\nSaldo total: {saldo_total} = {total_sin} + {comision} comisión\nPendiente: {saldo_pendiente}\nCuota: {cuota}"

init_db()
# Mensaje para /saldo FMGM0230:
# f"{codigo}\nSaldo total: {saldo_total} = {total_sin} + {comision} comisión\nPendiente: {saldo_pendiente}\nCuota: {cuota}"

init_db()
