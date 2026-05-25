from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.main import main_menu_kb
from services.reports import build_dashboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(build_dashboard(), reply_markup=main_menu_kb())


@router.message(F.text == "💼 Главный экран")
async def main_screen(message: Message):
    await message.answer(build_dashboard(), reply_markup=main_menu_kb())
