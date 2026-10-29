from datetime import datetime
import os
import threading
from flask import Flask
import psycopg2
import telebot

# --- SERVIDOR WEB DUMMY PARA RENDER (GRATIS) ---
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot en ejecución y saludable", 200


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
        "🔹 *CORREGIR FECHA:* `/fecha CODIGO FECHA` (Ej: `/fecha C001"
        " 25/10/2026`)\n"
        "🔹 *BORRAR:* `/eliminar CODIGO`[cite: 4]\n"
        "🔹 *PAGO:* `/pago CODIGO MONTO`[cite: 4]\n\n"
        "💡 *Fórmula:* `(Cuota * Plazo) + (Monto * 0.04)`[cite: 4]"
    )
    bot.reply_to(m, texto, parse_mode="Markdown")


@bot.message_handler(commands=["nuevo"])
def nuevo(m):
    try:
        p = m.text.split()
        _, codigo, monto, dias, cuota = p
        monto, dias, cuota = float(monto), int(dias), float(cuota)

        # Cálculo según fórmula: (Cuota *
