import os, sqlite3, datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
DB = "prodesa.db"

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS creditos (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, monto REAL, dias INTEGER, total REAL, cuota REAL, saldo REAL, fecha_inicio TEXT, fecha_fin TEXT, estado TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS abonos (id INTEGER PRIMARY KEY AUTOINCREMENT, credito_id INTEGER, codigo TEXT, monto REAL, fecha TEXT, tipo TEXT)")
    con.commit(); con.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 PRODESA\n/nuevo CODIGO MONTO DIAS TOTAL CUOTA\n/abono CODIGO MONTO\n/noabono CODIGO\n/saldo CODIGO")

async def nuevo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 5: await update.message.reply_text("Uso: /nuevo CODIGO MONTO DIAS TOTAL CUOTA"); return
    codigo, monto, dias, total, cuota = context.args[0], float(context.args[1]), int(context.args[2]), float(context.args[3]), float(context.args[4])
    con = sqlite3.connect(DB); cur = con.cursor()
    hoy = datetime.date.today(); fin = hoy + datetime.timedelta(days=dias)
    cur.execute("INSERT INTO creditos (codigo, monto, dias, total, cuota, saldo, fecha_inicio, fecha_fin, estado) VALUES (?,?,?,?,?,?,?,?,?)",(codigo, monto, dias, total, cuota, total, hoy.isoformat(), fin.isoformat(), "ACTIVO"))
    cid = cur.lastrowid; con.commit(); con.close()
    await update.message.reply_text(f"✅ CREDITO #{cid}\n{codigo} ${monto} -> ${total}\nComision 4%: ${monto*0.04:.2f}")

async def abono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: await update.message.reply_text("Uso: /abono CODIGO MONTO"); return
    codigo, monto = context.args[0], float(context.args[1])
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("SELECT id, saldo FROM creditos WHERE codigo=? AND estado='ACTIVO' ORDER BY id DESC LIMIT 1", (codigo,))
    row = cur.fetchone()
    if not row: await update.message.reply_text("No hay credito activo"); con.close(); return
    cid, saldo = row; ns = saldo - monto
    if ns <= 0: cur.execute("UPDATE creditos SET saldo=0, estado='CANCELADO' WHERE id=?", (cid,)); msg="🎉 CANCELADO"
    else: cur.execute("UPDATE creditos SET saldo=? WHERE id=?", (ns, cid)); msg=f"Saldo ${ns:.2f}"
    cur.execute("INSERT INTO abonos (credito_id, codigo, monto, fecha, tipo) VALUES (?,?,?,?,?)",(cid, codigo, monto, datetime.datetime.now().isoformat(), "ABONO"))
    con.commit(); con.close(); await update.message.reply_text(f"✅ ABONO ${monto} {codigo}\n{msg}")

async def noabono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1: await update.message.reply_text("Uso: /noabono CODIGO"); return
    codigo = context.args[0]; penal=0.45
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("SELECT id, saldo FROM creditos WHERE codigo=? AND estado='ACTIVO' ORDER BY id DESC LIMIT 1", (codigo,))
    row = cur.fetchone()
    if not row: await update.message.reply_text("No hay credito"); con.close(); return
    cid, saldo=row; ns=saldo+penal
    cur.execute("UPDATE creditos SET saldo=? WHERE id=?", (ns, cid))
    cur.execute("INSERT INTO abonos (credito_id, codigo, monto, fecha, tipo) VALUES (?,?,?,?,?)",(cid, codigo, penal, datetime.datetime.now().isoformat(), "PENALIZACION"))
    con.commit(); con.close(); await update.message.reply_text(f"⚠️ NO PAGO {codigo}\nPenal ${penal}\nNuevo saldo ${ns:.2f}")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1: await update.message.reply_text("Uso: /saldo CODIGO"); return
    codigo=context.args[0]; con=sqlite3.connect(DB); cur=con.cursor()
    cur.execute("SELECT id, monto, total, saldo, estado FROM creditos WHERE codigo=? ORDER BY id DESC", (codigo,))
    rows=cur.fetchall(); con.close()
    if not rows: await update.message.reply_text("Sin creditos"); return
    msg=f"📊 {codigo}\n"
    for r in rows[:10]: msg+=f"#{r[0]} ${r[1]}->{r[2]} Saldo ${r[3]} {r[4]}\n"
    await update.message.reply_text(msg)

if __name__=="__main__":
    init_db()
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nuevo", nuevo))
    app.add_handler(CommandHandler("abono", abono))
    app.add_handler(CommandHandler("noabono", noabono))
    app.add_handler(CommandHandler("saldo", saldo))
    app.run_polling()