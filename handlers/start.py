from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handlers.home import send_currency_converter_stub, send_main_screen

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await send_main_screen(message, state)


@router.message(F.text.in_({"💼 Главный экран", "🏠 Главное меню"}))
async def main_screen(message: Message, state: FSMContext):
    await send_main_screen(message, state)


@router.message(F.text == "💱 Конвертер валют")
async def currency_converter(message: Message, state: FSMContext):
    await send_currency_converter_stub(message, state)
