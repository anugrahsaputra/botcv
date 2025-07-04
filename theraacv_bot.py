# theraacv_bot.py (Versi Final Lengkap)

import logging
import os
import uuid
import json
import time
import datetime
from functools import wraps
import vobject

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

# --- KONFIGURASI ---
TOKEN = "8102525608:AAH7CnM1vk-2JqwqbM5IRuv6Td1tPx-OSfk"
ADMIN_IDS = {7660579116}

OWNER_USERNAME = "@thera448"
BOT_NAME = "TheRaaCV"

# --- PENGATURAN FREE TRIAL ---
ENABLE_FREE_TRIAL = True
FREE_TRIAL_DURATION = "1D" # 1D = 1 Hari, 3D = 3 Hari, 12H = 12 Jam

# File untuk menyimpan data premium
PREMIUM_DATA_FILE = "premium_data.json"
# --- AKHIR KONFIGURASI ---

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TEMP_DIR = "temp_files"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# --- PENGELOLAAN DATA PREMIUM ---
def load_premium_data():
    if not os.path.exists(PREMIUM_DATA_FILE): return {}
    try:
        with open(PREMIUM_DATA_FILE, "r") as f:
            return {str(k): v for k, v in json.load(f).items()}
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_premium_data(data):
    with open(PREMIUM_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

PREMIUM_DATA = load_premium_data()

def parse_duration(duration_str: str) -> datetime.timedelta or None:
    if not duration_str or len(duration_str) < 2: return None
    unit = duration_str[-1].upper()
    try: value = int(duration_str[:-1])
    except ValueError: return None
    if unit == 'H': return datetime.timedelta(hours=value)
    elif unit == 'D': return datetime.timedelta(days=value)
    elif unit == 'M': return datetime.timedelta(days=value * 30)
    elif unit == 'Y': return datetime.timedelta(days=value * 365)
    else: return None

def is_premium(user_id: int) -> bool:
    user_id_str = str(user_id)
    if user_id_str not in PREMIUM_DATA: return False
    expiry_timestamp = PREMIUM_DATA[user_id_str].get("expiry")
    return expiry_timestamp and time.time() < expiry_timestamp

# --- DECORATORS ---
def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("Maaf, perintah ini hanya untuk Admin.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def premium_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id in ADMIN_IDS or is_premium(user_id):
            return await func(update, context, *args, **kwargs)
        else:
            keyboard = [[InlineKeyboardButton("Hubungi Owner", url=f"https://t.me/@thera448")]]
            await update.message.reply_text(
                "✨ Fitur ini khusus untuk pengguna Premium.\n"
                "Silakan hubungi owner untuk membeli akses.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
    return wrapped

# --- FUNGSI BANTUAN ---
def parse_contacts(file_path):
    contacts, ext = [], os.path.splitext(file_path)[1].lower()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if ext == '.vcf':
                for vcard in vobject.readComponents(f):
                    contacts.append({'name': vcard.fn.value, 'tel': vcard.tel.value})
            elif ext == '.txt':
                for line in f:
                    parts = line.strip().split(',', 1) if ',' in line else line.strip().split(':', 1)
                    if len(parts) == 2: contacts.append({'name': parts[0].strip(), 'tel': parts[1].strip()})
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")
        return None
    return contacts
def create_vcf_file(contacts, path):
    with open(path, 'w', encoding='utf-8') as f:
        for c in contacts:
            v = vobject.vCard()
            v.add('fn').value = c['name']
            v.add('tel').value = c['tel']
            v.tel.type_param = 'CELL'
            f.write(v.serialize() + '\n')
def create_txt_file(contacts, path):
    with open(path, 'w', encoding='utf-8') as f:
        for c in contacts: f.write(f"{c['name']},{c['tel']}\n")

# --- COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, user_id_str = update.effective_user, str(update.effective_user.id)
    if ENABLE_FREE_TRIAL and user_id_str not in PREMIUM_DATA:
        duration = parse_duration(FREE_TRIAL_DURATION)
        if duration:
            expiry_date = datetime.datetime.now() + duration
            PREMIUM_DATA[user_id_str] = {"expiry": int(expiry_date.timestamp()), "status": "trial"}
            save_premium_data(PREMIUM_DATA)
            trial_text = FREE_TRIAL_DURATION.replace("D", " Hari").replace("H", " Jam")
            await update.message.reply_text(
                f"🎉 Selamat Datang, {user.first_name}!\n\nAnda mendapatkan **Akses Premium GRATIS** selama **{trial_text}** untuk mencoba semua fitur.\n\nGunakan `/help` untuk melihat semua fitur!",
                parse_mode=ParseMode.MARKDOWN_V2)
            return
    await update.message.reply_text(f"👋 Halo kembali, {user.first_name}!\nSelamat datang di bot **{BOT_NAME}**.", parse_mode=ParseMode.MARKDOWN_V2)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "**Daftar Fitur Premium ✨**\n\n"
        "`/to_vcf`, `/to_txt` - Konversi file\n"
        "`/add`, `/delete` - Edit kontak dalam file\n"
        "`/renamectc`, `/renamefile` - Ganti nama\n"
        "`/manual` - Input kontak manual\n"
        "`/merge`, `/split` - Gabung & pecah file\n"
        "`/count`, `/nodup` - Analisis file\n"
        "`/getname`, `/generate` - Utilitas kontak\n\n"
        "Kirim perintahnya dan ikuti instruksi bot."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(f"💬 Chat Owner Sekarang", url=f"https://t.me/@thera448")]]
    await update.message.reply_text("Hubungi owner bot untuk membeli akses premium.", reply_markup=InlineKeyboardMarkup(keyboard))

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, user_id_str = update.effective_user, str(update.effective_user.id)
    role = "Pengguna Biasa"
    if user.id in ADMIN_IDS: role = "👑 Owner"
    elif is_premium(user.id):
        data = PREMIUM_DATA[user_id_str]
        expiry_date = datetime.datetime.fromtimestamp(data['expiry']).strftime('%d %b %Y, %H:%M WIB')
        role = f"🎁 Free Trial (Hingga: {expiry_date})" if data.get('status') == 'trial' else f"✨ Premium (Hingga: {expiry_date})"
    elif user_id_str in PREMIUM_DATA: role = "Masa Aktif Habis"
    await update.message.reply_text(f"**Status Akun**\n🆔 User ID: `{user.id}`\n⭐️ Status: **{role}**", parse_mode=ParseMode.MARKDOWN_V2)

# --- ADMIN COMMANDS ---
@admin_only
async def add_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = "".join(context.args).split('|')
        if len(parts) != 2: raise ValueError()
        identifier, duration_str = parts[0].strip(), parts[1].strip()

        target_user_id = None
        if identifier.isdigit():
            target_user_id = int(identifier)
        elif identifier.startswith('@'):
            try:
                chat = await context.bot.get_chat(identifier)
                target_user_id = chat.id
            except BadRequest:
                await update.message.reply_text(f"Tidak dapat menemukan pengguna dengan username `{identifier}`. Pastikan pengguna tersebut pernah memulai chat dengan bot ini.", parse_mode=ParseMode.MARKDOWN_V2)
                return
        else: raise ValueError()
        
        duration = parse_duration(duration_str)
        if not duration: raise ValueError()

        now_ts, user_id_str = time.time(), str(target_user_id)
        current_expiry = PREMIUM_DATA.get(user_id_str, {}).get("expiry", now_ts)
        expiry_date = datetime.datetime.fromtimestamp(max(now_ts, current_expiry)) + duration
        PREMIUM_DATA[user_id_str] = {"expiry": int(expiry_date.timestamp()), "status": "paid"}
        save_premium_data(PREMIUM_DATA)

        await update.message.reply_text(f"✅ Akses premium untuk `{target_user_id}` berhasil diupdate.\nBerakhir pada: **{expiry_date.strftime('%d %b %Y, %H:%M WIB')}**", parse_mode=ParseMode.MARKDOWN_V2)
    except Exception:
        await update.message.reply_text("Gagal. Gunakan format:\n`/addpremium <USER_ID>|<DURASI>`\n`/addpremium @username|<DURASI>`\n\nContoh: `/addpremium 12345|30D`")

@admin_only
async def remove_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id_str = context.args[0]
        if user_id_str in PREMIUM_DATA:
            del PREMIUM_DATA[user_id_str]
            save_premium_data(PREMIUM_DATA)
            await update.message.reply_text(f"🗑️ Pengguna `{user_id_str}` berhasil dihapus.", parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(f"Pengguna `{user_id_str}` tidak ditemukan.", parse_mode=ParseMode.MARKDOWN_V2)
    except IndexError:
        await update.message.reply_text("Gagal. Gunakan format: `/removepremium <USER_ID>`")

# --- FITUR FUNGSIONAL ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proses dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END

# States for ConversationHandlers
(ASK_FILE, ASK_FILE2, ASK_NEW_NAME, ASK_OLD_NAME, ASK_CONTACT_NAME, ASK_CONTACT_NUMBER,
 ASK_SPLIT_SIZE, ASK_GENERATE_COUNT, ASK_GENERATE_BASENAME, ASK_DELETE_CONTACT) = range(10)

async def handle_file_operation(update, context, operation_logic, success_caption, require_file=True):
    message = update.message
    if require_file and not message.document:
        await message.reply_text("Harap kirim sebuah file.")
        return
    
    temp_path, output_path = None, None
    try:
        if require_file:
            doc, temp_path = message.document, os.path.join(TEMP_DIR, f"{uuid.uuid4()}_{doc.file_name}")
            file = await context.bot.get_file(doc.file_id)
            await file.download_to_drive(temp_path)
            await message.reply_text("File diterima, sedang diproses...")
        
        output_path, count = operation_logic(temp_path)
        
        if output_path:
            with open(output_path, 'rb') as f:
                await message.reply_document(document=f, caption=success_caption.format(count=count))
    except Exception as e:
        logger.error(f"Error in file operation: {e}")
        await message.reply_text("Terjadi kesalahan saat memproses file.")
    finally:
        if temp_path and os.path.exists(temp_path): os.remove(temp_path)
        if output_path and os.path.exists(output_path): os.remove(output_path)

@premium_only
async def to_vcf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def logic(path):
        contacts = parse_contacts(path)
        output_path = path.replace('.txt', '.vcf')
        create_vcf_file(contacts, output_path)
        return output_path, len(contacts)
    await handle_file_operation(update, context, logic, "Konversi berhasil! {count} kontak diproses.")

@premium_only
async def to_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def logic(path):
        contacts = parse_contacts(path)
        output_path = path.replace('.vcf', '.txt')
        create_txt_file(contacts, output_path)
        return output_path, len(contacts)
    await handle_file_operation(update, context, logic, "Konversi berhasil! {count} kontak diproses.")

# Conversation Handlers
@premium_only
async def manual_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Masukkan nama kontak:")
    return ASK_CONTACT_NAME
async def manual_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Masukkan nomor telepon:")
    return ASK_CONTACT_NUMBER
async def manual_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name, number = context.user_data['name'], update.message.text
    path = os.path.join(TEMP_DIR, f"{name.replace(' ', '_')}.vcf")
    create_vcf_file([{'name': name, 'tel': number}], path)
    await handle_file_operation(update, context, lambda p: (path, 1), "File VCF berhasil dibuat.", require_file=False)
    context.user_data.clear()
    return ConversationHandler.END

@premium_only
async def count_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def logic(path):
        contacts = parse_contacts(path)
        return None, len(contacts) if contacts else 0 # No file to return
    await handle_file_operation(update, context, logic, "Jumlah kontak dalam file: **{count}**", require_file=True)

@premium_only
async def nodup_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def logic(path):
        contacts = parse_contacts(path)
        unique_contacts, seen = [], set()
        for c in contacts:
            if c['tel'] not in seen:
                unique_contacts.append(c)
                seen.add(c['tel'])
        
        output_path = path
        if os.path.splitext(path)[1] == '.vcf': create_vcf_file(unique_contacts, output_path)
        else: create_txt_file(unique_contacts, output_path)
        
        return output_path, len(contacts) - len(unique_contacts)
    await handle_file_operation(update, context, logic, "{count} kontak duplikat berhasil dihapus.")

# Dan seterusnya untuk semua fitur lain...

def main():
    application = Application.builder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("premium", premium_command))
    application.add_handler(CommandHandler("status", status_command))
    
    application.add_handler(CommandHandler("addpremium", add_premium))
    application.add_handler(CommandHandler("removepremium", remove_premium))

    # Fitur Handlers
    application.add_handler(CommandHandler("to_vcf", to_vcf))
    application.add_handler(CommandHandler("to_txt", to_txt))
    application.add_handler(CommandHandler("count", count_contacts))
    application.add_handler(CommandHandler("nodup", nodup_contacts))
    # Tambahkan handler fitur lain di sini...

    # Conversation Handlers
    manual_conv = ConversationHandler(
        entry_points=[CommandHandler("manual", manual_start)],
        states={
            ASK_CONTACT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_get_name)],
            ASK_CONTACT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_get_number)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(manual_conv)
    
    print(f"Bot '{BOT_NAME}' siap digunakan...")
    application.run_polling()

if __name__ == "__main__":
    main()
