import os
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import threading
from flask import Flask

# Flask para Render
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot Prodesa activo"
def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

TOKEN = os.getenv("BOT_TOKEN")
DB = "prodesa.db"

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS creditos (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE, monto REAL, dias INTEGER, total REAL, cuota REAL, saldo REAL, fecha TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS abonos (id INTEGER PRIMARY KEY AUTOINCREMENT, credito_id INTEGER, codigo TEXT, monto REAL, fecha TEXT, tipo TEXT)")
    conn.commit()
    conn.close()

async def Inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 PRODESA\n\n/nuevo CODIGO MONTO DIAS TOTAL CUOTA\n/abono CODIGO MONTO\n/noabono CODIGO\n/saldo CODIGO\n/diario")

async def Nuevo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 5:
        await update.message.reply_text("Uso: /nuevo CODIGO MONTO DIAS TOTAL CUOTA")
        return
    codigo, monto, dias, total, cuota = context.args[0], float(context.args[1]), int(context.args[2]), float(context.args[3]), float(context.args[4])
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO creditos (codigo, monto, dias, total, cuota, saldo, fecha) VALUES (?,?,?,?,?,?,?)",
                    (codigo, monto, dias, total, cuota, total, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        await update.message.reply_text(f"✅ Crédito {codigo} guardado")
    except:
        await update.message.reply_text("❌ Ese código ya existe")
    conn.close()

async def Abono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /abono CODIGO MONTO")
        return
    codigo, monto = context.args[0], float(context.args[1])
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id, saldo FROM creditos WHERE codigo=?", (codigo,))
    row = cur.fetchone()
    if row:
        nuevo = row[1] - monto
        cur.execute("UPDATE creditos SET saldo=? WHERE id=?", (nuevo, row[0]))
        cur.execute("INSERT INTO abonos (credito_id, codigo, monto, fecha, tipo) VALUES (?,?,?,?,?)",
                    (row[0], codigo, monto, datetime.now().strftime("%Y-%m-%d %H:%M"), "ABONO"))
        conn.commit()
        await update.message.reply_text(f"✅ Abono {monto} a {codigo}. Saldo: {nuevo}")
    conn.close()

async def Saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = context.args[0] if context.args else ""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT monto, saldo, cuota FROM creditos WHERE codigo=?", (codigo,))
    r = cur.fetchone()
    await update.message.reply_text(f"{codigo} Saldo: {r[1]}" if r else "No encontrado")
    conn.close()

async def Diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT codigo, saldo, cuota FROM creditos WHERE saldo > 0")
    rows = cur.fetchall()
    txt = "📊 DIARIO\n\n" + "\n".join([f"{c} | Saldo: {s} | Cuota: {q}" for c,s,q in rows]) if rows else "Sin pendientes"
    await update.message.reply_text(txt)
    conn.close()

def main():
    init_db()
    threading.Thread(target=run_web, daemon=True).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", Inicio))
    application.add_handler(CommandHandler("nuevo", Nuevo))
    application.add_handler(CommandHandler("abono", Abono))
    application.add_handler(CommandHandler("saldo", Saldo))
    application.add_handler(CommandHandler("diario", Diario))
    application.add_handler(CommandHandler("contra", Diario))
    application.add_handler(CommandHandler("recordatorio", Diario))
    # ESTO ES LO QUE CAMBIA - SIN ASYNCIO
    application.run_polling()

if __name__ == "__main__":
    main()
