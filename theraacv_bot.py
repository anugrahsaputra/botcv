# theraacv_bot.py (Versi dengan Premium Berbasis Waktu)

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

# --- KONFIGURASI ---
TOKEN = "8102525608:AAH7CnM1vk-2JqwqbM5IRuv6Td1tPx-OSfk"
# Ganti 123456789 dengan User ID Telegram Anda.
ADMIN_IDS = {7660579116}

OWNER_USERNAME = "@thera448"
BOT_NAME = "TheRaaCV"

# File untuk menyimpan data premium (user_id dan tanggal kedaluwarsa)
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

# --- FUNGSI PENGELOLAAN DATA PREMIUM (JSON) ---

def load_premium_data():
    """Memuat data pengguna premium dari file JSON."""
    if not os.path.exists(PREMIUM_DATA_FILE):
        return {}
    try:
        with open(PREMIUM_DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_premium_data(data):
    """Menyimpan data pengguna premium ke file JSON."""
    with open(PREMIUM_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Muat data saat bot pertama kali dijalankan
PREMIUM_DATA = load_premium_data()

def is_premium(user_id: int) -> bool:
    """Mengecek apakah pengguna premium dan belum kedaluwarsa."""
    user_id_str = str(user_id)
    if user_id_str not in PREMIUM_DATA:
        return False
    
    expiry_timestamp = PREMIUM_DATA[user_id_str]
    return time.time() < expiry_timestamp

# States untuk ConversationHandlers (tetap sama)
(ASK_FILE, ASK_NEW_NAME, ASK_OLD_NAME, ASK_CONTACT_NAME, ASK_CONTACT_NUMBER,
 ASK_SPLIT_SIZE, ASK_MERGE_FILES, ASK_GENERATE_COUNT, ASK_GENERATE_BASENAME,
 ASK_DELETE_CONTACT) = range(10)

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
        # Cek admin ATAU pengguna premium yang valid
        if user_id in ADMIN_IDS or is_premium(user_id):
            return await func(update, context, *args, **kwargs)
        else:
            keyboard = [[InlineKeyboardButton("Hubungi Owner", url=f"https://t.me/{OWNER_USERNAME}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "✨ Fitur ini khusus untuk pengguna Premium.\n"
                "Silakan hubungi owner untuk membeli akses.",
                reply_markup=reply_markup
            )
            return
    return wrapped

# --- FUNGSI BANTUAN (HELPER FUNCTIONS) ---
# (Semua fungsi bantuan dari skrip sebelumnya, tidak ada perubahan)
def parse_contacts(file_path):
    contacts = []
    _, extension = os.path.splitext(file_path)
    try:
        if extension.lower() == '.vcf':
            with open(file_path, 'r', encoding='utf-8') as f:
                for vcard in vobject.readComponents(f):
                    name = vcard.fn.value if hasattr(vcard, 'fn') else "N/A"
                    tel = vcard.tel.value if hasattr(vcard, 'tel') else "N/A"
                    contacts.append({'name': name, 'tel': tel})
        elif extension.lower() == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if ',' in line: parts = line.strip().split(',', 1)
                    elif ':' in line: parts = line.strip().split(':', 1)
                    else: continue
                    if len(parts) == 2: contacts.append({'name': parts[0].strip(), 'tel': parts[1].strip()})
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")
        return None
    return contacts

def create_vcf_file(contacts, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for contact in contacts:
            vcard = vobject.vCard()
            vcard.add('fn').value = contact['name']
            vcard.add('tel').value = contact['tel']
            vcard.tel.type_param = 'CELL'
            f.write(vcard.serialize())
            f.write('\n')

def create_txt_file(contacts, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for contact in contacts:
            f.write(f"{contact['name']},{contact['tel']}\n")

def parse_duration(duration_str: str) -> datetime.timedelta or None:
    """Mengurai string durasi (e.g., '30D', '1M', '2Y') menjadi timedelta."""
    if not duration_str or len(duration_str) < 2:
        return None
    
    unit = duration_str[-1].upper()
    try:
        value = int(duration_str[:-1])
    except ValueError:
        return None

    if unit == 'D':
        return datetime.timedelta(days=value)
    elif unit == 'M':
        return datetime.timedelta(days=value * 30)  # Aproksimasi 1 bulan = 30 hari
    elif unit == 'Y':
        return datetime.timedelta(days=value * 365) # Aproksimasi 1 tahun = 365 hari
    else:
        return None

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Halo, {user_name}! Selamat datang di **{BOT_NAME}**.\n\n"
        "Bot ini memiliki fitur premium berbasis langganan.\n"
        "`/help` - Lihat semua fitur\n"
        "`/premium` - Beli akses premium\n"
        "`/status` - Cek status langganan Anda",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Isi help_command sama seperti sebelumnya)
    help_text = (
        "**Daftar Fitur Premium ✨**\n\n"
        "`/to_vcf`, `/to_txt` - Konversi file\n"
        "`/add`, `/delete` - Edit kontak dalam file\n"
        "`/renamectc`, `/renamefile` - Ganti nama\n"
        "`/manual` - Input kontak manual\n"
        "`/merge`, `/split` - Gabung & pecah file\n"
        "`/count`, `/nodup` - Analisis file\n"
        "`/getname`, `/generate` - Utilitas kontak"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Isi premium_command sama seperti sebelumnya)
    keyboard = [[InlineKeyboardButton(f"💬 Chat Owner Sekarang", url=f"https://t.me/@thera448")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Hubungi owner bot dengan menekan tombol di bawah ini untuk membeli akses premium.",
        reply_markup=reply_markup
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id_str = str(user.id)
    role = "Pengguna Biasa"

    if user.id in ADMIN_IDS:
        role = "👑 Owner"
    elif is_premium(user.id):
        expiry_ts = PREMIUM_DATA[user_id_str]
        expiry_date = datetime.datetime.fromtimestamp(expiry_ts)
        # Menyesuaikan dengan zona waktu lokal (contoh: WIB/GMT+7)
        expiry_date_local = expiry_date.strftime('%d %B %Y, %H:%M')
        role = f"✨ Premium (Berakhir pada: {expiry_date_local})"
    elif user_id_str in PREMIUM_DATA: # Jika ada di data tapi sudah tidak premium
        role = "Masa Premium Habis"
        
    status_text = (
        f"**Status Akun Anda**\n"
        f"👤 Nama: `{user.full_name}`\n"
        f"🆔 User ID: `{user.id}`\n"
        f"⭐️ Status: **{role}**"
    )
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN_V2)

# --- PERINTAH ADMIN ---
@admin_only
async def add_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Gabungkan argumen dan pisahkan berdasarkan '|'
        args_str = "".join(context.args)
        parts = args_str.split('|')
        
        if len(parts) != 2:
            raise ValueError("Format salah")

        user_identifier = parts[0].strip()
        duration_str = parts[1].strip()

        # Dapatkan User ID
        target_user_id = None
        if user_identifier.isdigit():
            target_user_id = int(user_identifier)
        elif user_identifier.startswith('@'):
            # Ini memerlukan cara untuk resolve username ke ID, yang tidak trivial
            # Untuk sekarang, kita minta admin menggunakan User ID saja.
            await update.message.reply_text("Fitur username belum didukung. Harap gunakan User ID (angka).")
            return
        else:
            raise ValueError("Identifier pengguna tidak valid")
        
        # Parse Durasi
        duration = parse_duration(duration_str)
        if duration is None:
            await update.message.reply_text("Format durasi tidak valid. Gunakan format seperti `30D` (Hari), `1M` (Bulan), atau `1Y` (Tahun).")
            return
        
        # Hitung tanggal kedaluwarsa
        # Jika user sudah premium, perpanjang dari tanggal expiry yang ada
        now_ts = time.time()
        current_expiry = PREMIUM_DATA.get(str(target_user_id), now_ts)
        start_date = datetime.datetime.fromtimestamp(max(now_ts, current_expiry))
        
        expiry_date = start_date + duration
        expiry_timestamp = int(expiry_date.timestamp())

        # Simpan data
        PREMIUM_DATA[str(target_user_id)] = expiry_timestamp
        save_premium_data(PREMIUM_DATA)

        expiry_date_str = expiry_date.strftime('%d %B %Y, %H:%M')
        await update.message.reply_text(
            f"✅ Akses premium untuk User ID `{target_user_id}` berhasil diperbarui.\n"
            f"Masa aktif hingga: **{expiry_date_str}**"
        )

    except Exception as e:
        logger.error(f"Error di addpremium: {e}")
        await update.message.reply_text(
            "Gagal. Gunakan format: `/addpremium <USER_ID>|<DURASI>`\n"
            "Contoh: `/addpremium 7660579116|30D`"
        )

@admin_only
async def remove_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id_str = context.args[0]
        if user_id_str in PREMIUM_DATA:
            del PREMIUM_DATA[user_id_str]
            save_premium_data(PREMIUM_DATA)
            await update.message.reply_text(f"🗑️ Pengguna dengan ID `{user_id_str}` berhasil dihapus dari daftar premium.")
        else:
            await update.message.reply_text(f"Pengguna dengan ID `{user_id_str}` tidak ditemukan di daftar premium.")
    except (IndexError, ValueError):
        await update.message.reply_text("Gagal. Gunakan format: `/removepremium <USER_ID>`")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Proses dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END

# --- SEMUA FITUR FUNGSIONAL (KINI PREMIUM) ---
# (PENTING: Pastikan semua fungsi ini sudah ada di skrip Anda dari versi sebelumnya.
# Mereka semua harus memiliki decorator @premium_only)

@premium_only
async def to_vcf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Kode lengkap fungsi to_vcf)
    pass 

# ... dan seterusnya untuk semua fitur lain seperti /to_txt, /merge, /split, dll.

def main():
    """Jalankan bot."""
    application = Application.builder().token(TOKEN).build()
    
    # Handler dasar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("premium", premium_command))
    application.add_handler(CommandHandler("status", status_command))

    # Handler Admin
    application.add_handler(CommandHandler("addpremium", add_premium))
    application.add_handler(CommandHandler("removepremium", remove_premium))
    
    # Handler Fitur Premium (Tambahkan semua fitur Anda di sini)
    application.add_handler(CommandHandler("to_vcf", to_vcf))
    # ...
    
    print(f"Bot '{BOT_NAME}' dengan sistem premium waktu sedang berjalan...")
    application.run_polling()


if __name__ == "__main__":
    # Pastikan semua fungsi handler fitur (to_vcf, merge_start, dll.) 
    # sudah ada di dalam file ini sebelum menjalankan main().
    main()
