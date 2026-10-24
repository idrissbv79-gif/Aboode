# -*- coding: utf-8 -*-
"""
بوت Messenger للمراسلة المجهولة
- يعمل عبر Facebook Graph API + Polling مثل الملف المرفق.
- لا يستخدم Webhook.
- لا يحفظ المحادثات أو الصور أو الرموز على القرص.
- جميع الحالات والرسائل والرموز موجودة في الذاكرة فقط وتضيع عند إعادة التشغيل.

التثبيت:
التشغيل:
    python anonymous_messenger_bot.py

مهم:
    ضع Page Access Token الحقيقي في PAGE_ACCESS_TOKEN أدناه.
    لا تضع التوكن في مستودع عام ولا تشاركه مع أي شخص.
"""

import random
import os
import threading
import time
import json
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ============================================================================
# إعدادات البوت — ضع التوكن هنا مباشرة كما طلبت
# ============================================================================

PAGE_ACCESS_TOKEN = "ضع_توكن_الصفحة_هنا"
ADMIN_CODE = "idriss888"
GRAPH_API_VERSION = "v23.0"
POLL_SECONDS = 3
REQUEST_TIMEOUT = 20
INVITE_TTL_MINUTES = 20
MAX_WORKERS = 16
CONVERSATIONS_PAGE_SIZE = 100

# لا يتم إنشاء أي ملف قاعدة بيانات أو ملف جلسات.
# البيانات التالية مؤقتة وتختفي عند إيقاف البرنامج.

# ============================================================================
# حالة الذاكرة فقط
# ============================================================================

PAGE_ID: Optional[str] = None
polling_thread: Optional[threading.Thread] = None
polling_start_lock = threading.Lock()
polling_started = False

state_lock = threading.RLock()

# user_id -> {status, partner, menu}
users: Dict[str, Dict[str, Any]] = {}
user_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

# waiting users يبحثون عن شخص عشوائي
waiting_users: deque[str] = deque()

# invite_code -> {owner, expires_at, used}
invite_codes: Dict[str, Dict[str, Any]] = {}

# user_id -> آخر معرف رسالة تمت معالجتها أو مجموعة الرسائل المعالجة
processed_message_ids: set[str] = set()
processed_order: deque[str] = deque()
MAX_PROCESSED_IDS = 10000

# conversation_id -> آخر وقت فحص اختياري لمنع تكرار القراءة
last_seen_by_conversation: Dict[str, str] = {}
admin_ids: set[str] = set()
bot_started_at = now_utc() if "now_utc" in globals() else datetime.now(timezone.utc)
stats = {
    "messages_received": 0,
    "messages_relayed": 0,
    "attachments_relayed": 0,
    "pairs_started": 0,
    "chats_ended": 0,
    "broadcasts": 0,
}


# ============================================================================
# أدوات عامة
# ============================================================================


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def api_url(path: str) -> str:
    return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{path}"


def http_json(url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = None
    headers = {"User-Agent": "AnonymousMessengerPollingBot/1.0"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Graph HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def graph_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(params or {})
    params["access_token"] = PAGE_ACCESS_TOKEN
    url = f"{api_url(path)}?{urllib.parse.urlencode(params)}"
    return http_json(url)


def graph_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{api_url(path)}?{urllib.parse.urlencode({'access_token': PAGE_ACCESS_TOKEN})}"
    return http_json(url, method="POST", payload=payload)


def get_page_id() -> str:
    global PAGE_ID
    if PAGE_ID:
        return PAGE_ID
    data = graph_get("me", {"fields": "id"})
    PAGE_ID = str(data["id"])
    return PAGE_ID


def send_text(user_id: str, text: str) -> bool:
    try:
        graph_post(
            "me/messages",
            {"recipient": {"id": user_id}, "message": {"text": text}},
        )
        return True
    except Exception as exc:
        print(f"[send_text] {user_id}: {exc}")
        return False


def send_action(user_id: str, action: str) -> bool:
    try:
        graph_post(
            "me/messages",
            {"recipient": {"id": user_id}, "sender_action": action},
        )
        return True
    except Exception as exc:
        print(f"[send_action] {user_id}: {exc}")
        return False


def send_attachment(user_id: str, attachment_type: str, url: str) -> bool:
    """إعادة إرسال مرفق عبر رابط Meta المؤقت دون حفظه محليًا."""
    if attachment_type not in {"image", "audio", "video", "file"}:
        return send_text(user_id, "⚠️ هذا النوع من المرفقات غير مدعوم من Messenger.")
    try:
        graph_post(
            "me/messages",
            {
                "recipient": {"id": user_id},
                "message": {
                    "attachment": {
                        "type": attachment_type,
                        "payload": {"url": url, "is_reusable": False},
                    }
                },
            },
        )
        return True
    except Exception as exc:
        print(f"[send_attachment] {user_id}: {exc}")
        return False


def mark_processed(message_id: str) -> bool:
    with state_lock:
        if message_id in processed_message_ids:
            return False
        processed_message_ids.add(message_id)
        processed_order.append(message_id)
        while len(processed_order) > MAX_PROCESSED_IDS:
            old = processed_order.popleft()
            processed_message_ids.discard(old)
        return True


def get_user(user_id: str) -> Dict[str, Any]:
    with state_lock:
        return users.setdefault(user_id, {"status": "idle", "partner": None})


def set_pair(user_a: str, user_b: str) -> None:
    with state_lock:
        users[user_a] = {"status": "chatting", "partner": user_b}
        users[user_b] = {"status": "chatting", "partner": user_a}


def clear_pair(user_id: str) -> Optional[str]:
    with state_lock:
        partner = users.get(user_id, {}).get("partner")
        users[user_id] = {"status": "idle", "partner": None}
        if partner:
            users[partner] = {"status": "idle", "partner": None}
        return partner


# ============================================================================
# القائمة، الانتظار، ورموز الدعوة
# ============================================================================

MENU = (
    "📌 القائمة الرئيسية\n\n"
    "1️⃣ البحث عن شخص عشوائي\n"
    "2️⃣ إنشاء كود دعوة صالح لمدة 20 دقيقة\n"
    "3️⃣ إدخال كود دعوة\n"
    "5️⃣ لوحة الإدارة (للمشرفين فقط)\n\n"
    "أرسل رقم الخيار. أثناء المحادثة أرسل 0 لإنهائها."
)

ADMIN_MENU = (
    "🛠️ لوحة الإدارة\n\n"
    "1️⃣ معلومات وإحصائيات البوت\n"
    "2️⃣ إذاعة رسالة لكل المستخدمين\n"
    "3️⃣ عرض المحادثات النشطة\n"
    "4️⃣ عرض قائمة المنتظرين\n"
    "5️⃣ العودة للقائمة الرئيسية\n\n"
    "أرسل رقم الخيار."
)


def show_menu(user_id: str) -> None:
    send_text(user_id, MENU)


def show_admin_menu(user_id: str) -> None:
    if user_id not in admin_ids:
        send_text(user_id, "❌ ليس لديك صلاحية الدخول إلى لوحة الإدارة.")
        show_menu(user_id)
        return
    send_text(user_id, ADMIN_MENU)


def format_uptime() -> str:
    seconds = max(0, int((datetime.now(timezone.utc) - bot_started_at).total_seconds()))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{days} يوم، {hours} ساعة، {minutes} دقيقة، {seconds} ثانية"


def admin_stats_text() -> str:
    with state_lock:
        total = len(users)
        active = sum(1 for item in users.values() if item.get("status") == "chatting")
        waiting = sum(1 for item in users.values() if item.get("status") == "waiting")
        codes = len(invite_codes)
        admins = len(admin_ids)
        snapshot = dict(stats)
    return (
        "📊 معلومات البوت\n"
        "━━━━━━━━━━━━━━\n"
        f"👥 المستخدمون المعروفون: {total}\n"
        f"💬 المحادثات النشطة: {active // 2}\n"
        f"🔎 المنتظرون: {waiting}\n"
        f"🔢 رموز الدعوة الحالية: {codes}\n"
        f"🛡️ المشرفون الحاليون: {admins}\n"
        f"📨 الرسائل المستقبلة: {snapshot['messages_received']}\n"
        f"🔁 الرسائل المنقولة: {snapshot['messages_relayed']}\n"
        f"📎 المرفقات المنقولة: {snapshot['attachments_relayed']}\n"
        f"✅ المحادثات التي بدأت: {snapshot['pairs_started']}\n"
        f"🚪 المحادثات المنتهية: {snapshot['chats_ended']}\n"
        f"📢 الإذاعات: {snapshot['broadcasts']}\n"
        f"⏱️ مدة التشغيل: {format_uptime()}\n"
        "━━━━━━━━━━━━━━\n"
        "⚠️ الإحصائيات مؤقتة وتختفي عند إعادة التشغيل."
    )


def admin_active_chats_text() -> str:
    with state_lock:
        pairs = []
        seen = set()
        for uid, item in users.items():
            partner = item.get("partner")
            if item.get("status") == "chatting" and partner and uid not in seen:
                pairs.append((uid, partner))
                seen.add(uid)
                seen.add(partner)
    if not pairs:
        return "💬 لا توجد محادثات نشطة حاليًا."
    lines = [f"💬 المحادثات النشطة: {len(pairs)}"]
    lines.extend(f"{i}. مستخدمان متصلان" for i, _ in enumerate(pairs, 1))
    return "\n".join(lines)


def admin_waiting_text() -> str:
    with state_lock:
        count = sum(1 for item in users.values() if item.get("status") == "waiting")
    return f"🔎 عدد المستخدمين المنتظرين: {count}\nلا يتم عرض هوياتهم حفاظًا على الخصوصية."


def broadcast_to_users(admin_id: str, text: str) -> None:
    with state_lock:
        recipients = [uid for uid in users if uid != admin_id]
    if not recipients:
        send_text(admin_id, "📭 لا يوجد مستخدمون معروفون للإذاعة.")
        show_admin_menu(admin_id)
        return

    def send_one(uid: str) -> bool:
        return send_text(uid, f"📢 رسالة من إدارة البوت:\n\n{text}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="broadcast") as pool:
        results = list(pool.map(send_one, recipients))
    sent = sum(1 for result in results if result)
    failed = len(results) - sent
    with state_lock:
        stats["broadcasts"] += 1
    send_text(admin_id, f"✅ انتهت الإذاعة.\nتم الإرسال: {sent}\nفشل: {failed}")
    show_admin_menu(admin_id)


def cleanup_expired_codes() -> None:
    current = now_utc()
    with state_lock:
        expired = [
            code for code, item in invite_codes.items()
            if item["expires_at"] <= current or item.get("used")
        ]
        for code in expired:
            invite_codes.pop(code, None)


def make_invite_code() -> str:
    cleanup_expired_codes()
    with state_lock:
        for _ in range(100):
            code = f"{random.randint(0, 99_999_999):08d}"
            if code not in invite_codes:
                return code
    raise RuntimeError("تعذر إنشاء رمز جديد")


def create_invite(user_id: str) -> None:
    old_codes = []
    with state_lock:
        old_codes = [c for c, item in invite_codes.items() if item["owner"] == user_id]
        for code in old_codes:
            invite_codes.pop(code, None)
        code = make_invite_code()
        invite_codes[code] = {
            "owner": user_id,
            "expires_at": now_utc() + timedelta(minutes=INVITE_TTL_MINUTES),
            "used": False,
        }
    send_text(
        user_id,
        f"✅ كود الدعوة الخاص بك: {code}\n"
        f"⏳ صالح لمدة {INVITE_TTL_MINUTES} دقيقة فقط.\n"
        "أرسل الكود إلى الشخص الآخر، ثم يختار الخيار 3.\n"
        "⚠️ الكود لا يُحفظ بعد إيقاف البوت.",
    )


def start_random_search(user_id: str) -> None:
    partner_to_remove = clear_pair(user_id)
    if partner_to_remove:
        send_text(partner_to_remove, "ℹ️ الطرف الآخر أنهى المحادثة.")

    with state_lock:
        if user_id in waiting_users:
            send_text(user_id, "⏳ أنت موجود بالفعل في قائمة البحث.")
            return
        while waiting_users:
            candidate = waiting_users.popleft()
            if candidate == user_id:
                continue
            if users.get(candidate, {}).get("status") == "waiting":
                set_pair(user_id, candidate)
                stats["pairs_started"] += 1
                send_text(user_id, "✅ تم العثور على شخص. يمكنكما التحدث الآن.")
                send_text(candidate, "✅ تم العثور على شخص. يمكنكما التحدث الآن.")
                return
        users[user_id] = {"status": "waiting", "partner": None}
        waiting_users.append(user_id)
    send_text(user_id, "🔎 جاري البحث عن شخص عشوائي...\nأرسل 0 للإلغاء.")


def cancel_waiting(user_id: str) -> None:
    with state_lock:
        users[user_id] = {"status": "idle", "partner": None}
        try:
            waiting_users.remove(user_id)
        except ValueError:
            pass
    send_text(user_id, "✅ تم إلغاء البحث.")
    show_menu(user_id)


def accept_invite(user_id: str, code: str) -> None:
    code = code.strip()
    if not code.isdigit() or len(code) != 8:
        send_text(user_id, "❌ أرسل كودًا مكونًا من 8 أرقام فقط.")
        return

    cleanup_expired_codes()
    with state_lock:
        item = invite_codes.get(code)
        if not item:
            send_text(user_id, "❌ الكود غير موجود أو انتهت صلاحيته.")
            return
        owner = item["owner"]
        if owner == user_id:
            send_text(user_id, "❌ لا يمكنك استخدام كودك مع نفسك.")
            return
        item["used"] = True
        invite_codes.pop(code, None)
        set_pair(owner, user_id)
        stats["pairs_started"] += 1

    send_text(owner, "✅ تم قبول كود الدعوة. بدأت المحادثة المجهولة.")
    send_text(user_id, "✅ تم الاتصال بصاحب الكود. بدأت المحادثة المجهولة.")


# ============================================================================
# نقل الرسائل والمرفقات
# ============================================================================


def extract_attachments(message: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    for attachment in message.get("attachments") or []:
        attachment_type = attachment.get("type")
        payload = attachment.get("payload") or {}
        url = payload.get("url")
        if attachment_type and url:
            yield attachment_type, url


def relay_message(sender_id: str, message: Dict[str, Any]) -> None:
    with state_lock:
        partner_id = users.get(sender_id, {}).get("partner")
        status = users.get(sender_id, {}).get("status")

    if status != "chatting" or not partner_id:
        show_menu(sender_id)
        return

    send_action(partner_id, "typing_on")

    text = (message.get("message") or "").strip()
    if text:
        send_text(partner_id, text)

    sent_attachment = False
    for attachment_type, url in extract_attachments(message):
        sent = send_attachment(partner_id, attachment_type, url)
        sent_attachment = sent or sent_attachment
        if sent:
            with state_lock:
                stats["attachments_relayed"] += 1

    if not text and not sent_attachment:
        send_text(partner_id, "⚠️ تم استلام رسالة، لكن Messenger لم يوفر محتواها القابل للنقل.")
    elif text:
        with state_lock:
            stats["messages_relayed"] += 1
    send_action(partner_id, "typing_off")


def end_chat(user_id: str) -> None:
    partner = clear_pair(user_id)
    with state_lock:
        stats["chats_ended"] += 1
    if partner:
        send_text(partner, "ℹ️ الطرف الآخر غادر المحادثة.")
        show_menu(partner)
    send_text(user_id, "✅ انتهت المحادثة.")
    show_menu(user_id)


def handle_message(sender_id: str, message: Dict[str, Any]) -> None:
    if not sender_id:
        return

    text = (message.get("message") or "").strip()
    user = get_user(sender_id)
    status = user.get("status")

    # إدخال الكود السري يمنح صلاحية مؤقتة داخل الذاكرة فقط.
    if text == ADMIN_CODE:
        with state_lock:
            admin_ids.add(sender_id)
            users[sender_id] = {"status": "admin_menu", "partner": None}
        send_text(sender_id, "✅ تم تفعيل صلاحية المشرف لهذه الجلسة.")
        show_admin_menu(sender_id)
        return

    if sender_id in admin_ids and status == "admin_broadcast":
        if text:
            users[sender_id]["status"] = "admin_menu"
            broadcast_to_users(sender_id, text)
        else:
            send_text(sender_id, "❌ اكتب نص الإذاعة أولًا.")
        return

    if sender_id in admin_ids and status == "admin_menu":
        if text == "1":
            send_text(sender_id, admin_stats_text())
            show_admin_menu(sender_id)
        elif text == "2":
            users[sender_id]["status"] = "admin_broadcast"
            send_text(sender_id, "📢 أرسل نص الرسالة التي تريد إذاعتها لكل المستخدمين، أو أرسل 0 للإلغاء.")
        elif text == "3":
            send_text(sender_id, admin_active_chats_text())
            show_admin_menu(sender_id)
        elif text == "4":
            send_text(sender_id, admin_waiting_text())
            show_admin_menu(sender_id)
        elif text == "5" or text == "0":
            users[sender_id]["status"] = "idle"
            show_menu(sender_id)
        else:
            send_text(sender_id, "❓ اختيار إداري غير صحيح.")
            show_admin_menu(sender_id)
        return

    if text == "0":
        if status == "waiting":
            cancel_waiting(sender_id)
        elif status == "chatting":
            end_chat(sender_id)
        else:
            show_menu(sender_id)
        return

    if status == "chatting":
        relay_message(sender_id, message)
        return

    if status == "waiting":
        if text in {"1", "بحث", "بحث عشوائي"}:
            send_text(sender_id, "⏳ ما زلت في قائمة البحث.")
        else:
            send_text(sender_id, "⏳ أنت في قائمة البحث. أرسل 0 للإلغاء.")
        return

    if status == "awaiting_code":
        accept_invite(sender_id, text)
        if users.get(sender_id, {}).get("status") != "chatting":
            users[sender_id]["status"] = "idle"
            show_menu(sender_id)
        return

    if text in {"", "ابدأ", "start", "menu", "القائمة"}:
        show_menu(sender_id)
    elif text == "1":
        start_random_search(sender_id)
    elif text == "2":
        create_invite(sender_id)
        show_menu(sender_id)
    elif text == "3":
        users[sender_id]["status"] = "awaiting_code"
        send_text(sender_id, "🔢 أرسل كود الدعوة المكون من 8 أرقام، أو أرسل 0 للإلغاء.")
    elif text == "5":
        if sender_id in admin_ids:
            users[sender_id]["status"] = "admin_menu"
            show_admin_menu(sender_id)
        else:
            send_text(sender_id, "❌ هذا الخيار مخصص للمشرفين فقط.")
            show_menu(sender_id)
    else:
        send_text(sender_id, "❓ اختيار غير صحيح.")
        show_menu(sender_id)


def safe_handle_message(sender_id: str, message: Dict[str, Any]) -> None:
    """يعالج رسائل المستخدم الواحد بالتسلسل لمنع تعارض تغيير حالته."""
    with user_locks[sender_id]:
        try:
            with state_lock:
                stats["messages_received"] += 1
            handle_message(sender_id, message)
        except Exception as exc:
            print(f"[user:{sender_id}] {exc}")


# ============================================================================
# Polling عبر Graph API
# ============================================================================


def iter_pages(first_page: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    page = first_page
    while True:
        for item in page.get("data", []):
            yield item
        next_url = (page.get("paging") or {}).get("next")
        if not next_url:
            break
        try:
            page = http_json(next_url)
        except Exception as exc:
            print(f"[paging] {exc}")
            break


def fetch_conversations() -> Iterable[Dict[str, Any]]:
    fields = (
        "messages.limit(20)"
        "{id,from,message,attachments,created_time}"
    )
    first = graph_get("me/conversations", {"fields": fields, "limit": CONVERSATIONS_PAGE_SIZE})
    return iter_pages(first)


def process_conversation(conversation: Dict[str, Any]) -> None:
    # أحدث 20 رسالة لكل محادثة؛ لا يتم تخزينها على القرص.
    conversation_id = conversation.get("id")
    messages = (conversation.get("messages") or {}).get("data") or []
    if not conversation_id or not messages:
        return

    # Graph قد يعيد الرسائل من الأحدث إلى الأقدم، لذلك نعالجها بالعكس.
    for message in reversed(messages):
        message_id = str(message.get("id") or "")
        sender = (message.get("from") or {}).get("id")
        if not message_id or not sender:
            continue
        # لا نعالج رسائل الصفحة نفسها مرة أخرى.
        if PAGE_ID and str(sender) == PAGE_ID:
            continue
        if mark_processed(message_id):
            safe_handle_message(str(sender), message)
    last_seen_by_conversation[conversation_id] = str(messages[0].get("id", ""))


def poll_once() -> None:
    conversations = list(fetch_conversations())
    if not conversations:
        return
    # العمال محدودون حتى لا نضغط Graph API أو جهاز التشغيل.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="conversation") as pool:
        list(pool.map(process_conversation, conversations))


def run() -> None:
    if not PAGE_ACCESS_TOKEN or PAGE_ACCESS_TOKEN == "ضع_توكن_الصفحة_هنا":
        raise SystemExit("ضع Page Access Token في المتغير PAGE_ACCESS_TOKEN أعلى الملف أولًا.")

    page_id = get_page_id()

    print("Anonymous Messenger bot started: Graph API + Polling")
    print(f"Page ID: {page_id}")
    print("No conversations, images, or invite codes are saved to disk.")

    while True:
        try:
            cleanup_expired_codes()
            poll_once()
        except (urllib.error.URLError, RuntimeError) as exc:
            print(f"[network] {exc}")
        except Exception as exc:
            print(f"[polling] {exc}")
        time.sleep(POLL_SECONDS)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        with state_lock:
            active = sum(1 for item in users.values() if item.get("status") == "chatting") // 2
            waiting = sum(1 for item in users.values() if item.get("status") == "waiting")
        if self.path.rstrip("/") == "/health":
            body = json.dumps({
                "status": "ok",
                "polling": polling_started,
                "active_chats": active,
                "waiting_users": waiting,
            }).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            body = b"Anonymous Messenger bot is running."
            content_type = "text/plain; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def start_polling_thread() -> None:
    global polling_thread, polling_started
    with polling_start_lock:
        if polling_started:
            return
        polling_thread = threading.Thread(target=run, name="facebook-polling", daemon=True)
        polling_thread.start()
        polling_started = True


if __name__ == "__main__":
    start_polling_thread()
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Web server listening on port {port}")
    server.serve_forever()
