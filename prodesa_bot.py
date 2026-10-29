import os
import threading
import asyncio
from flask import Flask

# --- FLASK PARA RENDER FREE ---
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "Bot Prodesa Live - OK"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)
# -------------------------------

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
# ... AQUI DEJA TODO TU CODIGO DE HANDLERS IGUAL ...

def main():
    init_db()
    # Iniciar web
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Fix para Python 3.14
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except:
        pass

    TOKEN = os.environ.get("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    # ... agrega tus handlers aqui ...
    # app.add_handler(...)
    
    print("Bot Prodesa corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
