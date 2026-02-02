from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trustora.amounts import format_amount, quantize_amount, to_decimal
from trustora.chains import validate_address
from trustora.config import load_settings
from trustora.config_service import get_config, update_config
from trustora.db import create_engine, create_session_factory
from trustora.enums import Chain, DisputeStatus, EscrowStatus, MessageRole, MessageType, Token
from trustora.escrow import get_escrow_for_update, transition_escrow
from trustora.fees import DEFAULT_FEE_SNAPSHOT, calculate_fee, calculate_net
from trustora.models import Dispute, Escrow, Message as EscrowMessage, User
from trustora.reviews import build_review_post, user_public_hash
from trustora.security import SignedRequest, generate_nonce, sign_hmac
from trustora.state_machine import validate_transition

logging.basicConfig(level=logging.INFO)


class EscrowFlow(StatesGroup):
    seller_id = State()
    amount = State()
    chain = State()
    payout_address = State()
    confirm_network = State()


MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ New Escrow"), KeyboardButton(text="🧾 My Deals")],
        [KeyboardButton(text="💸 Fees"), KeyboardButton(text="📘 How It Works")],
        [KeyboardButton(text="🆘 Support")],
    ],
    resize_keyboard=True,
)


async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None, salt: str) -> User:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if user:
        user.last_active_at = datetime.utcnow()
        session.add(user)
        return user
    public_hash = user_public_hash(tg_id, salt)
    user = User(
        tg_id=tg_id,
        username=username,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
        public_hash=public_hash,
    )
    session.add(user)
    return user


async def ensure_not_blocked(message: Message, session_factory) -> bool:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
        user = result.scalar_one_or_none()
    if user and user.is_blocked:
        await message.answer("Your account is blocked. Contact support.")
        return False
    return True


def generate_room_code() -> str:
    prefix = "TR"
    suffix = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{suffix}"


async def request_deposit_address(settings, chain: Chain) -> str:
    payload = {"chain": chain.value}
    timestamp = int(datetime.utcnow().timestamp())
    nonce = generate_nonce()
    message = f"address|{chain.value}|{timestamp}|{nonce}"
    signature = sign_hmac(settings.signer_hmac_secret, message)
    payload.update({"timestamp": timestamp, "nonce": nonce, "signature": signature})
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"{settings.signer_base_url}/address", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["address"]


async def handle_start(message: Message, state: FSMContext, session_factory, settings) -> None:
    async with session_factory() as session:
        async with session.begin():
            await get_or_create_user(session, message.from_user.id, message.from_user.username, settings.public_hash_salt)
    if not await ensure_not_blocked(message, session_factory):
        return
    await state.clear()
    await message.answer("Welcome to Trustora Escrow. Choose an option:", reply_markup=MENU)


async def new_escrow(message: Message, state: FSMContext, session_factory) -> None:
    if not await ensure_not_blocked(message, session_factory):
        return
    await state.set_state(EscrowFlow.seller_id)
    await message.answer("Enter seller Telegram ID (numeric).")


async def set_seller_id(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Please enter a numeric Telegram ID.")
        return
    await state.update_data(seller_id=int(message.text))
    await state.set_state(EscrowFlow.amount)
    await message.answer("Enter amount expected in USDT.")


async def set_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = quantize_amount(message.text or "")
    except ValueError:
        await message.answer("Enter a valid number.")
        return
    if amount <= 0:
        await message.answer("Amount must be positive.")
        return
    await state.update_data(amount=amount)
    await state.set_state(EscrowFlow.chain)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="TRC20"), KeyboardButton(text="BEP20")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer("Select chain:", reply_markup=keyboard)


async def set_chain(message: Message, state: FSMContext) -> None:
    if message.text not in {Chain.TRC20.value, Chain.BEP20.value}:
        await message.answer("Choose TRC20 or BEP20.")
        return
    await state.update_data(chain=message.text)
    await state.set_state(EscrowFlow.payout_address)
    await message.answer("Enter seller payout address for this chain.")


async def set_payout_address(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    chain = Chain(data["chain"])
    address = message.text or ""
    if not validate_address(chain, address):
        await message.answer("Invalid address for selected chain.")
        return
    await state.update_data(payout_address=address)
    await state.set_state(EscrowFlow.confirm_network)
    await message.answer(
        "⚠️ Ensure you are sending ONLY on the selected network.\n"
        "Tap 'I Understand' to reveal deposit details.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="I Understand")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


async def confirm_network(
    message: Message,
    state: FSMContext,
    session_factory,
    settings,
) -> None:
    if message.text != "I Understand":
        await message.answer("Please confirm by tapping 'I Understand'.")
        return
    data = await state.get_data()
    chain = Chain(data["chain"])
    deposit_address = await request_deposit_address(settings, chain)
    amount_expected = quantize_amount(data["amount"])
    async with session_factory() as session:
        async with session.begin():
            config = await get_config(session)
            snapshot = DEFAULT_FEE_SNAPSHOT
            if config and config.json:
                snapshot = DEFAULT_FEE_SNAPSHOT.__class__(
                    flat_fee=to_decimal(config.json.get("fee_flat", DEFAULT_FEE_SNAPSHOT.flat_fee)),
                    percent_fee=to_decimal(
                        config.json.get("fee_percent", DEFAULT_FEE_SNAPSHOT.percent_fee)
                    ),
                    threshold=to_decimal(config.json.get("fee_threshold", DEFAULT_FEE_SNAPSHOT.threshold)),
                )
            fee_amount = calculate_fee(amount_expected, snapshot)
            net_amount = calculate_net(amount_expected, snapshot)
            escrow = Escrow(
                room_code=generate_room_code(),
                buyer_tg_id=message.from_user.id,
                seller_tg_id=int(data["seller_id"]),
                chain=chain,
                token=Token.USDT,
                amount_expected=amount_expected,
                amount_received=None,
                fee_snapshot_json={
                    "flat_fee": format_amount(snapshot.flat_fee),
                    "percent_fee": str(snapshot.percent_fee),
                    "threshold": str(snapshot.threshold),
                },
                fee_amount=fee_amount,
                net_amount=net_amount,
                deposit_address=deposit_address,
                deposit_tx_hash=None,
                deposit_confirmations=0,
                payout_address=data["payout_address"],
                payout_tx_hash=None,
                payout_confirmations=0,
                status=EscrowStatus.AWAITING_DEPOSIT,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(escrow)
    await state.clear()
    await message.answer(
        f"Escrow created. Room: {escrow.room_code}\n"
        f"Deposit Address: `{escrow.deposit_address}`\n"
        f"Amount: {escrow.amount_expected} USDT\n"
        f"Network: {escrow.chain.value}\n",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MENU,
    )


async def list_deals(message: Message, session_factory) -> None:
    if not await ensure_not_blocked(message, session_factory):
        return
    async with session_factory() as session:
        result = await session.execute(
            select(Escrow)
            .where(
                (Escrow.buyer_tg_id == message.from_user.id)
                | (Escrow.seller_tg_id == message.from_user.id)
            )
            .order_by(Escrow.created_at.desc())
            .limit(5)
        )
        escrows = result.scalars().all()
    if not escrows:
        await message.answer("No deals yet.", reply_markup=MENU)
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=e.room_code, callback_data=f"room:{e.id}")]
            for e in escrows
        ]
    )
    await message.answer("Your recent deals:", reply_markup=keyboard)


async def show_fees(message: Message) -> None:
    await message.answer(
        "Fees: 5 USDT for deals up to 100 USDT, then 2%.",
        reply_markup=MENU,
    )


async def how_it_works(message: Message) -> None:
    await message.answer(
        "Trustora Escrow holds funds until buyer releases. Use TRC20 or BEP20 only.",
        reply_markup=MENU,
    )


async def support(message: Message) -> None:
    await message.answer("Support: contact @trustora_support", reply_markup=MENU)


def deal_room_keyboard(escrow: Escrow, is_buyer: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🧾 Summary", callback_data=f"summary:{escrow.id}")],
        [InlineKeyboardButton(text="💳 Deposit Details", callback_data=f"deposit:{escrow.id}")],
        [InlineKeyboardButton(text="💬 Chat", callback_data=f"chat:{escrow.id}")],
    ]
    if is_buyer and escrow.status == EscrowStatus.FUNDS_LOCKED:
        buttons.append([InlineKeyboardButton(text="✅ Release", callback_data=f"release:{escrow.id}")])
    buttons.append([InlineKeyboardButton(text="⚖️ Dispute", callback_data=f"dispute:{escrow.id}")])
    buttons.append([InlineKeyboardButton(text="🆘 Support", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_room(callback: CallbackQuery, session_factory) -> None:
    escrow_id = uuid.UUID(callback.data.split(":", 1)[1])
    async with session_factory() as session:
        result = await session.execute(select(Escrow).where(Escrow.id == escrow_id))
        escrow = result.scalar_one()
    is_buyer = callback.from_user.id == escrow.buyer_tg_id
    await callback.message.answer(
        f"Room {escrow.room_code} | Status: {escrow.status.value}\n"
        f"Amount: {escrow.amount_expected} USDT",
        reply_markup=deal_room_keyboard(escrow, is_buyer),
    )
    await callback.answer()


async def show_summary(callback: CallbackQuery, session_factory) -> None:
    escrow_id = uuid.UUID(callback.data.split(":", 1)[1])
    async with session_factory() as session:
        result = await session.execute(select(Escrow).where(Escrow.id == escrow_id))
        escrow = result.scalar_one()
    text = (
        f"🧾 Deal Summary\nRoom: {escrow.room_code}\n"
        f"Status: {escrow.status.value}\n"
        f"Amount: {escrow.amount_expected} USDT\n"
        f"Fee: {escrow.fee_amount} USDT\n"
        f"Net: {escrow.net_amount} USDT"
    )
    await callback.message.answer(text)
    await callback.answer()


async def show_deposit(callback: CallbackQuery, session_factory) -> None:
    escrow_id = uuid.UUID(callback.data.split(":", 1)[1])
    async with session_factory() as session:
        result = await session.execute(select(Escrow).where(Escrow.id == escrow_id))
        escrow = result.scalar_one()
    text = (
        f"💳 Deposit Details\n"
        f"Network: {escrow.chain.value}\n"
        f"Address: `{escrow.deposit_address}`\n"
        f"Expected: {escrow.amount_expected} USDT"
    )
    await callback.message.answer(text, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


async def request_release(callback: CallbackQuery, session_factory, settings, redis: Redis) -> None:
    escrow_id = uuid.UUID(callback.data.split(":", 1)[1])
    confirm_key = f"release_confirm:{callback.from_user.id}:{escrow_id}"
    if not await redis.get(confirm_key):
        await redis.set(confirm_key, "1", ex=120)
        await callback.message.answer("⚠️ Release is irreversible. Tap release again to confirm.")
        await callback.answer()
        return
    async with session_factory() as session:
        async with session.begin():
            escrow = await get_escrow_for_update(session, escrow_id)
            if callback.from_user.id != escrow.buyer_tg_id:
                await callback.answer("Only buyer can release.", show_alert=True)
                return
            validate_transition(escrow.status, EscrowStatus.RELEASE_REQUESTED)
            await transition_escrow(session, escrow, EscrowStatus.RELEASE_REQUESTED)

    if escrow.net_amount <= to_decimal(settings.auto_payout_max):
        await approve_and_send_payout(callback, session_factory, settings, escrow_id)
        return
    await callback.message.answer("Release request submitted for admin approval.")
    await callback.answer()


async def approve_and_send_payout(
    callback: CallbackQuery | None,
    session_factory,
    settings,
    escrow_id: uuid.UUID,
) -> None:
    async with session_factory() as session:
        async with session.begin():
            escrow = await get_escrow_for_update(session, escrow_id)
            if escrow.payout_tx_hash:
                if callback:
                    await callback.answer("Payout already sent.", show_alert=True)
                return
            await transition_escrow(session, escrow, EscrowStatus.RELEASE_APPROVED)

    timestamp = int(datetime.utcnow().timestamp())
    nonce = generate_nonce()
    signed = SignedRequest(
        escrow_id=str(escrow_id),
        chain=escrow.chain.value,
        payout_address=escrow.payout_address or "",
        amount=format_amount(escrow.net_amount),
        timestamp=timestamp,
        nonce=nonce,
        signature="",
    )
    signature = sign_hmac(settings.signer_hmac_secret, signed.message())
    payload = signed.__dict__ | {"signature": signature}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"{settings.signer_base_url}/payout", json=payload)
        response.raise_for_status()
        tx_data = response.json()
    if callback:
        seller_tx = tx_data.get("seller_tx_hash")
        fee_tx = tx_data.get("fee_tx_hash")
        await callback.message.answer(
            "Payout submitted.\n"
            f"Seller tx: {seller_tx}\n"
            f"Fee tx: {fee_tx}\n"
            "Status will update after confirmations."
        )
        await callback.answer()


async def open_dispute(callback: CallbackQuery, session_factory) -> None:
    escrow_id = uuid.UUID(callback.data.split(":", 1)[1])
    async with session_factory() as session:
        async with session.begin():
            escrow = await get_escrow_for_update(session, escrow_id)
            if escrow.status in {EscrowStatus.CANCELLED, EscrowStatus.COMPLETED}:
                await callback.answer("Cannot dispute completed/cancelled.", show_alert=True)
                return
            await transition_escrow(session, escrow, EscrowStatus.DISPUTED)
            session.add(
                Dispute(
                    escrow_id=escrow.id,
                    opened_by_tg_id=callback.from_user.id,
                    reason="Opened via bot",
                    status=DisputeStatus.OPEN,
                    created_at=datetime.utcnow(),
                    resolved_at=None,
                )
            )
    await callback.message.answer("Dispute opened. Our team will review.")
    await callback.answer()


async def prompt_reviews(callback: CallbackQuery | None, session_factory, settings, escrow_id: uuid.UUID) -> None:
    async with session_factory() as session:
        result = await session.execute(select(Escrow).where(Escrow.id == escrow_id))
        escrow = result.scalar_one()
    if escrow.status != EscrowStatus.COMPLETED:
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Leave Review", callback_data=f"review:{escrow.id}")]]
    )
    if callback:
        bot = callback.message.bot
        await bot.send_message(escrow.buyer_tg_id, "Leave a review for this escrow.", reply_markup=keyboard)
        await bot.send_message(escrow.seller_tg_id, "Leave a review for this escrow.", reply_markup=keyboard)


async def start_review(callback: CallbackQuery, redis: Redis, session_factory, settings) -> None:
    escrow_id = uuid.UUID(callback.data.split(":", 1)[1])
    async with session_factory() as session:
        result = await session.execute(select(Escrow).where(Escrow.id == escrow_id))
        escrow = result.scalar_one()
    if escrow.status != EscrowStatus.COMPLETED:
        await callback.answer("Reviews available after completion.", show_alert=True)
        return
    await redis.set(f"review:{callback.from_user.id}", str(escrow_id), ex=600)
    await callback.message.answer("Send rating (1-5) and comment, e.g. `5 Fast and smooth`.")
    await callback.answer()


def contains_profanity(text: str) -> bool:
    bad_words = {"spam", "scam"}
    lowered = text.lower()
    return any(word in lowered for word in bad_words)


async def handle_review_message(message: Message, session_factory, redis: Redis, settings) -> None:
    escrow_id = await redis.get(f"review:{message.from_user.id}")
    if not escrow_id:
        return
    await redis.delete(f"review:{message.from_user.id}")
    if not message.text:
        await message.answer("Review must be text.")
        return
    if re.search(r"https?://", message.text):
        await message.answer("Links are not allowed in reviews.")
        return
    if contains_profanity(message.text):
        await message.answer("Please remove inappropriate language.")
        return
    parts = message.text.split(" ", 1)
    if len(parts) != 2:
        await message.answer("Format: <rating> <comment>")
        return
    try:
        rating = int(parts[0])
    except ValueError:
        await message.answer("Rating must be a number 1-5.")
        return
    if rating < 1 or rating > 5:
        await message.answer("Rating must be 1-5.")
        return
    comment = parts[1].strip()
    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(select(Escrow).where(Escrow.id == uuid.UUID(escrow_id)))
            escrow = result.scalar_one()
            reviewer = message.from_user.id
            counterparty = escrow.seller_tg_id if reviewer == escrow.buyer_tg_id else escrow.buyer_tg_id
            from trustora.models import Review

            existing = await session.execute(
                select(Review).where(Review.escrow_id == escrow.id, Review.reviewer_tg_id == reviewer)
            )
            if existing.scalar_one_or_none():
                await message.answer("You already reviewed this escrow.")
                return
            review = Review(
                escrow_id=escrow.id,
                reviewer_tg_id=reviewer,
                counterparty_tg_id=counterparty,
                rating=rating,
                comment=comment,
                posted_channel_msg_id=None,
                created_at=datetime.utcnow(),
            )
            session.add(review)
    reviewer_hash = user_public_hash(message.from_user.id, settings.public_hash_salt)
    post = build_review_post(
        escrow.room_code,
        escrow.chain.value,
        escrow.amount_expected,
        reviewer_hash,
        rating,
        comment,
    )
    if settings.reviews_channel_id:
        msg = await message.bot.send_message(settings.reviews_channel_id, post)
        async with session_factory() as session:
            async with session.begin():
                from trustora.models import Review

                result = await session.execute(
                    select(Review).where(
                        Review.escrow_id == uuid.UUID(escrow_id),
                        Review.reviewer_tg_id == message.from_user.id,
                    )
                )
                review = result.scalar_one()
                review.posted_channel_msg_id = msg.message_id
                session.add(review)
    await message.answer("Review submitted. Thank you!")


async def start_chat(callback: CallbackQuery, redis: Redis) -> None:
    escrow_id = callback.data.split(":", 1)[1]
    await redis.set(f"chat:{callback.from_user.id}", escrow_id, ex=600)
    await callback.message.answer("Chat started. Send a message to relay.")
    await callback.answer()


async def relay_message(message: Message, session_factory, redis: Redis) -> None:
    chat_key = f"chat:{message.from_user.id}"
    escrow_id = await redis.get(chat_key)
    if not escrow_id:
        return
    async with session_factory() as session:
        result = await session.execute(select(Escrow).where(Escrow.id == uuid.UUID(escrow_id)))
        escrow = result.scalar_one()
    if escrow.chat_frozen:
        await message.answer("Chat is frozen for this dispute.")
        return
    rate_key = f"chat_rate:{escrow_id}:{message.from_user.id}"
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, 60)
    if count > 10:
        await message.answer("Rate limit exceeded. Try again later.")
        return
    role = MessageRole.BUYER if message.from_user.id == escrow.buyer_tg_id else MessageRole.SELLER
    prefix = f"💬 {escrow.room_code} | {'Buyer' if role == MessageRole.BUYER else 'Seller'}:"
    target_id = escrow.seller_tg_id if role == MessageRole.BUYER else escrow.buyer_tg_id

    if message.photo:
        if escrow.status != EscrowStatus.DISPUTED:
            await message.answer("Images are allowed only when a dispute is opened.")
            return
        photo = message.photo[-1]
        if photo.file_size and photo.file_size > 5 * 1024 * 1024:
            await message.answer("Image too large. Max 5MB.")
            return
        if message.caption and re.search(r"https?://", message.caption):
            await message.answer("Links are not allowed in evidence.")
            return
        await message.bot.send_photo(
            target_id,
            photo.file_id,
            caption=f"{prefix} Evidence image",
        )
        body = photo.file_id
        msg_type = MessageType.IMAGE
    else:
        if message.text is None:
            await message.answer("Only text is allowed unless dispute is opened.")
            return
        if re.search(r"https?://", message.text):
            await message.answer("Links are not allowed in chat.")
            return
        await message.bot.send_message(target_id, f"{prefix} {message.text}")
        body = message.text
        msg_type = MessageType.TEXT

    async with session_factory() as session:
        async with session.begin():
            session.add(
                EscrowMessage(
                    escrow_id=escrow.id,
                    sender_tg_id=message.from_user.id,
                    role=role,
                    type=msg_type,
                    body_or_file_id=body,
                    created_at=datetime.utcnow(),
                )
            )


def is_admin(settings, tg_id: int) -> bool:
    admin_ids = {int(x) for x in settings.admin_ids.split(",") if x}
    return tg_id in admin_ids


async def admin_entry(message: Message, redis: Redis, settings) -> None:
    if message.text != settings.admin_secret_command or not is_admin(settings, message.from_user.id):
        await message.answer("Unauthorized.")
        return
    await redis.set(f"admin:{message.from_user.id}", "1", ex=600)
    await message.answer("Admin session active for 10 minutes.", reply_markup=admin_menu())


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Approvals", callback_data="admin:approvals")],
            [InlineKeyboardButton(text="⚖️ Disputes", callback_data="admin:disputes")],
            [InlineKeyboardButton(text="🔍 Search", callback_data="admin:search")],
            [InlineKeyboardButton(text="🚫 Block/Unblock", callback_data="admin:block")],
            [InlineKeyboardButton(text="💸 Fee Config", callback_data="admin:fees")],
            [InlineKeyboardButton(text="📣 Broadcast", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="📊 Analytics", callback_data="admin:analytics")],
            [InlineKeyboardButton(text="🩺 Health", callback_data="admin:health")],
            [InlineKeyboardButton(text="🛑 Kill Switch", callback_data="admin:kill")],
            [InlineKeyboardButton(text="🧾 Audit Logs", callback_data="admin:audit")],
        ]
    )


async def admin_guard(callback: CallbackQuery, redis: Redis, settings) -> bool:
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return False
    active = await redis.get(f"admin:{callback.from_user.id}")
    if not active:
        await callback.answer("Admin session expired.", show_alert=True)
        return False
    return True


async def admin_approvals(callback: CallbackQuery, session_factory, redis: Redis, settings) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    async with session_factory() as session:
        result = await session.execute(
            select(Escrow).where(Escrow.status == EscrowStatus.RELEASE_REQUESTED)
        )
        escrows = result.scalars().all()
    if not escrows:
        await callback.message.answer("No approvals pending.")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Approve {e.room_code}", callback_data=f"admin:approve:{e.id}")]
            for e in escrows
        ]
    )
    await callback.message.answer("Approvals queue:", reply_markup=keyboard)
    await callback.answer()


async def admin_approve(callback: CallbackQuery, session_factory, redis: Redis, settings) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    escrow_id = uuid.UUID(callback.data.split(":", 2)[2])
    confirm_key = f"confirm:approve:{callback.from_user.id}:{escrow_id}"
    if not await redis.get(confirm_key):
        await redis.set(confirm_key, "1", ex=120)
        await callback.message.answer("Tap approve again to confirm.")
        await callback.answer()
        return
    await approve_and_send_payout(callback, session_factory, settings, escrow_id)


async def admin_disputes(callback: CallbackQuery, session_factory, redis: Redis, settings) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    async with session_factory() as session:
        result = await session.execute(select(Dispute).where(Dispute.status == DisputeStatus.OPEN))
        disputes = result.scalars().all()
    if not disputes:
        await callback.message.answer("No disputes open.")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Toggle Chat {d.escrow_id}", callback_data=f"admin:freeze:{d.escrow_id}"
                )
            ]
            for d in disputes
        ]
    )
    lines = [f"Dispute {d.id} | Escrow {d.escrow_id}" for d in disputes]
    await callback.message.answer("Open disputes:\n" + "\n".join(lines), reply_markup=keyboard)
    await callback.answer()


async def admin_freeze(callback: CallbackQuery, session_factory, redis: Redis, settings) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    escrow_id = uuid.UUID(callback.data.split(":", 2)[2])
    confirm_key = f"confirm:freeze:{callback.from_user.id}:{escrow_id}"
    if not await redis.get(confirm_key):
        await redis.set(confirm_key, "1", ex=120)
        await callback.message.answer("Tap again to confirm chat freeze toggle.")
        await callback.answer()
        return
    async with session_factory() as session:
        async with session.begin():
            escrow = await get_escrow_for_update(session, escrow_id)
            escrow.chat_frozen = not escrow.chat_frozen
            session.add(escrow)
    await callback.message.answer("Chat freeze toggled.")
    await callback.answer()


async def admin_health(callback: CallbackQuery, redis: Redis, settings) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    await callback.message.answer("System health: OK")
    await callback.answer()


async def admin_kill_switch(callback: CallbackQuery, session_factory, redis: Redis, settings) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    confirm_key = f"confirm:kill:{callback.from_user.id}"
    if not await redis.get(confirm_key):
        await redis.set(confirm_key, "1", ex=120)
        await callback.message.answer("Tap kill switch again to confirm.")
        await callback.answer()
        return
    async with session_factory() as session:
        async with session.begin():
            config = await get_config(session)
            await update_config(
                session,
                callback.from_user.id,
                {"pause_payouts": not config.json.get("pause_payouts", False)},
            )
    await callback.message.answer("Kill switch toggled.")
    await callback.answer()


async def admin_set_action(callback: CallbackQuery, redis: Redis, settings, action: str, prompt: str) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    await redis.set(f"admin_action:{callback.from_user.id}", action, ex=600)
    await callback.message.answer(prompt)
    await callback.answer()


async def admin_search(callback: CallbackQuery, redis: Redis, settings) -> None:
    await admin_set_action(callback, redis, settings, "search", "Send room code or escrow ID.")


async def admin_block(callback: CallbackQuery, redis: Redis, settings) -> None:
    await admin_set_action(callback, redis, settings, "block", "Send user ID to toggle block.")


async def admin_fees(callback: CallbackQuery, redis: Redis, settings) -> None:
    await admin_set_action(
        callback,
        redis,
        settings,
        "fees",
        "Send fee config as flat,percent,threshold (e.g. 5,0.02,100).",
    )


async def admin_broadcast(callback: CallbackQuery, redis: Redis, settings) -> None:
    await admin_set_action(callback, redis, settings, "broadcast", "Send broadcast message.")


async def admin_analytics(callback: CallbackQuery, session_factory, redis: Redis, settings) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    async with session_factory() as session:
        users = (await session.execute(select(User))).scalars().all()
        escrows = (await session.execute(select(Escrow))).scalars().all()
    await callback.message.answer(
        f"Users: {len(users)}\n"
        f"Deals: {len(escrows)}\n"
        f"Completed: {len([e for e in escrows if e.status == EscrowStatus.COMPLETED])}"
    )
    await callback.answer()


async def admin_audit(callback: CallbackQuery, session_factory, redis: Redis, settings) -> None:
    if not await admin_guard(callback, redis, settings):
        return
    from trustora.models import AuditLog

    async with session_factory() as session:
        result = await session.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(5))
        logs = result.scalars().all()
    if not logs:
        await callback.message.answer("No audit logs yet.")
        await callback.answer()
        return
    lines = [f"{log.created_at} | {log.action}" for log in logs]
    await callback.message.answer("Recent audit logs:\n" + "\n".join(lines))
    await callback.answer()


async def admin_action_message(message: Message, session_factory, redis: Redis, settings) -> None:
    action = await redis.get(f"admin_action:{message.from_user.id}")
    if not action or not is_admin(settings, message.from_user.id):
        return
    await redis.delete(f"admin_action:{message.from_user.id}")
    if action == "search":
        await handle_admin_search(message, session_factory)
    elif action == "block":
        await handle_admin_block(message, session_factory, redis)
    elif action == "fees":
        await handle_admin_fees(message, session_factory, redis)
    elif action == "broadcast":
        await handle_admin_broadcast(message, session_factory, redis)


async def handle_admin_search(message: Message, session_factory) -> None:
    query = (message.text or "").strip()
    async with session_factory() as session:
        escrow = None
        if query:
            try:
                escrow_id = uuid.UUID(query)
                result = await session.execute(select(Escrow).where(Escrow.id == escrow_id))
                escrow = result.scalar_one_or_none()
            except ValueError:
                if query.isdigit():
                    result = await session.execute(
                        select(Escrow).where(
                            (Escrow.buyer_tg_id == int(query)) | (Escrow.seller_tg_id == int(query))
                        )
                    )
                    escrow = result.scalars().first()
                else:
                    result = await session.execute(
                        select(Escrow).where(
                            (Escrow.room_code == query)
                            | (Escrow.deposit_tx_hash == query)
                            | (Escrow.payout_tx_hash == query)
                        )
                    )
                    escrow = result.scalar_one_or_none()
        if not escrow:
            await message.answer("No escrow found.")
            return
        await message.answer(
            f"Escrow {escrow.room_code} | Status: {escrow.status.value} | Amount: {escrow.amount_expected}"
        )


async def handle_admin_block(message: Message, session_factory, redis: Redis) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Enter numeric user ID.")
        return
    tg_id = int(message.text)
    confirm_key = f"confirm:block:{message.from_user.id}:{tg_id}"
    if not await redis.get(confirm_key):
        await redis.set(confirm_key, "1", ex=120)
        await message.answer("Send the same user ID again to confirm.")
        return
    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            user = result.scalar_one_or_none()
            if not user:
                await message.answer("User not found.")
                return
            user.is_blocked = not user.is_blocked
            session.add(user)
    await message.answer(f"User {tg_id} block status toggled.")


async def handle_admin_fees(message: Message, session_factory, redis: Redis) -> None:
    if not message.text:
        return
    parts = [p.strip() for p in message.text.split(",")]
    if len(parts) != 3:
        await message.answer("Format: flat,percent,threshold")
        return
    try:
        flat_fee = float(parts[0])
        percent_fee = float(parts[1])
        threshold = float(parts[2])
    except ValueError:
        await message.answer("Invalid numbers.")
        return
    confirm_key = f"confirm:fees:{message.from_user.id}:{flat_fee}:{percent_fee}:{threshold}"
    if not await redis.get(confirm_key):
        await redis.set(confirm_key, "1", ex=120)
        await message.answer("Send same fee config again to confirm.")
        return
    async with session_factory() as session:
        async with session.begin():
            await update_config(
                session,
                message.from_user.id,
                {
                    "fee_flat": flat_fee,
                    "fee_percent": percent_fee,
                    "fee_threshold": threshold,
                },
            )
    await message.answer("Fee config updated for new escrows.")


async def handle_admin_broadcast(message: Message, session_factory, redis: Redis) -> None:
    text = message.text or ""
    if not text:
        return
    confirm_key = f"confirm:broadcast:{message.from_user.id}"
    if not await redis.get(confirm_key):
        await redis.set(confirm_key, "1", ex=120)
        await message.answer("Send the broadcast again to confirm.")
        return
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.broadcast_opt_in.is_(True)))
        users = result.scalars().all()
    for user in users:
        try:
            await message.bot.send_message(user.tg_id, text)
        except Exception:
            continue
    await message.answer("Broadcast sent to opt-in users.")

async def create_app() -> None:
    settings = load_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    storage = RedisStorage.from_url(settings.redis_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    bot = Bot(settings.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=storage)

    dp.message.register(handle_start, F.text == "/start")
    dp.message.register(new_escrow, F.text == "➕ New Escrow")
    dp.message.register(list_deals, F.text == "🧾 My Deals")
    dp.message.register(show_fees, F.text == "💸 Fees")
    dp.message.register(how_it_works, F.text == "📘 How It Works")
    dp.message.register(support, F.text == "🆘 Support")
    dp.message.register(admin_entry, F.text == settings.admin_secret_command)

    dp.callback_query.register(show_room, F.data.startswith("room:"))
    dp.callback_query.register(show_summary, F.data.startswith("summary:"))
    dp.callback_query.register(show_deposit, F.data.startswith("deposit:"))
    dp.callback_query.register(request_release, F.data.startswith("release:"))
    dp.callback_query.register(open_dispute, F.data.startswith("dispute:"))
    dp.callback_query.register(start_chat, F.data.startswith("chat:"))
    dp.callback_query.register(start_review, F.data.startswith("review:"))
    dp.callback_query.register(lambda c: c.message.answer("Support: @trustora_support"), F.data == "support")
    dp.callback_query.register(admin_approvals, F.data == "admin:approvals")
    dp.callback_query.register(admin_disputes, F.data == "admin:disputes")
    dp.callback_query.register(admin_search, F.data == "admin:search")
    dp.callback_query.register(admin_block, F.data == "admin:block")
    dp.callback_query.register(admin_fees, F.data == "admin:fees")
    dp.callback_query.register(admin_broadcast, F.data == "admin:broadcast")
    dp.callback_query.register(admin_analytics, F.data == "admin:analytics")
    dp.callback_query.register(admin_health, F.data == "admin:health")
    dp.callback_query.register(admin_kill_switch, F.data == "admin:kill")
    dp.callback_query.register(admin_audit, F.data == "admin:audit")
    dp.callback_query.register(admin_approve, F.data.startswith("admin:approve:"))
    dp.callback_query.register(admin_freeze, F.data.startswith("admin:freeze:"))

    dp.message.register(set_seller_id, EscrowFlow.seller_id)
    dp.message.register(set_amount, EscrowFlow.amount)
    dp.message.register(set_chain, EscrowFlow.chain)
    dp.message.register(set_payout_address, EscrowFlow.payout_address)
    dp.message.register(confirm_network, EscrowFlow.confirm_network)
    dp.message.register(relay_message)
    dp.message.register(admin_action_message)
    dp.message.register(handle_review_message)

    dp.workflow_data.update(session_factory=session_factory, settings=settings, redis=redis)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(create_app())
