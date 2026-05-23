from aiogram import F, Router
from aiogram.types import Message

from services.reports import build_summary_report

router = Router()


@router.message(F.text == "📊 Отчёт")
async def report(message: Message):
    await message.answer(build_summary_report())
