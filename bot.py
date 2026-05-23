import asyncio
import logging
import os

from aiogram import Dispatcher, Bot
from dotenv import load_dotenv

from database import init_db
from handlers import start, participants, transactions, payments, report


async def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не найден. Укажите его в .env")

    init_db()

    bot = Bot(token=token)
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(participants.router)
    dp.include_router(transactions.router)
    dp.include_router(payments.router)
    dp.include_router(report.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
