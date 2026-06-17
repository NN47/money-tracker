from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.main import dashboard_actions_kb, main_menu_kb, recurring_due_kb
from services.recurring_payments import fetch_unpaid_due_recurring_payments
from services.reports import build_dashboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    unpaid_operations = fetch_unpaid_due_recurring_payments()
    due_kb = recurring_due_kb(unpaid_operations)
    extra_rows = due_kb.inline_keyboard if due_kb else None
    await message.answer(build_dashboard(), reply_markup=dashboard_actions_kb(extra_rows), parse_mode="HTML")
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


@router.message(F.text == "💼 Главный экран")
async def main_screen(message: Message, state: FSMContext):
    await state.clear()
    unpaid_operations = fetch_unpaid_due_recurring_payments()
    due_kb = recurring_due_kb(unpaid_operations)
    extra_rows = due_kb.inline_keyboard if due_kb else None
    await message.answer(build_dashboard(), reply_markup=dashboard_actions_kb(extra_rows), parse_mode="HTML")
    await message.answer("Главное меню:", reply_markup=main_menu_kb())
