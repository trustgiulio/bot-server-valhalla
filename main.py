import os
import re
import threading
from flask import Flask
import discord
from discord.ext import commands

# ----------------------------------------------------
# 1. CONFIGURAZIONE FLASK (Per mantenere il bot attivo)
# ----------------------------------------------------
app = Flask(__name__)


@app.route("/")
def home():
  return "Il bot Discord avanzato con Flask è online e operativo!"


def run_flask():
  app.run(host="0.0.0.0", port=8080)


# ----------------------------------------------------
# 2. CONFIGURAZIONE BOT DISCORD & INTENTS
# ----------------------------------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Configurazioni per il sistema Join-to-Create (Modifica con i tuoi ID reali se necessario)
TARGET_CATEGORY_ID = 123456789012345678  # ID della categoria per le stanze vocali temporanee
TRIGGER_CHANNEL_ID = 123456789012345678  # ID del canale vocale "Crea Stanza"

# Dizionario per tracciare le stanze temporanee: {channel_id: owner_id}
created_vcs = {}


@bot.event
async def on_ready():
  print(f"Bot Connesso come {bot.user} (ID: {bot.user.id})")
  print(
      "Pronto a gestire server complessi, ruoli, canali e stanze dinamiche!"
  )


# ----------------------------------------------------
# 3. SISTEMA JOIN-TO-CREATE (Vocali Temporanee)
# ----------------------------------------------------
@bot.event
async def on_voice_state_update(member, before, after):
  guild = member.guild

  # Creazione stanza quando l'utente entra nel canale trigger
  if after.channel and after.channel.id == TRIGGER_CHANNEL_ID:
    category = guild.get_channel(TARGET_CATEGORY_ID)
    if not category or not isinstance(category, discord.CategoryChannel):
      return

    channel_name = f"🔊 Stanza di {member.display_name}"
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            connect=True, speak=True
        ),
        member: discord.PermissionOverwrite(
            manage_channels=True,
            manage_permissions=True,
            move_members=True,
            connect=True,
            speak=True,
        ),
    }

    new_vc = await guild.create_voice_channel(
        name=channel_name, category=category, overwrites=overwrites
    )
    await member.move_to(new_vc)
    created_vcs[new_vc.id] = member.id

  # Eliminazione automatica stanza vuota
  if before.channel and before.channel.id in created_vcs:
    if len(before.channel.members) == 0:
      created_vcs.pop(before.channel.id, None)
      try:
        await before.channel.delete(
            reason="Stanza vocale vuota eliminata automaticamente."
        )
      except discord.HTTPException:
        pass


# ----------------------------------------------------
# 4. COMANDO MAGICO: !setup (Crea ruoli, categorie e canali da un prompt)
# ----------------------------------------------------
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_server(ctx, *, prompt: str = None):
  """Crea automaticamente ruoli, categorie e canali leggendo il prompt dell'utente.

  Esempio: !setup Ruoli: Admin, Member | Categorie: Staff, Community | Canali:
  regolamenti, chat-generale, 🔊-lounge
  """
  if not prompt:
    await ctx.send(
        "❌ Specifica le istruzioni! Esempio:\n`!setup Ruoli: VIP, Member |"
        " Categorie: Gaming | Canali: chat, 🔊-gioco`"
    )
    return

  await ctx.send(
      "⚙️ **Analisi del prompt e generazione del server in corso...**"
  )

  try:
    # Parsing basilare del prompt separato da barre verticali (|) o sezioni
    roles_part = re.search(r"Ruoli:\s*([^|]+)", prompt, re.IGNORECASE)
    categories_part = re.search(r"Categorie:\s*([^|]+)", prompt, re.IGNORECASE)
    channels_part = re.search(r"Canali:\s*(.+)", prompt, re.IGNORECASE)

    # 1. Creazione Ruoli
    if roles_part:
      roles_list = [r.strip() for r in roles_part.group(1).split(",")]
      for role_name in roles_list:
        if role_name:
          await ctx.guild.create_role(
              name=role_name, reason="Setup automatico via bot"
          )

    # 2. Creazione Categorie
    if categories_part:
      cats_list = [c.strip() for c in categories_part.group(1).split(",")]
      for cat_name in cats_list:
        if cat_name:
          await ctx.guild.create_category(
              name=cat_name, reason="Setup automatico via bot"
          )

    # 3. Creazione Canali
    if channels_part:
      chans_list = [ch.strip() for ch in channels_part.group(1).split(",")]
      target_cat = ctx.guild.categories[0] if ctx.guild.categories else None

      for ch_name in chans_list:
        if ch_name:
          if "🔊" in ch_name or "vc" in ch_name.lower() or "vocale" in ch_name.lower():
            await ctx.guild.create_voice_channel(
                name=ch_name,
                category=target_cat,
                reason="Setup automatico via bot",
            )
          else:
            await ctx.guild.create_text_channel(
                name=ch_name,
                category=target_cat,
                reason="Setup automatico via bot",
            )

    await ctx.send(
        "✅ **Setup completato con successo!** Ruoli, categorie e canali sono"
        " stati generati in base alle tue indicazioni."
    )

  except Exception as e:
    await ctx.send(
        f"❌ Si è verificato un errore durante il setup: ```{str(e)}```"
    )


# ----------------------------------------------------
# 5. COMANDI EXTRA PER LA GESTIONE DELLE STANZE E DEL SERVER
# ----------------------------------------------------
@bot.command(name="lock")
async def lock_channel(ctx):
  """Blocca la stanza vocale temporanea corrente."""
  if ctx.author.voice and ctx.author.voice.channel:
    channel = ctx.author.voice.channel
    if channel.id in created_vcs and created_vcs[channel.id] == ctx.author.id:
      await channel.set_permissions(
          ctx.guild.default_role, connect=False, speak=True
      )
      await ctx.send(
          f"🔒 La stanza **{channel.name}** è stata bloccata.", delete_after=10
      )
    else:
      await ctx.send(
          "❌ Non sei il proprietario di questa stanza temporanea.",
          delete_after=5,
      )
  else:
    await ctx.send("❌ Devi essere in un canale vocale.", delete_after=5)


@bot.command(name="unlock")
async def unlock_channel(ctx):
  """Sblocca la stanza vocale temporanea corrente."""
  if ctx.author.voice and ctx.author.voice.channel:
    channel = ctx.author.voice.channel
    if channel.id in created_vcs and created_vcs[channel.id] == ctx.author.id:
      await channel.set_permissions(
          ctx.guild.default_role, connect=True, speak=True
      )
      await ctx.send(
          f"🔓 La stanza **{channel.name}** è stata sbloccata.", delete_after=10
      )
    else:
      await ctx.send(
          "❌ Non sei il proprietario di questa stanza temporanea.",
          delete_after=5,
      )
  else:
    await ctx.send("❌ Devi essere in un canale vocale.", delete_after=5)


@bot.command(name="kickvc")
async def kick_vc(ctx, member: discord.Member):
  """Espelle un utente dalla tua stanza vocale temporanea."""
  if ctx.author.voice and ctx.author.voice.channel:
    channel = ctx.author.voice.channel
    if channel.id in created_vcs and created_vcs[channel.id] == ctx.author.id:
      if member.voice and member.voice.channel and member.voice.channel.id == channel.id:
        await member.move_to(None)
        await ctx.send(
            f"👢 **{member.display_name}** è stato cacciato dalla stanza.",
            delete_after=10,
        )
      else:
        await ctx.send(
            "❌ L'utente non si trova nella tua stanza.", delete_after=5
        )
    else:
      await ctx.send(
          "❌ Non sei il proprietario di questa stanza.", delete_after=5
      )
  else:
    await ctx.send("❌ Devi essere in un canale vocale.", delete_after=5)


@bot.command(name="rename")
async def rename_vc(ctx, *, new_name: str):
  """Rinomina la tua stanza vocale temporanea."""
  if ctx.author.voice and ctx.author.voice.channel:
    channel = ctx.author.voice.channel
    if channel.id in created_vcs and created_vcs[channel.id] == ctx.author.id:
      await channel.edit(name=f"🔊 {new_name}")
      await ctx.send(
          f"✏️ Stanza rinominata in **🔊 {new_name}**.", delete_after=10
      )
    else:
      await ctx.send(
          "❌ Non sei il proprietario di questa stanza.", delete_after=5
      )
  else:
    await ctx.send("❌ Devi essere in un canale vocale.", delete_after=5)


# ----------------------------------------------------
# 6. AVVIO COMBINATO (Flask + Bot Discord)
# ----------------------------------------------------
if __name__ == "__main__":
  # Avvia Flask in un thread in background per l'hosting
  flask_thread = threading.Thread(target=run_flask)
  flask_thread.daemon = True
  flask_thread.start()

  # Avvia il bot Discord (Inserisci qui il tuo Token)
  TOKEN = os.environ.get("DISCORD_TOKEN", "IL_TUO_TOKEN_DISCORD_QUI")
  bot.run(TOKEN)
