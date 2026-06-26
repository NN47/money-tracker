import asyncio
import contextlib
import logging
import os
from datetime import datetime, timedelta, time

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from dotenv import load_dotenv

from database import init_db
from handlers import payments, report, settings, start, transactions
from services.recurring_payments import MOSCOW_TZ, fetch_unpaid_due_recurring_payments


def seconds_until_next_moscow_notification() -> float:
    now = datetime.now(MOSCOW_TZ)
    target = datetime.combine(now.date(), time(hour=13), tzinfo=MOSCOW_TZ)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def recurring_payment_notifier(bot: Bot, owner_telegram_id: int) -> None:
    while True:
        await asyncio.sleep(seconds_until_next_moscow_notification())
        try:
            operations = fetch_unpaid_due_recurring_payments()
            if operations:
                await payments.send_recurring_payment_notification(bot, owner_telegram_id)
        except Exception:
            logging.exception("Failed to send recurring payment notification")


async def healthcheck(_: web.Request) -> web.Response:
    return web.Response(text="Money Tracker Bot is running")


async def telegram_webhook(request: web.Request) -> web.Response:
    bot: Bot = request.app["bot"]
    dp: Dispatcher = request.app["dp"]

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)

    return web.Response(text="OK")


async def on_startup(app: web.Application) -> None:
    bot: Bot = app["bot"]
    dp: Dispatcher = app["dp"]
    webhook_url: str = app["webhook_url"]
    allowed_updates = dp.resolve_used_update_types()
    await bot.set_webhook(f"{webhook_url}/webhook", allowed_updates=allowed_updates)
    logging.info("Webhook configured with allowed updates: %s", allowed_updates)
    owner_telegram_id: int | None = app.get("owner_telegram_id")
    if owner_telegram_id is None:
        logging.warning("OWNER_TELEGRAM_ID is not set; recurring payment notifications are disabled")
        return
    app["recurring_payment_notifier"] = asyncio.create_task(
        recurring_payment_notifier(bot, owner_telegram_id)
    )


async def on_cleanup(app: web.Application) -> None:
    notifier = app.get("recurring_payment_notifier")
    if notifier:
        notifier.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await notifier
    bot: Bot = app["bot"]
    await bot.session.close()


async def main() -> None:
    load_dotenv()

    token = os.getenv("BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")
    owner_telegram_id_raw = os.getenv("OWNER_TELEGRAM_ID")
    owner_telegram_id = int(owner_telegram_id_raw) if owner_telegram_id_raw else None
    port = int(os.getenv("PORT", 10000))

    if not token:
        raise RuntimeError("BOT_TOKEN не найден. Укажите его в .env")
    if not webhook_url:
        raise RuntimeError("WEBHOOK_URL не найден. Укажите его в .env")

    init_db()

    bot = Bot(token=token)
    dp = Dispatcher()
    payments.configure_owner(owner_telegram_id)

    dp.include_router(start.router)
    dp.include_router(transactions.router)
    dp.include_router(payments.router)
    dp.include_router(report.router)
    dp.include_router(settings.router)

    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app["webhook_url"] = webhook_url.rstrip("/")
    app["owner_telegram_id"] = owner_telegram_id

    app.router.add_get("/", healthcheck)
    app.router.add_post("/webhook", telegram_webhook)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()

    logging.info("Server started on 0.0.0.0:%s", port)

    stop_event = asyncio.Event()
    await stop_event.wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
