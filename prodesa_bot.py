import os
import threading
import asyncio
import sqlite3
from datetime import date, timedelta
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "Bot Prodesa Live - OK"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

FERIADOS = {
    date(2025,1,1), date(2025,4,17), date(2025,4,18), date(2025,5,1), date(2025,6,17), date(2025,8,6), date(2025,9,15), date(2025,11,2), date(2025,12,25),
    date(2026,1,1), date(2026,4,2), date(2026,4,3), date(2026,5,1), date(2026,6,17), date(2026,8,6), date(2026,9,15), date(2026,11,2), date(2026,12,25),
}
def es_habil(d: date): return d.weekday() < 5 and d not in FERIADOS
def add_dias_habiles(inicio: date, dias: int):
    d = inicio; c = 0
    while c < dias - 1:
        d += timedelta(days=1)
        if es_habil(d): c+=1
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
    con.execute("CREATE TABLE IF NOT EXISTS creditos (codigo TEXT PRIMARY KEY, monto REAL, plazo INTEGER, cuota REAL, comision REAL, total_pagar REAL, fecha_otorgamiento TEXT, fecha_vencimiento TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, monto REAL, fecha TEXT)")
    return con

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "PRODESA SV - CRUD COMPLETO\n\n"
        "CREAR: /nuevo CODIGO MONTO PLAZO CUOTA\nEj: /nuevo C001 300 30 12\n\n"
        "VER: /saldo CODIGO\nLISTAR: /clientes\nREPORTE: /reporte_general\n\n"
        "EDITAR: /editar CODIGO MONTO PLAZO CUOTA\nEj: /editar C001 350 30 13\n\n"
        "BORRAR: /eliminar CODIGO\n\n"
        "PAGO: /pago CODIGO MONTO\n\n"
        "Fórmula: (Cuota*Plazo)+(Monto*0.04)"
    )

async def nuevo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo=context.args[0].upper(); monto=float(context.args[1]); plazo=int(context.args[2]); cuota=float(context.args[3])
        total_cuotas=cuota*plazo; comision=monto*0.04; total_pagar=total_cuotas+comision; hoy=date.today(); venc=add_dias_habiles(hoy, plazo)
        con=db(); con.execute("INSERT INTO creditos VALUES (?,?,?,?,?,?,?,?)", (codigo, monto, plazo, cuota, comision, total_pagar, hoy.isoformat(), venc.isoformat())); con.commit(); con.close()
        await update.message.reply_text(f"✅ {codigo} CREADO\nTotal: ${total_pagar} (Cuotas ${total_cuotas}+Comisión ${comision})\nVence: {venc}")
    except Exception as e:
        await update.message.reply_text(f"Error /nuevo CODIGO MONTO PLAZO CUOTA {e}")

async def editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo=context.args[0].upper(); monto=float(context.args[1]); plazo=int(context.args[2]); cuota=float(context.args[3])
        total_cuotas=cuota*plazo; comision=monto*0.04; total_pagar=total_cuotas+comision
        con=db(); cur=con.cursor(); existe=cur.execute("SELECT fecha_otorgamiento FROM creditos WHERE codigo=?", (codigo,)).fetchone()
        if not existe: await update.message.reply_text("Código no existe"); return
        f_otorg=date.fromisoformat(existe[0]); venc=add_dias_habiles(f_otorg, plazo)
        con.execute("UPDATE creditos SET monto=?, plazo=?, cuota=?, comision=?, total_pagar=?, fecha_vencimiento=? WHERE codigo=?", (monto, plazo, cuota, comision, total_pagar, venc.isoformat(), codigo)); con.commit(); con.close()
        await update.message.reply_text(f"✏️ {codigo} ACTUALIZADO\nNuevo Total: ${total_pagar}\nNuevo venc: {venc}")
    except Exception as e:
        await update.message.reply_text(f"Error /editar CODIGO MONTO PLAZO CUOTA {e}")

async def eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo=context.args[0].upper()
        con=db(); con.execute("DELETE FROM creditos WHERE codigo=?", (codigo,)); con.execute("DELETE FROM pagos WHERE codigo=?", (codigo,)); con.commit(); con.close()
        await update.message.reply_text(f"🗑️ {codigo} ELIMINADO con todos sus pagos")
    except Exception as e:
        await update.message.reply_text(f"Error /eliminar CODIGO {e}")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo=context.args[0].upper(); con=db(); cur=con.cursor(); c=cur.execute("SELECT * FROM creditos WHERE codigo=?", (codigo,)).fetchone()
        if not c: await update.message.reply_text("No existe"); return
        _, monto, plazo, cuota, comision, total_pagar, f_otorg, f_venc = c; f_venc_d=date.fromisoformat(f_venc); hoy=date.today()
        pagado=cur.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE codigo=?", (codigo,)).fetchone()[0]
        dias=contar_mora(f_venc_d, hoy) if hoy>f_venc_d else 0; penal=dias*penalizacion_por_monto(monto); saldo_f=total_pagar-pagado+penal; con.close()
        await update.message.reply_text(f"💳 {codigo}\nCuota ${cuota} x {plazo} = ${cuota*plazo}\nComisión 4%: ${comision}\nTOTAL: ${total_pagar}\nPagado: ${pagado}\nMora: {dias}d Penal: ${penal:.2f}\n👉 SALDO: ${saldo_f:.2f}")
    except Exception as e:
        await update.message.reply_text(f"/saldo CODIGO {e}")

async def pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo=context.args[0].upper(); monto=float(context.args[1])
        con=db(); con.execute("INSERT INTO pagos VALUES (NULL,?,?,?)", (codigo, monto, date.today().isoformat())); con.commit(); con.close()
        await update.message.reply_text(f"Pago ${monto} OK"); await saldo(update, context)
    except: await update.message.reply_text("/pago CODIGO MONTO")

async def clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con=db(); rows=con.execute("SELECT codigo, total_pagar FROM creditos").fetchall(); con.close()
    await update.message.reply_text("\n".join([f"{r[0]} - Total ${r[1]}" for r in rows]) if rows else "Sin clientes")

async def reporte_general(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con=db(); cur=con.cursor(); creditos=cur.execute("SELECT * FROM creditos").fetchall(); txt="📊 REPORTE\n\n"; total=0; mora=0
    for codigo, monto, plazo, cuota, comision, total_pagar, f_otorg, f_venc in creditos:
        f_venc_d=date.fromisoformat(f_venc); hoy=date.today(); pag=cur.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE codigo=?", (codigo,)).fetchone()[0]
        d=contar_mora(f_venc_d, hoy) if hoy>f_venc_d else 0; p=d*penalizacion_por_monto(monto); saldo_f=total_pagar-pag+p; total+=saldo_f
        if d>0: mora+=1
        txt+=f"{codigo}: Saldo ${saldo_f:.2f} Mora {d}d\n"
    txt+=f"\nCartera: ${total:.2f}\nEn mora: {mora}"; con.close(); await update.message.reply_text(txt)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    try: asyncio.set_event_loop(asyncio.new_event_loop())
    except: pass
    TOKEN = os.environ.get("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("nuevo", nuevo))
    app.add_handler(CommandHandler("editar", editar)); app.add_handler(CommandHandler("eliminar", eliminar))
    app.add_handler(CommandHandler("saldo", saldo)); app.add_handler(CommandHandler("pago", pago))
    app.add_handler(CommandHandler("clientes", clientes)); app.add_handler(CommandHandler("reporte_general", reporte_general))
    print("Bot Prodesa corriendo..."); app.run_polling()

if __name__ == "__main__": main()
