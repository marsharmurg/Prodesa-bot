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
    txt = txt.strip().replace("/", " ").replace("-", " ")
    try:
        return datetime.strptime(txt, "%d %m %Y")
    except Exception:
        return datetime.now()


def format_fecha(dt):
    return dt.strftime("%d %m %Y")


def obtener_festivos_locales(year):
    return [
        f"01 01 {year}",  # Año Nuevo
        f"01 05 {year}",  # Día del Trabajo
        f"10 05 {year}",  # Día de la Madre
        f"17 06 {year}",  # Día del Padre
        f"05 08 {year}",  # Fiestas Agostinas
        f"06 08 {year}",  # Fiestas Agostinas
        f"15 09 {year}",  # Independencia
        f"02 11 {year}",  # Día de los Difuntos
        f"25 12 {year}",  # Navidad
    ]


def calcular_vencimiento(fecha_inicio, dias_plazo, festivos_extra=None):
    if festivos_extra is None:
        festivos_extra = []

    actual = fecha_inicio
    dias_contados = 0

    while dias_contados < dias_plazo:
        actual += timedelta(days=1)
        str_actual = format_fecha(actual)
        festivos_ano = obtener_festivos_locales(actual.year)

        if (
            actual.weekday() < 5
            and str_actual not in festivos_ano
            and str_actual not in festivos_extra
        ):
            dias_contados += 1

    return actual


def obtener_tarifa_penalizacion(monto):
    if 25 <= monto <= 199.00:
        return 0.45
    elif 200.00 <= monto <= 399.00:
        return 0.60
    elif monto >= 400.00:
        return 0.90
    return 0.0


def calcular_calificacion(fallas):
    if fallas == 0:
        return "AA"
    elif fallas == 1:
        return "AB"
    elif fallas == 2:
        return "AC"
    else:
        return "AD"


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS clientes (codigo TEXT PRIMARY KEY, nombre"
        " TEXT, foto_url TEXT)"
    )
    c.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS foto_url TEXT;")
    c.execute("""CREATE TABLE IF NOT EXISTS creditos 
    (id SERIAL PRIMARY KEY, codigo TEXT, num_credito TEXT, monto REAL, dias INTEGER, total REAL, cuota REAL, comision REAL, saldo REAL, fallas INTEGER DEFAULT 0, calificacion TEXT DEFAULT 'AA', fecha_inicio TEXT, fecha_fin TEXT, estado TEXT)""")
    c.execute(
        "ALTER TABLE creditos ADD COLUMN IF NOT EXISTS num_credito TEXT;"
    )
    c.execute(
        "ALTER TABLE creditos ADD COLUMN IF NOT EXISTS fallas INTEGER DEFAULT"
        " 0;"
    )
    c.execute(
        "ALTER TABLE creditos ADD COLUMN IF NOT EXISTS calificacion TEXT"
        " DEFAULT 'AA';"
    )
    c.execute("""CREATE TABLE IF NOT EXISTS abonos 
    (id SERIAL PRIMARY KEY, credito_id INTEGER, codigo TEXT, num_credito TEXT, fecha TEXT, monto REAL, penalizacion REAL, saldo_restante REAL)""")
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
        "🔹 *ESTADO DE CUENTA:* `/saldo CODIGO`\n"
        "🔹 *ASIGNAR FOTO:* Adjunta una foto y pon de comentario `/foto"
        " CODIGO`\n"
        "🔹 *HISTORIAL CREDITICIO:* `/historial CODIGO`\n"
        "🔹 *REPORTE DIARIO:* `/reporte` o `/reporte 29 10 2026`\n"
        "🔹 *PAGO/ABONO:* `/pago CODIGO MONTO [DIAS_RETRASO]`\n"
        "🔹 *CORREGIR FECHA:* `/fecha CODIGO 28 10 2026`\n"
        "🔹 *EDITAR:* `/editar CODIGO MONTO PLAZO CUOTA`\n"
        "🔹 *BORRAR:* `/eliminar CODIGO`"
    )
    bot.reply_to(m, texto, parse_mode="Markdown")


@bot.message_handler(commands=["historial"])
def historial_cliente(m):
    try:
        p = m.text.split()
        if len(p) < 2:
            bot.reply_to(m, "Usa: `/historial CODIGO`", parse_mode="Markdown")
            return

        codigo = p[1]
        conn = get_conn()
        c = conn.cursor()

        c.execute(
            "SELECT COALESCE(num_credito, codigo), monto, fecha_inicio,"
            " COALESCE(fecha_fin, 'Pendiente'), COALESCE(fallas, 0),"
            " COALESCE(calificacion, 'AA'), estado FROM creditos WHERE"
            " codigo=%s ORDER BY id ASC",
            (codigo,),
        )
        filas = c.fetchall()

        if not filas:
            bot.reply_to(
                m,
                f"❌ No existen registros de créditos para el cliente {codigo}.",
            )
            c.close()
            conn.close()
            return

        msg = f"📜 *HISTORIAL CREDITICIO GENERAL DE {codigo}*\n\n"
        for f in filas:
            num_cred, monto, f_ini, f_fin, fallas, calif, estado = f
            estado_icon = "🟢" if estado == "ACTIVO" else "✅"
            msg += (
                f"{estado_icon} *Crédito:* `{num_cred}`\n"
                f"• Monto: ${monto:.2f}\n"
                f"• Período: {f_ini} al {f_fin}\n"
                f"• Fallas: {fallas} | Calificación: *{calif}*\n"
                f"• Estado: {estado}\n"
                f"-----------------------------------\n"
            )

        bot.reply_to(m, msg, parse_mode="Markdown")
        c.close()
        conn.close()
    except Exception as e:
        bot.reply_to(
            m, f"❌ Error al consultar historial: {str(e)}", parse_mode="Markdown"
        )


@bot.message_handler(content_types=["photo"])
def recibir_foto_adjunta(m):
    try:
        caption = m.caption.strip() if m.caption else ""
        if caption.startswith("/foto"):
            p = caption.split()
            if len(p) > 1:
                codigo = p[1]
                file_id = m.photo[-1].file_id

                conn = get_conn()
                c = conn.cursor()
                c.execute(
                    "INSERT INTO clientes (codigo, foto_url) VALUES (%s, %s)"
                    " ON CONFLICT (codigo) DO UPDATE SET foto_url = EXCLUDED.foto_url",
                    (codigo, file_id),
                )
                conn.commit()

                bot.reply_to(
                    m,
                    f"🖼️ Foto guardada con éxito para el cliente *{codigo}*.",
                    parse_mode="Markdown",
                )
                c.close()
                conn.close()
            else:
                bot.reply_to(
                    m,
                    "⚠️ Indica el código del cliente. Ejemplo: `/foto"
                    " AEMR3930`",
                    parse_mode="Markdown",
                )
    except Exception as e:
        bot.reply_to(m, f"❌ Error al guardar la foto: {str(e)}")


@bot.message_handler(commands=["foto"])
def guardar_foto_url(m):
    try:
        p = m.text.split()
        codigo, url = p[1], p[2]

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO clientes (codigo, foto_url) VALUES (%s, %s) ON"
            " CONFLICT (codigo) DO UPDATE SET foto_url = EXCLUDED.foto_url",
            (codigo, url),
        )
        conn.commit()

        bot.reply_to(
            m,
            f"🖼️ Foto asignada con éxito al cliente *{codigo}*.",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa:\n1. Adjuntar foto con texto: `/foto CODIGO`\n2. O enlace:"
            " `/foto CODIGO URL`",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["saldo"])
def saldo(m):
    try:
        p = m.text.split()
        if len(p) < 2:
            bot.reply_to(m, "Usa: `/saldo CODIGO`", parse_mode="Markdown")
            return

        codigo = p[1]
        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT foto_url FROM clientes WHERE codigo=%s", (codigo,))
        res_foto = c.fetchone()
        foto_url = res_foto[0] if res_foto else None

        c.execute(
            "SELECT id, COALESCE(num_credito, codigo), monto, dias, cuota,"
            " total, saldo, COALESCE(fallas, 0), COALESCE(calificacion, 'AA'),"
            " fecha_inicio, COALESCE(fecha_fin, 'No calculada') FROM creditos"
            " WHERE codigo=%s AND estado='ACTIVO' ORDER BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ El cliente *{codigo}* no tiene crédito activo.")
            c.close()
            conn.close()
            return

        (
            cid,
            num_credito,
            monto,
            dias,
            cuota,
            total,
            saldo_actual,
            fallas,
            calif,
            fecha_ini,
            fecha_venc,
        ) = row

        c.execute(
            "SELECT fecha, COALESCE(monto, 0), COALESCE(penalizacion, 0),"
            " COALESCE(saldo_restante, 0) FROM abonos WHERE credito_id=%s ORDER"
            " BY id ASC",
            (cid,),
        )
        abonos = c.fetchall()

        msg = (
            f"📊 *ESTADO DE CUENTA: {codigo}*\n"
            f"🆔 *Crédito Activo:* `{num_credito}`\n\n"
            f"🗓️ *Inicio:* {fecha_ini} | *Vencimiento:* {fecha_venc}\n"
            f"💵 *Monto:* ${monto:.2f} | *Cuota:* ${cuota:.2f}\n"
            f"⭐ *Calificación:* *{calif}* ({fallas} fallas)\n"
            f"💰 *Total Crédito:* ${total:.2f}\n"
            f"🔴 *SALDO PENDIENTE: ${saldo_actual:.2f}*\n"
            f"-----------------------------------\n"
            f"📝 *HISTORIAL DE ABONOS:*\n"
        )

        if not abonos:
            msg += "_No hay abonos registrados en este crédito._\n"
        else:
            for a in abonos:
                f_pago, m_pago, pen_pago, s_pago = a
                pen_txt = f" (Mora: ${pen_pago:.2f})" if pen_pago > 0 else ""
                msg += f"• `{f_pago}`: ${m_pago:.2f}{pen_txt} ➔ Queda: ${s_pago:.2f}\n"

        if foto_url:
            try:
                bot.send_photo(
                    m.chat.id, foto_url, caption=msg, parse_mode="Markdown"
                )
            except Exception:
                bot.reply_to(m, msg, parse_mode="Markdown")
        else:
            bot.reply_to(m, msg, parse_mode="Markdown")

        c.close()
        conn.close()
    except Exception as e:
        bot.reply_to(
            m, f"❌ Error al consultar saldo: {str(e)}", parse_mode="Markdown"
        )


@bot.message_handler(commands=["nuevo"])
def nuevo(m):
    try:
        p = m.text.split()
        codigo, monto, dias, cuota = p[1], float(p[2]), int(p[3]), float(p[4])
        dt_inicio = (
            parse_fecha(" ".join(p[5:])) if len(p) > 4 else datetime.now()
        )
        fecha_inicio_str = format_fecha(dt_inicio)

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM creditos WHERE codigo=%s", (codigo,))
        conteo = c.fetchone()[0] + 1
        num_credito = f"{codigo}-{conteo}"

        c.execute("SELECT fecha FROM festivos")
        festivos_extra = [r[0] for r in c.fetchall()]

        dt_vencimiento = calcular_vencimiento(dt_inicio, dias, festivos_extra)
        fecha_vencimiento_str = format_fecha(dt_vencimiento)

        comision = monto * 0.04
        total = (cuota * dias) + comision

        c.execute(
            "INSERT INTO clientes (codigo) VALUES (%s) ON CONFLICT DO NOTHING",
            (codigo,),
        )
        c.execute(
            "INSERT INTO creditos (codigo, num_credito, monto, dias, total,"
            " cuota, comision, saldo, fallas, calificacion, fecha_inicio,"
            " fecha_fin, estado) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                codigo,
                num_credito,
                monto,
                dias,
                total,
                cuota,
                comision,
                total,
                0,
                "AA",
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
            f"🆔 *N° de Crédito:* `{num_credito}`\n"
            f"👤 *Cliente:* {codigo}\n"
            f"💵 *Monto:* ${monto:.2f}\n"
            f"📅 *Inicio:* {fecha_inicio_str}\n"
            f"🏁 *Vencimiento:* {fecha_vencimiento_str}\n"
            f"⏱️ *Plazo (L-V):* {dias} días hábiles\n"
            f"💲 *Cuota diaria:* ${cuota:.2f}\n"
            f"💰 *Total a pagar:* ${total:.2f}\n"
            f"⭐ *Calificación inicial:* AA\n"
            f"⚠️ *Penalización por mora:* ${tarifa_penalizacion:.2f}/día no pagado",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/nuevo CODIGO MONTO PLAZO CUOTA [DD MM YYYY]`",
            parse_mode="Markdown",
        )


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
            "SELECT id, COALESCE(num_credito, codigo), monto, saldo,"
            " COALESCE(fallas, 0) FROM creditos WHERE codigo=%s AND"
            " estado='ACTIVO' ORDER BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ {codigo} no tiene crédito activo.")
            c.close()
            conn.close()
            return

        cid, num_credito, monto_credito, saldo_actual, fallas_actuales = row
        tarifa = obtener_tarifa_penalizacion(monto_credito)
        penalizacion_total = tarifa * dias_retraso

        nuevas_fallas = fallas_actuales + dias_retraso
        nueva_calificacion = calcular_calificacion(nuevas_fallas)

        nuevo_saldo = (saldo_actual + penalizacion_total) - monto_abono
        fecha_pago_str = format_fecha(datetime.now())

        c.execute(
            "UPDATE creditos SET saldo=%s, fallas=%s, calificacion=%s WHERE"
            " id=%s",
            (nuevo_saldo, nuevas_fallas, nueva_calificacion, cid),
        )
        c.execute(
            "INSERT INTO abonos (credito_id, codigo, num_credito, fecha, monto,"
            " penalizacion, saldo_restante) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                cid,
                codigo,
                num_credito,
                fecha_pago_str,
                monto_abono,
                penalizacion_total,
                nuevo_saldo,
            ),
        )

        estado = "ACTIVO"
        if nuevo_saldo <= 0:
            estado = "CANCELADO"
            c.execute(
                "UPDATE creditos SET estado='CANCELADO', fecha_fin=%s WHERE"
                " id=%s",
                (fecha_pago_str, cid),
            )

        conn.commit()

        msg = (
            f"💰 *PAGO REGISTRADO*\n\n"
            f"🆔 *Crédito:* `{num_credito}`\n"
            f"👤 *Cliente:* {codigo}\n"
            f"💵 *Abono:* ${monto_abono:.2f}\n"
        )
        if dias_retraso > 0:
            msg += (
                f"⚠️ *Días no abonados agregados:* {dias_retraso}\n💸"
                f" *Penalización:* ${penalizacion_total:.2f}\n"
            )

        msg += (
            f"⭐ *Calificación actual:* *{nueva_calificacion}* ({nuevas_fallas}"
            f" fallas acumuladas)\n"
        )
        msg += f"🔴 *Saldo restante: ${nuevo_saldo:.2f}*"

        if estado == "CANCELADO":
            msg += f"\n\n🎉 *¡CRÉDITO {num_credito} FINALIZADO Y CANCELADO!*"

        bot.reply_to(m, msg, parse_mode="Markdown")
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m,
            "Usa: `/pago CODIGO MONTO [DIAS_SIN_PAGAR]`",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["reporte"])
def reporte_diario(m):
    try:
        p = m.text.split()
        if len(p) > 1:
            fecha_consulta = format_fecha(parse_fecha(" ".join(p[1:])))
        else:
           # Resta 6 horas para ajustar la zona horaria a El Salvador
            fecha_consulta = format_fecha(datetime.now() - timedelta(hours=6))

        conn = get_conn()
        c = conn.cursor()

        # Consulta ultra-segura
        c.execute(
            """
            SELECT 
                codigo, 
                monto, 
                COALESCE(penalizacion, 0), 
                COALESCE(saldo_restante, 0),
                COALESCE(num_credito, codigo)
            FROM abonos 
            WHERE fecha LIKE %s
            ORDER BY id ASC
        """,
            (f"{fecha_consulta}%",),
        )

        filas = c.fetchall()

        if not filas:
            bot.reply_to(
                m,
                f"📅 *REPORTE DE COBROS ({fecha_consulta})*\n\n_No se"
                " registraron cobros en esta fecha._",
                parse_mode="Markdown",
            )
            c.close()
            conn.close()
            return

        total_cobrado = 0.0
        total_pen = 0.0

        msg = f"📅 *REPORTE DIARIO DE CARTERA ({fecha_consulta})*\n\n"
        for f in filas:
            cod, monto, pen, s_rest, num_cred = f
            monto_val = float(monto) if monto else 0.0
            pen_val = float(pen) if pen else 0.0
            s_rest_val = float(s_rest) if s_rest else 0.0

            total_cobrado += monto_val
            total_pen += pen_val

            mora_txt = f" (Mora: ${pen_val:.2f})" if pen_val > 0 else ""
            msg += (
                f"👤 `{num_cred}` ({cod}): ${monto_val:.2f}{mora_txt} | Queda:"
                f" ${s_rest_val:.2f}\n"
            )

        msg += f"\n-----------------------------------\n"
        msg += f"💵 *TOTAL COBRADO:* ${total_cobrado:.2f}\n"
        if total_pen > 0:
            msg += f"⚠️ *TOTAL PENALIZACIONES:* ${total_pen:.2f}\n"

        bot.reply_to(m, msg, parse_mode="Markdown")
        c.close()
        conn.close()
    except Exception as e:
        bot.reply_to(
            m,
            f"❌ Error al consultar el reporte: {str(e)}",
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
            "SELECT id, COALESCE(num_credito, codigo), dias FROM creditos WHERE"
            " codigo=%s AND estado='ACTIVO' ORDER BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, f"❌ Código {codigo} no existe o no está activo.")
            c.close()
            conn.close()
            return

        cid, num_credito, dias = row
        c.execute("SELECT fecha FROM festivos")
        festivos_extra = [r[0] for r in c.fetchall()]

        dt_venc = calcular_vencimiento(dt_nueva, dias, festivos_extra)
        venc_str = format_fecha(dt_venc)

        c.execute(
            "UPDATE creditos SET fecha_inicio=%s, fecha_fin=%s WHERE id=%s",
            (nueva_fecha_str, venc_str, cid),
        )
        conn.commit()
        bot.reply_to(
            m,
            f"📅 *FECHA CORREGIDA*\n\n🆔 *Crédito:* `{num_credito}`\n🗓️ *Nueva"
            f" Fecha Inicio:* {nueva_fecha_str}\n🏁 *Nuevo Vencimiento:*"
            f" {venc_str}",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m, "Usa: `/fecha CODIGO DD MM YYYY`", parse_mode="Markdown"
        )


@bot.message_handler(commands=["editar"])
def editar(m):
    try:
        p = m.text.split()
        codigo, monto, dias, cuota = p[1], float(p[2]), int(p[3]), float(p[4])

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, COALESCE(num_credito, codigo), fecha_inicio FROM"
            " creditos WHERE codigo=%s AND estado='ACTIVO' ORDER BY id DESC"
            " LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, "Código no existe")
            c.close()
            conn.close()
            return

        cid, num_credito, fecha_ini_str = row
        dt_ini = parse_fecha(fecha_ini_str)

        c.execute("SELECT fecha FROM festivos")
        festivos_extra = [r[0] for r in c.fetchall()]

        dt_venc = calcular_vencimiento(dt_ini, dias, festivos_extra)
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
            f"✏️ *CRÉDITO EDITADO*\n\n🆔 *Crédito:* `{num_credito}`\n💵 *Monto:*"
            f" ${monto:.2f}\n⏱️ *Plazo (L-V):* {dias} días\n💲 *Cuota:*"
            f" ${cuota:.2f}\n💰 *Nuevo Total:* ${total:.2f}\n🏁 *Vencimiento"
            f" ajustado:* {venc_str}",
            parse_mode="Markdown",
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(
            m, "Usa: `/editar CODIGO MONTO PLAZO CUOTA`", parse_mode="Markdown"
        )


@bot.message_handler(commands=["eliminar"])
def eliminar(m):
    try:
        p = m.text.split()
        codigo = p[1]

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, COALESCE(num_credito, codigo) FROM creditos WHERE"
            " codigo=%s AND estado='ACTIVO' ORDER BY id DESC LIMIT 1",
            (codigo,),
        )
        row = c.fetchone()

        if not row:
            bot.reply_to(m, "Código no existe")
            c.close()
            conn.close()
            return

        cid, num_credito = row
        c.execute("DELETE FROM abonos WHERE credito_id=%s", (cid,))
        c.execute("DELETE FROM creditos WHERE id=%s", (cid,))
        conn.commit()
        bot.reply_to(
            m, f"🗑️ Crédito `{num_credito}` eliminado correctamente."
        )
        c.close()
        conn.close()
    except Exception:
        bot.reply_to(m, "Usa: `/eliminar CODIGO`", parse_mode="Markdown")


print("Bot corriendo...")
bot.infinity_polling()
