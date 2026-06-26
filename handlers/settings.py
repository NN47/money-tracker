from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from handlers.home import send_main_screen
from keyboards.main import BACK_TEXT, currency_choice_kb, settings_menu_kb
from services.currencies import SUPPORTED_CURRENCIES
from services.users import get_user_default_currency, set_user_default_currency

router = Router()


class SettingsStates(StatesGroup):
    waiting_currency = State()


@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ Настройки", reply_markup=settings_menu_kb())


@router.message(F.text == "💱 Валюта по умолчанию")
async def default_currency_settings(message: Message, state: FSMContext):
    current = get_user_default_currency(message.from_user.id if message.from_user else None)
    await state.set_state(SettingsStates.waiting_currency)
    await message.answer(
        f"Текущая валюта по умолчанию: {current}\nВыберите новую валюту из списка:",
        reply_markup=currency_choice_kb(SUPPORTED_CURRENCIES),
    )


@router.message(SettingsStates.waiting_currency, F.text == BACK_TEXT)
async def currency_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ Настройки", reply_markup=settings_menu_kb())


@router.message(SettingsStates.waiting_currency)
async def save_default_currency(message: Message, state: FSMContext):
    value = (message.text or "").strip().upper()
    if value not in SUPPORTED_CURRENCIES:
        await message.answer("Выберите валюту кнопкой из списка.")
        return
    currency = set_user_default_currency(message.from_user.id if message.from_user else None, value)
    await state.clear()
    await message.answer(f"✅ Валюта по умолчанию изменена на {currency}", reply_markup=settings_menu_kb())


@router.message(F.text == BACK_TEXT)
async def settings_back(message: Message, state: FSMContext):
    await send_main_screen(message, state)
