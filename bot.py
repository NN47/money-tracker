import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from dotenv import load_dotenv

from database import init_db
from handlers import payments, report, start, transactions


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
    webhook_url: str = app["webhook_url"]
    await bot.set_webhook(f"{webhook_url}/webhook")


async def on_cleanup(app: web.Application) -> None:
    bot: Bot = app["bot"]
    await bot.session.close()


async def main() -> None:
    load_dotenv()

    token = os.getenv("BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")
    port = int(os.getenv("PORT", 10000))

    if not token:
        raise RuntimeError("BOT_TOKEN не найден. Укажите его в .env")
    if not webhook_url:
        raise RuntimeError("WEBHOOK_URL не найден. Укажите его в .env")

    init_db()

    bot = Bot(token=token)
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(transactions.router)
    dp.include_router(payments.router)
    dp.include_router(report.router)

    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app["webhook_url"] = webhook_url.rstrip("/")

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
