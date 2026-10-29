import os
import telebot
import psycopg2
from datetime import datetime

TOKEN = os.environ.get('BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')

bot = telebot.TeleBot(TOKEN)

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def parse_fecha(txt):
    try:
        # intenta dd/mm/yyyy
        d = datetime.strptime(txt, "%d/%m/%Y")
        return d.strftime("%d/%m/%Y")
    except:
        return txt

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clientes (codigo TEXT PRIMARY KEY, nombre TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS creditos 
    (id SERIAL PRIMARY KEY, codigo TEXT, monto REAL, dias INTEGER, total REAL, cuota REAL, comision REAL, saldo REAL, fecha_inicio TEXT, fecha_fin TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS abonos 
    (id SERIAL PRIMARY KEY, credito_id INTEGER, codigo TEXT, fecha TEXT, monto REAL, penalizacion REAL, saldo_restante REAL)''')
    conn.commit()
    c.close()
    conn.close()

init_db()

@bot.message_handler(commands=['nuevo'])
def nuevo(m):
    try:
        p = m.text.split()
        _, codigo, monto, dias, total, cuota = p
        monto, dias, total, cuota = float(monto), int(dias), float(total), float(cuota)
        conn = get_conn(); c = conn.cursor()
        c.execute("INSERT INTO clientes (codigo) VALUES (%s) ON CONFLICT (codigo) DO NOTHING", (codigo,))
        comision = monto * 0.04
        fecha_inicio = datetime.now().strftime("%d/%m/%Y")
        c.execute("INSERT INTO creditos (codigo, monto, dias, total, cuota, comision, saldo, fecha_inicio, estado) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (codigo, monto, dias, total, cuota, comision, total, fecha_inicio, 'ACTIVO'))
        conn.commit()
        bot.reply_to(m, f"✅ CREDITO CREADO\nCliente: {codigo}\nPrestado: ${monto} | Total: ${total}")
        c.close(); conn.close()
    except Exception as e:
        bot.reply_to(m, f"Usa: /nuevo CODIGO MONTO DIAS TOTAL CUOTA\nError: {e}")

@bot.message_handler(commands=['abono'])
def abono(m):
    try:
        conn = get_conn(); c = conn.cursor()
        p = m.text.split()
        codigo, monto_abono = p[1], float(p[2])
        fecha = parse_fecha(p[3]) + " 12:00" if len(p) > 3 else datetime.now().strftime("%d/%m/%Y %H:%M")
        c.execute("SELECT id, saldo FROM creditos WHERE codigo=%s AND estado='ACTIVO' ORDER BY id DESC LIMIT 1", (codigo,))
        row = c.fetchone()
        if not row:
            bot.reply_to(m, f"❌ {codigo} sin activos")
            c.close(); conn.close()
            return
        cid, saldo = row
        nuevo = saldo - monto_abono
        c.execute("UPDATE creditos SET saldo=%s WHERE id=%s", (nuevo, cid))
        c.execute("INSERT INTO abonos (credito_id, codigo, fecha, monto, penalizacion, saldo_restante) VALUES (%s,%s,%s,%s,%s,%s)", (cid, codigo, fecha, monto_abono, 0, nuevo))
        if nuevo <= 0:
            c.execute("UPDATE creditos SET estado='CANCELADO', fecha_fin=%s WHERE id=%s", (fecha, cid))
        conn.commit()
        bot.reply_to(m, f"💰 {codigo} abonó ${monto_abono}\nSaldo: ${nuevo:.2f}")
        c.close(); conn.close()
    except Exception as e:
        bot.reply_to(m, f"Error abono: {e}")

print("Bot corriendo...")
bot.infinity_polling()
