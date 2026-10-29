import os
import telebot
import psycopg2
from datetime import datetime

TOKEN = os.environ.get('BOT_TOKEN') or 'PEGA_TU_TOKEN_AQUI'
DATABASE_URL = os.environ.get('DATABASE_URL')

bot = telebot.TeleBot(TOKEN)
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
conn.autocommit = True
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS clientes (codigo TEXT PRIMARY KEY, nombre TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS creditos (id SERIAL PRIMARY KEY, codigo TEXT, monto REAL, dias INTEGER, total REAL, cuota REAL, comision REAL, saldo REAL, fecha_inicio TEXT, fecha_fin TEXT, estado TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS abonos (id SERIAL PRIMARY KEY, credito_id INTEGER, codigo TEXT, fecha TEXT, monto REAL, penalizacion REAL, saldo_restante REAL)''')

def parse_fecha(txt):
    if not txt:
        return datetime.now().strftime("%d/%m/%Y")
    return txt

@bot.message_handler(commands=['nuevo'])
def nuevo(m):
    try:
        p = m.text.split()
        if len(p) < 6:
            bot.reply_to(m, "Usa: /nuevo CODIGO MONTO DIAS TOTAL CUOTA [FECHA]\nEj: /nuevo FMGM0230 100 26 126 4.5 28/10/2025")
            return
        _, codigo, monto, dias, total, cuota = p[:6]
        fecha = parse_fecha(p[6]) if len(p) > 6 else datetime.now().strftime("%d/%m/%Y")
        monto, dias, total, cuota = float(monto), int(dias), float(total), float(cuota)
        comision = monto * 0.04
        c.execute("INSERT INTO clientes (codigo) VALUES (%s) ON CONFLICT (codigo) DO NOTHING", (codigo,))
        c.execute("INSERT INTO creditos (codigo, monto, dias, total, cuota, comision, saldo, fecha_inicio, estado) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id", (codigo, monto, dias, total, cuota, comision, total, fecha, 'ACTIVO'))
        cid = c.fetchone()[0]
        bot.reply_to(m, f"✅ CREDITO #{cid} CREADO\nCliente: {codigo}\nPrestado: ${monto} Total: ${total}\nInicio: {fecha}\nComision: ${comision}\nGuardado para siempre")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

@bot.message_handler(commands=['abono'])
def abono(m):
    try:
        p = m.text.split()
        codigo, monto_abono = p[1], float(p[2])
        fecha = parse_fecha(p[3]) + " 12:00" if len(p) > 3 else datetime.now().strftime("%d/%m/%Y %H:%M")
        c.execute("SELECT id, saldo FROM creditos WHERE codigo=%s AND estado='ACTIVO' ORDER BY id DESC LIMIT 1", (codigo,))
        row = c.fetchone()
        if not row:
            bot.reply_to(m, f"❌ {codigo} sin activos"); return
        cid, saldo = row
        nuevo = saldo - monto_abono
        c.execute("UPDATE creditos SET saldo=%s WHERE id=%s", (nuevo, cid))
        c.execute("INSERT INTO abonos (credito_id, codigo, fecha, monto, penalizacion, saldo_restante) VALUES (%s,%s,%s,%s,%s,%s)", (cid, codigo, fecha, monto_abono, 0, nuevo))
import os
import telebot
import psycopg2
from datetime import datetime

TOKEN = os.environ.get('BOT_TOKEN') or 'PEGA_TU_TOKEN_AQUI'
DATABASE_URL = os.environ.get('DATABASE_URL')

bot = telebot.TeleBot(TOKEN)
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
conn.autocommit = True
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS clientes (codigo TEXT PRIMARY KEY, nombre TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS creditos (id SERIAL PRIMARY KEY, codigo TEXT, monto REAL, dias INTEGER, total REAL, cuota REAL, comision REAL, saldo REAL, fecha_inicio TEXT, fecha_fin TEXT, estado TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS abonos (id SERIAL PRIMARY KEY, credito_id INTEGER, codigo TEXT, fecha TEXT, monto REAL, penalizacion REAL, saldo_restante REAL)''')

def parse_fecha(txt):
    if not txt:
        return datetime.now().strftime("%d/%m/%Y")
    return txt

@bot.message_handler(commands=['nuevo'])
def nuevo(m):
    try:
        p = m.text.split()
        if len(p) < 6:
            bot.reply_to(m, "Usa: /nuevo CODIGO MONTO DIAS TOTAL CUOTA [FECHA]\nEj: /nuevo FMGM0230 100 26 126 4.5 28/10/2025")
            return
        _, codigo, monto, dias, total, cuota = p[:6]
        fecha = parse_fecha(p[6]) if len(p) > 6 else datetime.now().strftime("%d/%m/%Y")
        monto, dias, total, cuota = float(monto), int(dias), float(total), float(cuota)
        comision = monto * 0.04
        c.execute("INSERT INTO clientes (codigo) VALUES (%s) ON CONFLICT (codigo) DO NOTHING", (codigo,))
        c.execute("INSERT INTO creditos (codigo, monto, dias, total, cuota, comision, saldo, fecha_inicio, estado) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id", (codigo, monto, dias, total, cuota, comision, total, fecha, 'ACTIVO'))
        cid = c.fetchone()[0]
        bot.reply_to(m, f"✅ CREDITO #{cid} CREADO\nCliente: {codigo}\nPrestado: ${monto} Total: ${total}\nInicio: {fecha}\nComision: ${comision}\nGuardado para siempre")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

@bot.message_handler(commands=['abono'])
def abono(m):
    try:
        p = m.text.split()
        codigo, monto_abono = p[1], float(p[2])
        fecha = parse_fecha(p[3]) + " 12:00" if len(p) > 3 else datetime.now().strftime("%d/%m/%Y %H:%M")
        c.execute("SELECT id, saldo FROM creditos WHERE codigo=%s AND estado='ACTIVO' ORDER BY id DESC LIMIT 1", (codigo,))
        row = c.fetchone()
        if not row:
            bot.reply_to(m, f"❌ {codigo} sin activos"); return
        cid, saldo = row
        nuevo = saldo - monto_abono
        c.execute("UPDATE creditos SET saldo=%s WHERE id=%s", (nuevo, cid))
        c.execute("INSERT INTO abonos (credito_id, codigo, fecha, monto, penalizacion, saldo_restante) VALUES (%s,%s,%s,%s,%s,%s)", (cid, codigo, fecha, monto_abono, 0, nuevo))
        if nuevo <= 0:
            c.execute("UPDATE creditos SET estado='CANCELADO', fecha_fin=%s WHERE id=%s", (fecha, cid))
            bot.reply_to(m, f"🎉 CREDITO #{cid} CANCELADO\n{codigo} abonó ${monto_abono} el {fecha}")
        else:
            bot.reply_to(m, f"💰 #{cid} {codigo} abonó ${monto_abono}\nFecha: {fecha}\nSaldo: ${nuevo:.2f}")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

@bot.message_handler(commands=['noabono'])
def noabono(m):
    try:
        p = m.text.split()
        codigo = p[1]
        fecha = parse_fecha(p[2]) + " 12:00" if len(p) > 2 else datetime.now().strftime("%d/%m/%Y %H:%M")
        c.execute("SELECT id, saldo FROM creditos WHERE codigo=%s AND estado='ACTIVO' ORDER BY id DESC LIMIT 1", (codigo,))
        row = c.fetchone()
        if not row: bot.reply_to(m, "No activos"); return
        cid, saldo = row
        nuevo = saldo + 0.45
        c.execute("UPDATE creditos SET saldo=%s WHERE id=%s", (nuevo, cid))
        c.execute("INSERT INTO abonos (credito_id, codigo, fecha, monto, penalizacion, saldo_restante) VALUES (%s,%s,%s,%s,%s,%s)", (cid, codigo, fecha, 0, 0.45, nuevo))
        bot.reply_to(m, f"⚠️ #{cid} {codigo} NO PAGÓ\nFecha: {fecha}\n+0.45 | Saldo ${nuevo:.2f}")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

@bot.message_handler(commands=['saldo','clientes','lista'])
def saldo(m):
    try:
        if m.text.startswith('/clientes') or m.text.startswith('/lista'):
            c.execute("SELECT codigo, COUNT(*), SUM(saldo) FROM creditos WHERE estado='ACTIVO' GROUP BY codigo")
            rows = c.fetchall()
            txt = f"📊 CARTERA: ${sum(r[2] or 0 for r in rows):.2f}\n\n"
            for cod, cnt, sal in rows: txt += f"{cod}: {cnt} cred - ${sal:.2f}\n"
            bot.reply_to(m, txt or "Sin activos"); return
        _, codigo = m.text.split()
        c.execute("SELECT id, monto, total, saldo, fecha_inicio, estado FROM creditos WHERE codigo=%s ORDER BY id DESC", (codigo,))
        for cid, mo, to, sa, fi, es in c.fetchall():
            bot.reply_to(m, f"#{cid} ${mo}->{to} Saldo ${sa:.2f} Inicio {fi} {es}")
    except Exception as e:
        bot.reply_to(m, f"/saldo CODIGO o /clientes")

print("Bot Prodesa Postgres corriendo...")
bot.infinity_polling()
