import os, sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
DB = "prodesa.db"
TASA_DIARIA = 0.01136 # 1.136% diario - sale de tu ejemplo 150->209.65 en 35 dias

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS creditos (
        codigo TEXT PRIMARY KEY, nombre TEXT, monto REAL, dias INTEGER,
        cuota REAL, total_sin REAL, comision REAL, saldo_total REAL, saldo_pend REAL,
        fecha_otorg TEXT, fecha_venc TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, fecha TEXT, monto REAL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS feriados (fecha TEXT PRIMARY KEY)""")
    con.commit(); con.close()

def es_habil(fecha_str, feriados):
    dt = datetime.strptime(fecha_str, "%d/%m/%Y")
    return dt.weekday() < 5 and fecha_str not in feriados

def get_feriados():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT fecha FROM feriados")
    f = [r[0] for r in cur.fetchall()]
    con.close()
    return set(f)

def calcular_vencimiento(fecha_inicio_str, dias):
    feriados = get_feriados()
    dt = datetime.strptime(fecha_inicio_str, "%d/%m/%Y")
    cont = 0
    while cont < dias:
        dt += timedelta(days=1)
        fs = dt.strftime("%d/%m/%Y")
        if es_habil(fs, feriados):
            cont += 1
    return dt.strftime("%d/%m/%Y")

def get_penal(monto):
    if monto < 200: return 0.45
    if monto < 400: return 0.55
    return 0.90

async def nuevo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text("Uso: /nuevo CODIGO NOMBRE MONTO DIAS [FECHA DD/MM/AAAA]\nEj: /nuevo FMGM0230 Juan 150 35 29/10/2026")
        return
    codigo = args[0].upper()
    nombre = args[1]
    monto = float(args[2])
    dias = int(args[3])
    fecha_otorg = args[4] if len(args)>=5 else datetime.now().strftime("%d/%m/%Y")
    
    comision = round(monto * 0.04, 2)
    interes = round(monto * TASA_DIARIA * dias, 2)
    total_sin = round(monto + interes, 2)
    cuota = round(total_sin / dias, 2)
    saldo_total = round(total_sin + comision, 2)
    fecha_venc = calcular_vencimiento(fecha_otorg, dias)

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("INSERT OR REPLACE INTO creditos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (codigo, nombre, monto, dias, cuota, total_sin, comision, saldo_total, saldo_total, fecha_otorg, fecha_venc))
    con.commit(); con.close()
    await update.message.reply_text(
        f"✅ CREDITO CREADO\n\nCliente: {nombre} ({codigo})\nMonto: ${monto}\n"
        f"Días: {dias} | Otorg: {fecha_otorg} | Venc: {fecha_venc}\n"
        f"Comisión 4%: ${comision} ({monto}x0.04)\nInterés: ${interes}\nCuota: ${cuota}\n"
        f"SALDO TOTAL: ${saldo_total} = ${total_sin} + ${comision} comisión")

async def saldo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /saldo CODIGO")
        return
    codigo = context.args[0].upper()
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT * FROM creditos WHERE codigo=?", (codigo,))
    r = cur.fetchone()
    con.close()
    if not r: 
        await update.message.reply_text("No existe"); return
    _, nombre, monto, dias, cuota, total_sin, comision, saldo_total, saldo_pend, f_otorg, f_venc = r
    await update.message.reply_text(f"📋 {nombre} ({codigo})\nSaldo total: ${saldo_total} ({total_sin}+{comision})\nPendiente: ${saldo_pend}\nCuota: ${cuota} x {dias}d\nVenc: {f_venc}\nPenal/día: ${get_penal(monto)}")

async def abono_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = context.args[0].upper(); ab = float(context.args[1])
    fecha = context.args[2] if len(context.args)>=3 else datetime.now().strftime("%d/%m/%Y")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT saldo_pend FROM creditos WHERE codigo=?", (codigo,))
    row = cur.fetchone()
    if not row:
        await update.message.reply_text("No existe"); return
    nuevo = round(row[0] - ab, 2)
    if nuevo < 0: nuevo = 0
    cur.execute("UPDATE creditos SET saldo_pend=? WHERE codigo=?", (nuevo, codigo))
    cur.execute("INSERT INTO pagos (codigo, fecha, monto) VALUES (?,?,?)", (codigo, fecha, ab))
    con.commit(); con.close()
    await update.message.reply_text(f"✅ Abono ${ab} a {codigo}\nPendiente: ${nuevo}")

# ... (resto comandos reporte, diario, feriado igual que antes) ...

if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("nuevo", nuevo))
    app.add_handler(CommandHandler("saldo", saldo_cmd))
    app.add_handler(CommandHandler("abono", abono_cmd))
    print("Bot Prodesa corriendo...")
    app.run_polling()
