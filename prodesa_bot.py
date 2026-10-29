import os
import threading
import asyncio
import sqlite3
from datetime import date, timedelta
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- FLASK PARA RENDER FREE (NO BORRAR) ---
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): 
    return "Bot Prodesa Live - OK"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)
# ------------------------------------------

# --- LOGICA DE CREDITOS ---
FERIADOS = {
    date(2025,1,1), date(2025,4,17), date(2025,4,18), date(2025,5,1), date(2025,6,17), date(2025,8,6), date(2025,9,15), date(2025,11,2), date(2025,12,25),
    date(2026,1,1), date(2026,4,2), date(2026,4,3), date(2026,5,1), date(2026,6,17), date(2026,8,6), date(2026,9,15), date(2026,11,2), date(2026,12,25),
}
def es_habil(d: date): return d.weekday() < 5 and d not in FERIADOS
def add_dias_habiles(inicio: date, dias: int):
    d = inicio; agregados = 0
    while agregados < dias - 1:
        d += timedelta(days=1)
        if es_habil(d): agregados += 1
    return d
def contar_mora(desde: date, hasta: date):
    mora=0; d=desde+timedelta(days=1)
    while d <= hasta:
        if es_habil(d): mora+=1
        d+=timedelta(days=1)
    return mora
def penalizacion_por_monto(monto: float):
    if 25 <= monto <= 199.99: return 0.45
    if 200 <= monto <= 399.99: return 0.55
    if monto >= 400: return 0.90
    return 0.0
def db():
    con = sqlite3.connect("prodesa.db")
    con.execute("CREATE TABLE IF NOT EXISTS creditos (codigo TEXT PRIMARY KEY, monto REAL, fecha_otorgamiento TEXT, fecha_vencimiento TEXT, plazo INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, monto REAL, fecha TEXT)")
    return con

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("PRODESA SV - Créditos\n/nuevo CODIGO MONTO PLAZO\nEj: /nuevo C001 300 30\n/saldo CODIGO\n/pago CODIGO MONTO\n/reporte CODIGO\n/reporte_general\n/clientes")

async def nuevo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo=context.args[0].upper(); monto=float(context.args[1]); plazo=int(context.args[2])
        hoy=date.today(); venc=add_dias_habiles(hoy, plazo)
        con=db(); con.execute("INSERT OR REPLACE INTO creditos VALUES (?,?,?,?,?)", (codigo, monto, hoy.isoformat(), venc.isoformat(), plazo)); con.commit(); con.close()
        await update.message.reply_text(f"✅ {codigo} creado\nMonto ${monto}\nOtorgado {hoy}\nVence {venc} ({plazo} días hábiles)\nPenal ${penalizacion_por_monto(monto)}/día")
    except Exception as e: await update.message.reply_text("Usa: /nuevo CODIGO MONTO PLAZO Ej: /nuevo C001 300 30")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo=context.args[0].upper(); con=db(); cur=con.cursor()
        c=cur.execute("SELECT * FROM creditos WHERE codigo=?", (codigo,)).fetchone()
        if not c: await update.message.reply_text("Código no encontrado"); return
        _, monto, f_otorg, f_venc, plazo = c; f_venc_d=date.fromisoformat(f_venc); hoy=date.today()
        pagado=cur.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE codigo=?", (codigo,)).fetchone()[0]
        dias=contar_mora(f_venc_d, hoy) if hoy>f_venc_d else 0; penal=dias*penalizacion_por_monto(monto); total=monto-pagado+penal; con.close()
        await update.message.reply_text(f"💳 {codigo}\nMonto ${monto}\nOtorg {f_otorg}\nVence {f_venc}\nPagado ${pagado}\nMora {dias} días (L-V sin asueto)\nPenal ${penal:.2f}\nSALDO ${total:.2f}")
    except: await update.message.reply_text("Usa: /saldo CODIGO")

async def pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo=context.args[0].upper(); monto=float(context.args[1])
        con=db(); con.execute("INSERT INTO pagos (codigo, monto, fecha) VALUES (?,?,?)", (codigo, monto, date.today().isoformat())); con.commit(); con.close()
        await update.message.reply_text(f"Pago ${monto} para {codigo} OK")
    except: await update.message.reply_text("Usa: /pago CODIGO MONTO")

async def reporte_general(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con=db(); cur=con.cursor(); creditos=cur.execute("SELECT * FROM creditos").fetchall()
    texto="📊 REPORTE GENERAL\n\n"; total=0; mora_c=0
    for cod, mon, f_o, f_v, pla in creditos:
        f_v_d=date.fromisoformat(f_v); hoy=date.today()
        pag=cur.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE codigo=?", (cod,)).fetchone()[0]
        d=contar_mora(f_v_d, hoy) if hoy>f_v_d else 0; p=d*penalizacion_por_monto(mon); saldo_p=mon-pag+p; total+=saldo_p
        if d>0: mora_c+=1
        texto+=f"{cod}: ${saldo_p:.2f} mora {d}d\n"
    texto+=f"\nCartera ${total:.2f}\nEn mora: {mora_c}"; con.close()
    await update.message.reply_text(texto)

async def clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con=db(); rows=con.execute("SELECT codigo, monto, fecha_vencimiento FROM creditos").fetchall(); con.close()
    if not rows: await update.message.reply_text("Sin clientes"); return
    await update.message.reply_text("\n".join([f"{r[0]} ${r[1]} vence {r[2]}" for r in rows]))

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    try: asyncio.set_event_loop(asyncio.new_event_loop())
    except: pass
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN: print("ERROR: No hay BOT_TOKEN"); return
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nuevo", nuevo))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("pago", pago))
    app.add_handler(CommandHandler("reporte", saldo))
    app.add_handler(CommandHandler("reporte_general", reporte_general))
    app.add_handler(CommandHandler("clientes", clientes))
    print("Bot Prodesa corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
