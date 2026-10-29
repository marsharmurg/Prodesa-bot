from datetime import datetime
import os
import threading
from flask import Flask
import psycopg2
import telebot

# --- SERVIDOR WEB DUMMY PARA RENDER ---
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot activo y saludable", 200


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_web_server, daemon=True).start()

# --- CONFIGURACIÓN DEL BOT Y BASE DE DATOS ---
TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

bot = telebot.TeleBot(TOKEN)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def parse_fecha(txt):
    try:
        d = datetime.strptime(txt, "%d/%m/%Y")
        return d.strftime("%d/%m/%Y")
    except Exception:
        return txt


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS clientes (codigo TEXT PRIMARY KEY, nombre"
        " TEXT)"
    )
    c.execute("""CREATE TABLE IF NOT EXISTS creditos 
    (id SERIAL PRIMARY KEY, codigo TEXT, monto REAL, dias INTEGER, total REAL, cuota REAL, comision REAL, saldo REAL, fecha_inicio TEXT, fecha_fin TEXT, estado TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS abonos 
    (id SERIAL PRIMARY KEY, credito_id INTEGER, codigo TEXT, fecha TEXT, monto REAL, penalizacion REAL, saldo_restante REAL)""")
    conn.commit()
    c.close()
    conn.close()


init_db()


# --- COMANDOS DEL BOT ---


@bot.message_handler(commands=["start", "help"])
def send_welcome(m):
    texto = (
        "🤖 *PRODESA BOT - COMANDOS*\n\n"
        "🔹 *CREAR:* `/nuevo CODIGO MONTO PLAZO CUOTA`[cite: 4]\n"
        "🔹 *VER:* `/saldo CODIGO`[cite: 4]\n"
        "🔹 *EDITAR:* `/editar CODIGO MONTO PLAZO CUOTA`[cite: 4]\n"
        "🔹 *CORREGIR FECHA:* `/fecha CODIGO FECHA`\n"
        "🔹 *BORRAR:* `/eliminar CODIGO`[cite: 4]\n"
        "🔹 *PAGO:* `/pago CODIGO MONTO`[cite: 4]"
    )
    bot.reply_to(m, texto, parse_mode="Markdown")


@bot.message_handler(commands=["nuevo"])
def nuevo(m):
    try:
        p = m.text.split()
        _, codigo, monto, dias, cuota = p
        monto, dias, cuota = float(monto), int(dias), float(cuota)

        comision = monto * 0.04
        total = (cuota * dias) + comision
        fecha_inicio = datetime.now().strftime("%d/%m/%Y")

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO clientes (codigo) VALUES (%s) ON CONFLICT (codigo) DO"
            " NOTHING",
            (codigo,),
        )
        c.execute(
            "INSERT INTO creditos (codigo, monto, dias, total, cuota, comision,"
            " saldo, fecha_inicio, estado) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                codigo,
                monto,
                dias,
                total,
                cuota,
                comision,
                total,
                fecha_inicio,
                "ACTIVO",
            ),
        )
        conn.commit()
        bot.reply_to(
            m,
            f"✅ CRÉDITO CREADO\nCliente: {codigo}\nMonto: ${monto}\nPlazo:"
            f" {dias} días\nCuota: ${cuota}\nTotal a pagar: ${total:.2f}",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/nuevo CODIGO MONTO PLAZO CUOTA`\nEjemplo: `/nuevo C001 350"
            " 30 13`",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["saldo"])
def saldo(m):
    try:
        p = m.text.split()
        codigo = p[1]
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT monto, dias, cuota, total, saldo, fecha_inicio FROM"
            " creditos WHERE codigo=%s AND estado='ACTIVO' ORDER BY id DESC"
            " LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ El cliente {codigo} no tiene créditos activos.")
            c.close()
            conn.close()
            return

        monto, dias, cuota, total, saldo_actual, fecha = row
        bot.reply_to(
            m,
            f"📊 *ESTADO DE CUENTA: {codigo}*\n\n"
            f"• Fecha inicio: {fecha}\n"
            f"• Monto prestado: ${monto:.2f}\n"
            f"• Plazo: {dias} días | Cuota: ${cuota:.2f}\n"
            f"• Total crédito: ${total:.2f}\n"
            f"• *Saldo pendiente: ${saldo_actual:.2f}*",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(m, "Usa: `/saldo CODIGO`", parse_mode="Markdown")


@bot.message_handler(commands=["editar"])
def editar(m):
    try:
        p = m.text.split()
        _, codigo, monto, dias, cuota = p
        monto, dias, cuota = float(monto), int(dias), float(cuota)

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id FROM creditos WHERE codigo=%s AND estado='ACTIVO' ORDER"
            " BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, "Código no existe")[cite: 4]
            c.close()
            conn.close()
            return

        cid = row[0]
        comision = monto * 0.04
        total = (cuota * dias) + comision

        c.execute(
            "UPDATE creditos SET monto=%s, dias=%s, cuota=%s, comision=%s,"
            " total=%s, saldo=%s WHERE id=%s",
            (monto, dias, cuota, comision, total, total, cid),
        )
        conn.commit()
        bot.reply_to(
            m,
            f"✏️ CRÉDITO ACTUALIZADO\nCliente: {codigo}\nNuevo Monto:"
            f" ${monto}\nPlazo: {dias} días\nCuota: ${cuota}\nNuevo Total:"
            f" ${total:.2f}",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/editar CODIGO MONTO PLAZO CUOTA`\nEjemplo: `/editar C001"
            " 350 30 13`",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["fecha"])
def editar_fecha(m):
    try:
        p = m.text.split()
        codigo, nueva_fecha = p[1], parse_fecha(p[2])

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id FROM creditos WHERE codigo=%s AND estado='ACTIVO' ORDER"
            " BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ Código {codigo} no existe o no está activo.")
            c.close()
            conn.close()
            return

        cid = row[0]
        c.execute(
            "UPDATE creditos SET fecha_inicio=%s WHERE id=%s",
            (nueva_fecha, cid),
        )
        conn.commit()
        bot.reply_to(
            m,
            f"📅 FECHA CORREGIDA\nCliente: {codigo}\nNueva Fecha de inicio:"
            f" {nueva_fecha}",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/fecha CODIGO DD/MM/YYYY`\nEjemplo: `/fecha C001"
            " 25/10/2026`",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["eliminar"])
def eliminar(m):
    try:
        p = m.text.split()
        codigo = p[1]

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id FROM creditos WHERE codigo=%s AND estado='ACTIVO' ORDER"
            " BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, "Código no existe")[cite: 4]
            c.close()
            conn.close()
            return

        cid = row[0]
        c.execute("DELETE FROM abonos WHERE credito_id=%s", (cid,))
        c.execute("DELETE FROM creditos WHERE id=%s", (cid,))
        conn.commit()
        bot.reply_to(
            m, f"🗑️ Crédito del cliente {codigo} ha sido eliminado con éxito."
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(m, "Usa: `/eliminar CODIGO`", parse_mode="Markdown")


@bot.message_handler(commands=["pago", "abono"])
def pago(m):
    try:
        p = m.text.split()
        codigo, monto_abono = p[1], float(p[2])
        fecha = (
            parse_fecha(p[3]) + " 12:00"
            if len(p) > 3
            else datetime.now().strftime("%d/%m/%Y %H:%M")
        )

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, saldo FROM creditos WHERE codigo=%s AND estado='ACTIVO'"
            " ORDER BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ {codigo} no tiene crédito activo.")
            c.close()
            conn.close()
            return

        cid, saldo_actual = row
        nuevo_saldo = saldo_actual - monto_abono

        c.execute(
            "UPDATE creditos SET saldo=%s WHERE id=%s", (nuevo_saldo, cid)
        )
        c.execute(
            "INSERT INTO abonos (credito_id, codigo, fecha, monto,"
            " penalizacion, saldo_restante) VALUES (%s,%s,%s,%s,%s,%s)",
            (cid, codigo, fecha, monto_abono, 0, nuevo_saldo),
        )

        if nuevo_saldo <= 0:
            c.execute(
                "UPDATE creditos SET estado='CANCELADO', fecha_fin=%s WHERE"
                " id=%s",
                (fecha, cid),
            )

        conn.commit()
        bot.reply_to(
            m,
            f"💰 PAGO REGISTRADO\nCliente: {codigo}\nAbonó: ${monto_abono:.2f}\nSaldo"
            f" restante: ${nuevo_saldo:.2f}",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/pago CODIGO MONTO [FECHA]`\nEjemplo: `/pago C001 20`",
            parse_mode="Markdown",
        )


print("Bot corriendo...")
bot.infinity_polling()
