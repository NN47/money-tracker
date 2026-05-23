from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.main import main_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для учёта финансов. Выберите действие:",
        reply_markup=main_menu_kb(),
    )
