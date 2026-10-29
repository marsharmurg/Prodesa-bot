import os
import threading
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- FLASK PARA RENDER FREE (NO BORRAR) ---
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): 
    return "Bot Prodesa Live - OK"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)
# ------------------------------------------

# --- TUS FUNCIONES ---
def init_db():
    # si tenias base de datos pon tu codigo aqui
    pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy Prodesa Bot y ya estoy Live en Render 🚀")

def main():
    # 1. Iniciar Flask en segundo plano
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Fix Python 3.14
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except:
        pass

    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        print("ERROR: No hay BOT_TOKEN en Environment")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    # --- HANDLERS ---
    app.add_handler(CommandHandler("start", start))
    # AQUI agrega tus otros handlers que tenias antes

    print("Bot Prodesa corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
