from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import get_connection, now_iso
from keyboards.main import main_menu_kb, participants_menu_kb

router = Router()


class ParticipantStates(StatesGroup):
    waiting_name = State()
    waiting_delete_id = State()


@router.message(F.text == "👥 Участники")
async def participants_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Раздел участников:", reply_markup=participants_menu_kb())


@router.message(F.text == "➕ Добавить")
async def add_participant_start(message: Message, state: FSMContext):
    await state.set_state(ParticipantStates.waiting_name)
    await message.answer("Введите имя участника:")


@router.message(ParticipantStates.waiting_name)
async def add_participant_finish(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым. Введите снова:")
        return
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO participants(name, created_at) VALUES(?, ?)",
            (name, now_iso()),
        )
    await state.clear()
    await message.answer(f"Участник «{name}» добавлен.", reply_markup=participants_menu_kb())


@router.message(F.text == "📋 Список")
async def list_participants(message: Message):
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name FROM participants ORDER BY id").fetchall()
    if not rows:
        await message.answer("Список участников пуст.")
        return
    text = "👥 Участники:\n" + "\n".join(f"{row['id']}. {row['name']}" for row in rows)
    await message.answer(text)


@router.message(F.text == "❌ Удалить")
async def delete_participant_start(message: Message, state: FSMContext):
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name FROM participants ORDER BY id").fetchall()
    if not rows:
        await message.answer("Удалять пока некого.")
        return
    text = "Введите ID участника для удаления:\n" + "\n".join(
        f"{row['id']}. {row['name']}" for row in rows
    )
    await state.set_state(ParticipantStates.waiting_delete_id)
    await message.answer(text)


@router.message(ParticipantStates.waiting_delete_id)
async def delete_participant_finish(message: Message, state: FSMContext):
    try:
        participant_id = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Введите корректный числовой ID.")
        return
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM participants WHERE id = ?", (participant_id,))
    await state.clear()
    if cur.rowcount:
        await message.answer("Участник удалён.", reply_markup=participants_menu_kb())
    else:
        await message.answer("Участник с таким ID не найден.", reply_markup=participants_menu_kb())


@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_kb())
