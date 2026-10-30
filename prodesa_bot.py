@bot.message_handler(commands=["reporte"])
def reporte_diario(m):
    try:
        p = m.text.split()
        # Si no pones fecha, toma la de hoy (29 10 2026)
        fecha_consulta = (
            format_fecha(parse_fecha(" ".join(p[1:])))
            if len(p) > 1
            else format_fecha(datetime.now())
        )

        conn = get_conn()
        c = conn.cursor()

        # COALESCE evita errores si hay valores nulos o campos vacíos en abonos antiguos
        c.execute(
            "SELECT COALESCE(num_credito, codigo), codigo, monto,"
            " COALESCE(penalizacion, 0), COALESCE(saldo_restante, 0) FROM"
            " abonos WHERE fecha LIKE %s ORDER BY id ASC",
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

        total_cobrado = sum(f[2] for f in filas)
        total_pen = sum(f[3] for f in filas)

        msg = f"📅 *REPORTE DIARIO DE CARTERA ({fecha_consulta})*\n\n"
        for f in filas:
            num_cred, cod, monto, pen, s_rest = f
            mora_txt = f" (Mora: ${pen:.2f})" if pen > 0 else ""
            msg += (
                f"👤 `{num_cred}` ({cod}): ${monto:.2f}{mora_txt} | Queda:"
                f" ${s_rest:.2f}\n"
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
            f"❌ Error al generar reporte: {str(e)}\nUsa: `/reporte 29 10"
            " 2026`",
            parse_mode="Markdown",
        )
