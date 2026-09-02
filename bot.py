from __future__ import annotations

import asyncio
import io
import logging
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
import discord

from detector import Detection, ScamImageDetector
from proof_renderer import render_message_proof


def load_env_file(path: Path) -> None:
    """Carrega KEY=VALUE sem imprimir ou sobrescrever variáveis existentes."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(Path(__file__).parent / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("SAS")

TOKEN = os.environ.get("DISCORD_TOKEN", "")
BOT_STATUS = os.environ.get("BOT_STATUS", "SAS | Protegendo o servidor")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() in {"1", "true", "yes", "sim"}
TIMEOUT_DAYS = int(os.environ.get("TIMEOUT_DAYS", "7"))
THRESHOLD = int(os.environ.get("DETECTION_THRESHOLD", "6"))
LOG_CHANNEL_ID = int(os.environ["LOG_CHANNEL_ID"]) if os.environ.get("LOG_CHANNEL_ID") else None
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
detector = ScamImageDetector(Path(__file__).parent / "references", THRESHOLD)
scan_slots = asyncio.Semaphore(2)
timeout_tasks: dict[tuple[int, int], asyncio.Task[None]] = {}
removal_notified: set[tuple[int, int]] = set()
sas_timeout_targets: dict[tuple[int, int], datetime] = {}


def is_image(attachment: discord.Attachment) -> bool:
    content_type = (attachment.content_type or "").lower()
    suffix = Path(attachment.filename).suffix.lower()
    return content_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp"}


async def report(
    message: discord.Message,
    finding: Detection,
    proof_image: bytes,
    errors: list[str] | None = None,
) -> None:
    member = message.author
    assert isinstance(member, discord.Member)
    signals = ", ".join(finding.matched_terms) or "hash visual"
    day_label = "Dia" if TIMEOUT_DAYS == 1 else "Dias"
    prefix = "**MODO TESTE**\n" if DRY_RUN else ""
    content = (
        f"{prefix}"
        f"**Nome:** {discord.utils.escape_markdown(member.display_name)} <@{member.id}>\n"
        f"**ID:** {member.id}\n"
        f"**Tempo:** {TIMEOUT_DAYS} {day_label}\n"
        f"**Motivo:** Discord hackeado.\n"
        f"**Sinais:** {signals}.\n"
        f"**Provas:** Em anexo"
    )
    if errors:
        content += "\n**Erros:** " + "; ".join(errors)

    log.warning(
        "Detecção: autor=%s (%s), score=%s, hash_distance=%s, sinais=[%s]%s",
        member,
        member.id,
        finding.score,
        finding.perceptual_distance,
        signals,
        " | " + "; ".join(errors) if errors else "",
    )
    if not LOG_CHANNEL_ID:
        return
    channel = client.get_channel(LOG_CHANNEL_ID)
    if isinstance(channel, discord.abc.Messageable):
        proof_filename = f"prova-mensagem-{message.id}.png"
        proof = discord.File(io.BytesIO(proof_image), filename=proof_filename)
        embed = discord.Embed(description=content, colour=discord.Colour.red())
        embed.set_image(url=f"attachment://{proof_filename}")
        try:
            await channel.send(
                embed=embed,
                file=proof,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
        except discord.HTTPException as exc:
            log.error("Falha ao enviar o log ao canal %s: %s", LOG_CHANNEL_ID, exc)


async def moderate(
    message: discord.Message,
    finding: Detection,
    evidence: list[tuple[str, bytes]],
) -> None:
    member = message.author
    assert isinstance(member, discord.Member)
    try:
        avatar = await member.display_avatar.with_size(128).read()
    except discord.HTTPException:
        avatar = None
    proof_image = await asyncio.to_thread(
        render_message_proof,
        display_name=member.display_name,
        username=member.name,
        avatar=avatar,
        content=message.content,
        created_at=message.created_at,
        guild_name=message.guild.name,
        guild_id=message.guild.id,
        channel_name=getattr(message.channel, "name", str(message.channel.id)),
        channel_id=message.channel.id,
        message_id=message.id,
        user_id=member.id,
        evidence=evidence,
    )
    if DRY_RUN:
        await report(message, finding, proof_image)
        return

    errors = []
    try:
        await message.delete()
    except discord.HTTPException as exc:
        errors.append(f"falha ao apagar: {exc}")
    timeout_applied = False
    timeout_key = (member.guild.id, member.id)
    sas_timeout_targets[timeout_key] = discord.utils.utcnow() + timedelta(days=TIMEOUT_DAYS)
    try:
        await member.timeout(timedelta(days=TIMEOUT_DAYS), reason="Discord hackeado — imagem de golpe detectada")
        timeout_applied = True
    except (discord.Forbidden, discord.HTTPException) as exc:
        sas_timeout_targets.pop(timeout_key, None)
        errors.append(f"falha no timeout: {exc}")

    if timeout_applied:
        dm_filename = f"prova-mensagem-{message.id}.png"
        dm_proof = discord.File(io.BytesIO(proof_image), filename=dm_filename)
        dm_embed = discord.Embed(
            title="⌛ Timeout aplicado",
            description=f"Você recebeu um timeout no servidor **{discord.utils.escape_markdown(message.guild.name)}**.",
            colour=discord.Colour.green(),
            timestamp=discord.utils.utcnow(),
        )
        day_label = "Dia" if TIMEOUT_DAYS == 1 else "Dias"
        dm_embed.add_field(name="Duração", value=f"`{TIMEOUT_DAYS} {day_label}`", inline=False)
        dm_embed.add_field(name="Motivo", value="Discord hackeado.", inline=False)
        dm_embed.set_image(url=f"attachment://{dm_filename}")
        dm_embed.set_footer(text="SAS — Sistema de moderação")
        try:
            await member.send(embed=dm_embed, file=dm_proof)
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"não foi possível enviar a mensagem privada: {exc}")

    await report(message, finding, proof_image, errors)


async def notify_timeout_removed(member: discord.Member) -> None:
    key = (member.guild.id, member.id)
    if key in removal_notified:
        return
    removal_notified.add(key)
    embed = discord.Embed(
        title="✅ Timeout removido",
        description=(
            f"Seu timeout no servidor **{discord.utils.escape_markdown(member.guild.name)}** foi removido.\n"
            "Você já pode voltar a participar normalmente."
        ),
        colour=discord.Colour.green(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text="SAS — Sistema de moderação")
    try:
        await member.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning("Não foi possível avisar %s sobre a remoção do timeout: %s", member.id, exc)


def format_timeout_duration(until) -> str:
    seconds = max(1, math.ceil((until - discord.utils.utcnow()).total_seconds()))
    if seconds >= 86400:
        value = math.ceil(seconds / 86400)
        return f"{value} {'Dia' if value == 1 else 'Dias'}"
    if seconds >= 3600:
        value = math.ceil(seconds / 3600)
        return f"{value} {'Hora' if value == 1 else 'Horas'}"
    value = math.ceil(seconds / 60)
    return f"{value} {'Minuto' if value == 1 else 'Minutos'}"


async def get_manual_timeout_details(member: discord.Member) -> tuple[str, str]:
    """Obtém motivo e moderador do Audit Log quando o bot tem permissão."""
    await asyncio.sleep(1.0)  # dá tempo para a entrada aparecer no Audit Log
    try:
        async for entry in member.guild.audit_logs(limit=8, action=discord.AuditLogAction.member_update):
            target_id = getattr(entry.target, "id", None)
            age = abs((discord.utils.utcnow() - entry.created_at).total_seconds())
            changed_timeout = getattr(entry.after, "timed_out_until", None)
            if target_id == member.id and age <= 30 and changed_timeout is not None:
                reason = entry.reason or "Não informado."
                moderator = getattr(entry.user, "display_name", None) or getattr(entry.user, "name", None) or "Desconhecido"
                return reason, moderator
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning("Sem acesso ao Audit Log para obter o motivo do timeout de %s: %s", member.id, exc)
    return "Não informado.", "Desconhecido"


async def notify_manual_timeout(member: discord.Member) -> None:
    until = member.timed_out_until
    if until is None:
        return
    reason, moderator = await get_manual_timeout_details(member)
    embed = discord.Embed(
        title="⌛ Timeout aplicado",
        description=f"Você recebeu um timeout no servidor **{discord.utils.escape_markdown(member.guild.name)}**.",
        colour=discord.Colour.green(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Duração", value=f"`{format_timeout_duration(until)}`", inline=False)
    embed.add_field(name="Motivo", value=discord.utils.escape_markdown(reason)[:1024], inline=False)
    embed.add_field(name="Aplicado por", value=discord.utils.escape_markdown(moderator), inline=False)
    embed.set_footer(text="SAS — Sistema de moderação")
    try:
        await member.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning("Não foi possível avisar %s sobre o timeout manual: %s", member.id, exc)


def schedule_timeout_expiry(member: discord.Member) -> None:
    """Agenda uma verificação no vencimento, mesmo se o Gateway não emitir outro evento."""
    until = member.timed_out_until
    if until is None or until <= discord.utils.utcnow():
        return

    key = (member.guild.id, member.id)
    removal_notified.discard(key)
    previous = timeout_tasks.pop(key, None)
    if previous and previous is not asyncio.current_task():
        previous.cancel()

    async def wait_and_check() -> None:
        try:
            delay = max(0.0, (until - discord.utils.utcnow()).total_seconds())
            await asyncio.sleep(delay + 1.0)
            fresh = await member.guild.fetch_member(member.id)
            if fresh.is_timed_out():
                schedule_timeout_expiry(fresh)
                return
            await notify_timeout_removed(fresh)
        except asyncio.CancelledError:
            raise
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            log.warning("Não foi possível verificar o fim do timeout de %s: %s", member.id, exc)
        finally:
            if timeout_tasks.get(key) is asyncio.current_task():
                timeout_tasks.pop(key, None)

    timeout_tasks[key] = asyncio.create_task(wait_and_check(), name=f"timeout-expiry-{member.guild.id}-{member.id}")


@client.event
async def on_ready() -> None:
    await client.change_presence(activity=discord.CustomActivity(name=BOT_STATUS))
    log.info(
        "SAS conectado como %s | dry-run=%s | referências=%d",
        client.user,
        DRY_RUN,
        len(detector.reference_hashes),
    )
    # Reconstrói os agendamentos após uma reinicialização do bot.
    for guild in client.guilds:
        for member in guild.members:
            if member.is_timed_out():
                schedule_timeout_expiry(member)


@client.event
async def on_member_update(before: discord.Member, after: discord.Member) -> None:
    """Avisa por DM quando um timeout expira ou é removido manualmente."""
    if after.bot:
        return
    key = (after.guild.id, after.id)
    if before.is_timed_out() and not after.is_timed_out():
        sas_timeout_targets.pop(key, None)
        task = timeout_tasks.pop(key, None)
        if task:
            task.cancel()
        await notify_timeout_removed(after)
    elif after.is_timed_out() and before.timed_out_until != after.timed_out_until:
        schedule_timeout_expiry(after)
        expected_until = sas_timeout_targets.pop(key, None)
        if expected_until is not None:
            difference = abs((after.timed_out_until - expected_until).total_seconds())
            if difference <= 10:
                return
        await notify_manual_timeout(after)


@client.event
async def on_message(message: discord.Message) -> None:
    if not message.guild or message.author.bot or not isinstance(message.author, discord.Member):
        return
    # O Discord não permite timeout do dono/admin; também evitamos qualquer tentativa.
    if message.author == message.guild.owner or message.author.guild_permissions.administrator:
        return

    evidence: list[tuple[str, bytes]] = []
    for attachment in message.attachments:
        if not is_image(attachment) or attachment.size > MAX_IMAGE_BYTES:
            continue
        try:
            async with scan_slots:
                payload = await attachment.read(use_cached=True)
                evidence.append((attachment.filename, payload))
        except (discord.HTTPException, aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.warning("Não foi possível analisar anexo %s: %s", attachment.id, exc)

    for _, payload in evidence:
        async with scan_slots:
            finding = await asyncio.to_thread(detector.analyse, payload)

        if finding.suspicious:
            await moderate(message, finding, evidence)
            return


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Defina DISCORD_TOKEN no arquivo .env")
    client.run(TOKEN, log_handler=None)
