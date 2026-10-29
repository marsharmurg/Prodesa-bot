from datetime import datetime, timedelta
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
    """Parsea formatos tipo 28 10 2026 o 28/10/2026 a objeto datetime."""
    txt = txt.strip().replace("/", " ").replace("-", " ")
    try:
        return datetime.strptime(txt, "%d %m %Y")
    except Exception:
        return datetime.now()


def format_fecha(dt):
    """Devuelve la fecha en formato DD MM YYYY."""
    return dt.strftime("%d %m %Y")


def calcular_vencimiento(fecha_inicio, dias_plazo, festivos=None):
    """Calcula la fecha de vencimiento contando solo de Lunes a Viernes y saltando festivos."""
    if festivos is None:
        festivos = []
    actual = fecha_inicio
    dias_contados = 0
    while dias_contados < dias_plazo:
        actual += timedelta(days=1)
        # 0 = Lunes, 4 = Viernes, 5 = Sábado, 6 = Domingo
        str_actual = format_fecha(actual)
        if actual.weekday() < 5 and str_actual not in festivos:
            dias_contados += 1
    return actual


def obtener_tarifa_penalizacion(monto):
    """Determina la tarifa diaria de penalización según el monto prestado."""
    if 25 <= monto <= 199.00:
        return 0.45
    elif 200.00 <= monto <= 399.00:
        return 0.60
    elif monto >= 400.00:
        return 0.90
    return 0.0


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
    c.execute(
        "CREATE TABLE IF NOT EXISTS festivos (fecha TEXT PRIMARY KEY,"
        " descripcion TEXT)"
    )
    conn.commit()
    c.close()
    conn.close()


init_db()


# --- COMANDOS DEL BOT ---


@bot.message_handler(commands=["start", "help"])
def send_welcome(m):
    texto = (
        "🤖 *PRODESA BOT - SISTEMA DE CRÉDITOS*\n\n"
        "🔹 *CREAR:* `/nuevo CODIGO MONTO PLAZO CUOTA [FECHA_INICIO]`\n"
        "🔹 *VER SALDO:* `/saldo CODIGO`\n"
        "🔹 *EDITAR:* `/editar CODIGO MONTO PLAZO CUOTA`\n"
        "🔹 *CORREGIR FECHA:* `/fecha CODIGO 28 10 2026`\n"
        "🔹 *PAGO/ABONO:* `/pago CODIGO MONTO [DIAS_RETRASO]`\n"
        "🔹 *REGISTRAR FESTIVO:* `/festivo 25 12 2026 Navidad`\n"
        "🔹 *BORRAR:* `/eliminar CODIGO`\n\n"
        "📌 *Notas:* Cobros de L-V. Formato de fecha: `DD MM YYYY`."
    )
    bot.reply_to(m, texto, parse_mode="Markdown")


@bot.message_handler(commands=["festivo"])
def agregar_festivo(m):
    try:
        p = m.text.split(maxsplit=2)
        fecha_str = format_fecha(parse_fecha(p[1]))
        desc = p[2] if len(p) > 2 else "Día Festivo"

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO festivos (fecha, descripcion) VALUES (%s, %s) ON"
            " CONFLICT DO NOTHING",
            (fecha_str, desc),
        )
        conn.commit()
        bot.reply_to(
            m, f"📅 Festivo registrado: *{fecha_str}* ({desc})", parse_mode="Markdown"
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(m, "Usa: `/festivo DD MM YYYY Descripcion`", parse_mode="Markdown")


@bot.message_handler(commands=["nuevo"])
def nuevo(m):
    try:
        p = m.text.split()
        codigo, monto, dias, cuota = p[1], float(p[2]), int(p[3]), float(p[4])
        dt_inicio = (
            parse_fecha(" ".join(p[5:])) if len(p) > 4 else datetime.now()
        )
        fecha_inicio_str = format_fecha(dt_inicio)

        # Cargar festivos
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT fecha FROM festivos")
        festivos = [r[0] for r in c.fetchall()]

        dt_vencimiento = calcular_vencimiento(dt_inicio, dias, festivos)
        fecha_vencimiento_str = format_fecha(dt_vencimiento)

        comision = monto * 0.04
        total = (cuota * dias) + comision

        c.execute(
            "INSERT INTO clientes (codigo) VALUES (%s) ON CONFLICT DO NOTHING",
            (codigo,),
        )
        c.execute(
            "INSERT INTO creditos (codigo, monto, dias, total, cuota, comision,"
            " saldo, fecha_inicio, fecha_fin, estado) VALUES"
            " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                codigo,
                monto,
                dias,
                total,
                cuota,
                comision,
                total,
                fecha_inicio_str,
                fecha_vencimiento_str,
                "ACTIVO",
            ),
        )
        conn.commit()

        tarifa_penalizacion = obtener_tarifa_penalizacion(monto)

        bot.reply_to(
            m,
            f"✅ *CRÉDITO CREADO*\n\n"
            f"👤 *Cliente:* {codigo}\n"
            f"💵 *Monto:* ${monto:.2f}\n"
            f"📅 *Inicio:* {fecha_inicio_str}\n"
            f"🏁 *Vencimiento:* {fecha_vencimiento_str}\n"
            f"⏱️ *Plazo (L-V):* {dias} días hábiles\n"
            f"💲 *Cuota diaria:* ${cuota:.2f}\n"
            f"💰 *Total a pagar:* ${total:.2f}\n"
            f"⚠️ *Penalización por mora:* ${tarifa_penalizacion:.2f}/día no pagado",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception as e:
        bot.reply_to(
            m,
            "Usa: `/nuevo CODIGO MONTO PLAZO CUOTA [DD MM YYYY]`\nEjemplo:"
            " `/nuevo C001 150 20 9.5 28 10 2026`",
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
            "SELECT monto, dias, cuota, total, saldo, fecha_inicio, fecha_fin"
            " FROM creditos WHERE codigo=%s AND estado='ACTIVO' ORDER BY id DESC"
            " LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ El cliente *{codigo}* no tiene crédito activo.")
            c.close()
            conn.close()
            return

        monto, dias, cuota, total, saldo_actual, fecha_ini, fecha_venc = row
        tarifa_pen = obtener_tarifa_penalizacion(monto)

        bot.reply_to(
            m,
            f"📊 *ESTADO DE CUENTA: {codigo}*\n\n"
            f"🗓️ *Fecha Inicio:* {fecha_ini}\n"
            f"🏁 *Vencimiento:* {fecha_venc}\n"
            f"💵 *Monto Prestado:* ${monto:.2f}\n"
            f"⏱️ *Plazo:* {dias} días hábiles (L-V)\n"
            f"💲 *Cuota:* ${cuota:.2f}\n"
            f"💰 *Total Crédito:* ${total:.2f}\n"
            f"⚠️ *Tarifa Mora:* ${tarifa_pen:.2f}/día\n"
            f"🔴 *SALDO PENDIENTE: ${saldo_actual:.2f}*",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(m, "Usa: `/saldo CODIGO`", parse_mode="Markdown")


@bot.message_handler(commands=["pago", "abono"])
def pago(m):
    try:
        p = m.text.split()
        codigo = p[1]
        monto_abono = float(p[2])
        dias_retraso = int(p[3]) if len(p) > 3 else 0

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, monto, saldo FROM creditos WHERE codigo=%s AND"
            " estado='ACTIVO' ORDER BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ {codigo} no tiene crédito activo.")
            c.close()
            conn.close()
            return

        cid, monto_credito, saldo_actual = row
        tarifa = obtener_tarifa_penalizacion(monto_credito)
        penalizacion_total = tarifa * dias_retraso

        # El nuevo saldo suma la penalización y resta el abono
        nuevo_saldo = (saldo_actual + penalizacion_total) - monto_abono
        fecha_pago_str = format_fecha(datetime.now())

        c.execute(
            "UPDATE creditos SET saldo=%s WHERE id=%s", (nuevo_saldo, cid)
        )
        c.execute(
            "INSERT INTO abonos (credito_id, codigo, fecha, monto,"
            " penalizacion, saldo_restante) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                cid,
                codigo,
                fecha_pago_str,
                monto_abono,
                penalizacion_total,
                nuevo_saldo,
            ),
        )

        if nuevo_saldo <= 0:
            c.execute(
                "UPDATE creditos SET estado='CANCELADO', fecha_fin=%s WHERE"
                " id=%s",
                (fecha_pago_str, cid),
            )

        conn.commit()

        msg = (
            f"💰 *PAGO REGISTRADO*\n\n"
            f"👤 *Cliente:* {codigo}\n"
            f"💵 *Abono:* ${monto_abono:.2f}\n"
        )
        if dias_retraso > 0:
            msg += (
                f"⚠️ *Días no abonados:* {dias_retraso}\n"
                f"💸 *Penalización agregada:* ${penalizacion_total:.2f}\n"
            )

        msg += f"🔴 *Saldo restante: ${nuevo_saldo:.2f}*"

        bot.reply_to(m, msg, parse_mode="Markdown")
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/pago CODIGO MONTO [DIAS_SIN_PAGAR]`\nEjemplo: `/pago C001"
            " 10 2`",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["fecha"])
def editar_fecha(m):
    try:
        p = m.text.split()
        codigo = p[1]
        dt_nueva = parse_fecha(" ".join(p[2:]))
        nueva_fecha_str = format_fecha(dt_nueva)

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, dias FROM creditos WHERE codigo=%s AND estado='ACTIVO'"
            " ORDER BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ Código {codigo} no existe o no está activo.")
            c.close()
            conn.close()
            return

        cid, dias = row
        c.execute("SELECT fecha FROM festivos")
        festivos = [r[0] for r in c.fetchall()]

        dt_venc = calcular_vencimiento(dt_nueva, dias, festivos)
        venc_str = format_fecha(dt_venc)

        c.execute(
            "UPDATE creditos SET fecha_inicio=%s, fecha_fin=%s WHERE id=%s",
            (nueva_fecha_str, venc_str, cid),
        )
        conn.commit()
        bot.reply_to(
            m,
            f"📅 *FECHA CORREGIDA*\n\n"
            f"👤 *Cliente:* {codigo}\n"
            f"🗓️ *Nueva Fecha Inicio:* {nueva_fecha_str}\n"
            f"🏁 *Nuevo Vencimiento:* {venc_str}",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/fecha CODIGO DD MM YYYY`\nEjemplo: `/fecha C001 28 10 2026`",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["editar"])
def editar(m):
    try:
        p = m.text.split()
        codigo, monto, dias, cuota = p[1], float(p[2]), int(p[3]), float(p[4])

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, fecha_inicio FROM creditos WHERE codigo=%s AND"
            " estado='ACTIVO' ORDER BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, "Código no existe")
            c.close()
            conn.close()
            return

        cid, fecha_ini_str = row
        dt_ini = parse_fecha(fecha_ini_str)

        c.execute("SELECT fecha FROM festivos")
        festivos = [r[0] for r in c.fetchall()]

        dt_venc = calcular_vencimiento(dt_ini, dias, festivos)
        venc_str = format_fecha(dt_venc)

        comision = monto * 0.04
        total = (cuota * dias) + comision

        c.execute(
            "UPDATE creditos SET monto=%s, dias=%s, cuota=%s, comision=%s,"
            " total=%s, saldo=%s, fecha_fin=%s WHERE id=%s",
            (monto, dias, cuota, comision, total, total, venc_str, cid),
        )
        conn.commit()

        bot.reply_to(
            m,
            f"✏️ *CRÉDITO EDITADO*\n\n"
            f"👤 *Cliente:* {codigo}\n"
            f"💵 *Monto:* ${monto:.2f}\n"
            f"⏱️ *Plazo (L-V):* {dias} días\n"
            f"💲 *Cuota:* ${cuota:.2f}\n"
            f"💰 *Nuevo Total:* ${total:.2f}\n"
            f"🏁 *Vencimiento ajustado:* {venc_str}",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/editar CODIGO MONTO PLAZO CUOTA`\nEjemplo: `/editar C001"
            " 150 20 9.5`",
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
            bot.reply_to(m, "Código no existe")
            c.close()
            conn.close()
            return

        cid = row[0]
        c.execute("DELETE FROM abonos WHERE credito_id=%s", (cid,))
        c.execute("DELETE FROM creditos WHERE id=%s", (cid,))
        conn.commit()
        bot.reply_to(
            m, f"🗑️ Crédito del cliente {codigo} eliminado correctamente."
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(m, "Usa: `/eliminar CODIGO`", parse_mode="Markdown")


print("Bot corriendo...")
bot.infinity_polling()
