import requests
import time
import hmac
import hashlib
import random
import string
import json
import base64
import gzip
import os

WORLD_URL = "https://api.eeventapp.io/minegram/world"
INIT_DATA = os.getenv("INIT_DATA")
SALT = os.getenv("SALT")

def generate_headers():
    request_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    timestamp = str(int(time.time() * 1000))

    msg = f"{INIT_DATA}.{request_id}.{timestamp}.{SALT}"

    signature = hmac.new(
        SALT.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "accept": "*/*",
        "content-type": "application/json",
        "x-esecure-initdata": INIT_DATA,
        "x-esecure-requestid": request_id,
        "x-esecure-timestamp": timestamp,
        "x-esecure-signature": signature,
        "Referer": "https://api.eeventapp.io/"
    }

def load_world():
    res = requests.post(
        WORLD_URL,
        headers=generate_headers(),
        json={}
    )

    text = res.text

    try:
        if text.startswith("{") or text.startswith("["):
            data = json.loads(text)
        else:
            data = json.loads(
                gzip.decompress(
                    base64.b64decode(text)
                ).decode()
            )
    except:
        print("Decode lỗi")
        return

    with open("map.json", "w", encoding="utf-8") as f:
        json.dump(data, f)

    print("Saved map.json")

# ==========================================
# GỌI HÀM LẤY MAP MỚI NHẤT TRƯỚC KHI ĐÀO
# ==========================================
print("🔄 Đang tải dữ liệu bản đồ mới nhất...")
load_world()
time.sleep(2)

# ==========================================
# 1. CẤU HÌNH TOOL AUTO V3 (CÓ GIỚI HẠN SỐ LƯỢNG)
# ==========================================
# CÁC MÃ BLOCK: 3 (Đá), 4 (Than), 5 (Sắt), 6 (Vàng), 8 (Kim Cương), 9 (Gỗ), 10 (Lá)
TARGET_BLOCK = 4

# --- TÍNH NĂNG MỚI THÊM ---
MAX_COLLECT = 0  # Số lượng block TỐI ĐA muốn đào (Để 0 nếu muốn đào sạch cả map)

EAT_THRESHOLD = 15  # Mức thể lực báo động cần ăn táo

AUTO_TRADE_COAL = False  # True/False tự động bán than

# BỘ NÃO CHỌN CÚP TỐI ƯU NHẤT
OPTIMAL_TOOLS = {
    10: "",               # Lá: Dùng tay không
    9:  "",               # Gỗ: Dùng tay không
    2:  "",               # Đất: Dùng tay không
    3:  "stone_pickaxe",   # Đá: Cúp gỗ  wood_pickaxe
    4:  "stone_pickaxe",   # Than: Cúp gỗ  wood_pickaxe
    5:  "stone_pickaxe",  # Sắt: Cúp đá  stone_pickaxe
    6:  "iron_pickaxe",   # Vàng: Cúp sắt  iron_pickaxe
    8:  "gold_pickaxe"    # Kim cương: Cúp vàng / Cúp kim cương  gold_pickaxe
}

API_BASE = "https://api.eeventapp.io/minegram"

# ==========================================
# 2. CÁC HÀM GIAO TIẾP MẠNG
# ==========================================
def send_api(endpoint, payload):
    try:
        res = requests.post(f"{API_BASE}/{endpoint}", headers=generate_headers(), json=payload, timeout=10)
        if res.status_code == 200:
            text = res.text
            if text.startswith('{') or text.startswith('['):
                return json.loads(text)
            return json.loads(gzip.decompress(base64.b64decode(text)).decode('utf-8'))
        return {"error": True, "status": res.status_code}
    except Exception as e:
        return {"error": True, "reason": str(e)}

# ==========================================
# TRADE THAN (AUTO BÁN)
# ==========================================
def trade_coal():
    trade_res = send_api("trader/proceed", {
        "traderId": "resource_trader",
        "offerIndex": 0
    })

    if trade_res.get("success"):
        print("💰 Đã trade 30 than với Resource Trader!")
    else:
        print("❌ Trade thất bại:", trade_res.get("reason", "unknown"))

# ==========================================
# 3. CÁC HÀM XỬ LÝ TÚI ĐỒ (INVENTORY)
# ==========================================
def has_item(inventory, item_id):
    if item_id == "": return True
    for item in inventory:
        if item and "Entity" in item and item["Entity"].get("ID") == item_id:
            return True
    return False

def get_item_index(inventory, item_id):
    for idx, item in enumerate(inventory):
        if item and "Entity" in item and item["Entity"].get("ID") == item_id:
            return idx
    return -1

# ==========================================
# 4. CHẠY VÒNG LẶP AUTO (MAIN)
# ==========================================
try:
    with open('map.json', 'r', encoding='utf-8') as f:
        world_data = json.load(f)["world"]

    target_positions = [i for i, block_id in enumerate(world_data) if block_id == TARGET_BLOCK]

    stone_positions = [i for i, block_id in enumerate(world_data) if block_id == 3]
    stone_index = 0

    req_tool = OPTIMAL_TOOLS.get(TARGET_BLOCK, "wood_pickaxe")

    print(f"🔍 Quét Map: Tìm thấy {len(target_positions)} khối (ID: {TARGET_BLOCK})")

    if MAX_COLLECT > 0:
        print(f"🎯 Mục tiêu thiết lập: Đào chính xác {MAX_COLLECT} khối.")
    else:
        print("🎯 Mục tiêu thiết lập: Càn quét toàn bộ bản đồ.")

    print(f"🧠 Bot đã tự chọn công cụ tối ưu: '{req_tool if req_tool else 'Tay Không'}'\n")

    print("⏳ Đang tải dữ liệu túi đồ và thể lực...")
    init_res = send_api("user", {})
    if init_res.get("error"):
        print("❌ Lỗi tải dữ liệu. Hãy cập nhật lại chuỗi InitData!")
        exit()

    current_inventory = init_res.get("user", {}).get("Inventory", [])
    current_food = init_res.get("user", {}).get("Food", 0)

    collected = 0
    coal_counter = 0

    for pos in target_positions:

        # --- BƯỚC 1: KIỂM TRA CÚP & TỰ ĐỘNG CHẾ TẠO ---
        if not has_item(current_inventory, req_tool):

            print(f"⚠️ Không tìm thấy {req_tool} trong túi (Có thể vừa gãy). Đang Auto Chế Tạo...")
            craft_res = send_api("craft", {"entityId": req_tool})

            if craft_res.get("success"):
                print(f"   🔨 Chế tạo {req_tool} THÀNH CÔNG!")
                current_inventory = craft_res.get("user", {}).get("Inventory", [])

                # ==========================================
                # ĐÀO 3 ĐÁ SAU KHI CHẾ TẠO CÚP ĐÁ
                # ==========================================
                if req_tool == "stone_pickaxe":

                    print("   🪨 Đào 3 đá sau khi chế tạo cúp đá...")

                    for _ in range(3):

                        if stone_index >= len(stone_positions):
                            break

                        stone_pos = stone_positions[stone_index]
                        stone_index += 1

                        stone_break = send_api(
                            "world/break",
                            {
                                "position": stone_pos,
                                "toolEntityId": req_tool
                            }
                        )

                        if stone_break.get("success"):
                            print(f"      ⛏️ Đã đào đá tại pos {stone_pos}")
                        else:
                            print("      ❌ Đào đá lỗi")

            else:
                reason = craft_res.get("reason", "Thiếu nguyên liệu")
                print(f"   ❌ Chế tạo thất bại: {reason}. Bot tự động dừng để bạn đi farm nguyên liệu!")
                break

            time.sleep(0.4)

        # --- BƯỚC 2: ĐẬP BLOCK ---
        break_res = send_api("world/break", {"position": pos, "toolEntityId": req_tool})

        if break_res.get("success"):

            collected += 1

            user_data = break_res.get("user", {})
            current_food = user_data.get("Food", current_food)
            current_inventory = user_data.get("Inventory", current_inventory)

            drops = break_res.get("drops", [])

            # ĐẾM THAN
            for d in drops:
                if d.get("id") == "coal":
                    coal_counter += d.get("amount", 1)

            # AUTO BÁN THAN
            while coal_counter >= 30 and AUTO_TRADE_COAL:

                print("📦 Đủ 30 than -> gọi trader...")
                trade_coal()
                coal_counter -= 30

            drop_names = [d.get("id") for d in drops] if drops else ["Bốc hơi"]

            print(f"⛏️ Pos {pos:05} | Đã gom: {collected} | Rớt: {drop_names} | Thể lực: {current_food}/60")

            if MAX_COLLECT > 0 and collected >= MAX_COLLECT:
                print(f"\n✅ CHÚC MỪNG: Đã đạt đủ chỉ tiêu {MAX_COLLECT} khối. Bot tự động đóng máy để bảo toàn thể lực!")
                break

            while current_food < EAT_THRESHOLD:

                apple_idx = get_item_index(current_inventory, "apple")

                if apple_idx != -1:

                    print(f"   🆘 Thể lực yếu ({current_food})! Đang tự động ăn táo ở ô {apple_idx}...")

                    eat_res = send_api("inventory/eat", {"index": apple_idx})

                    if eat_res.get("success"):

                        current_food = eat_res.get("user", {}).get("Food", 0)
                        current_inventory = eat_res.get("user", {}).get("Inventory", [])
                        print(f"   🍎 Nhai táo xong! Thể lực hồi lên: {current_food}")

                    else:
                        print("   ❌ Lỗi khi ăn táo!")
                        break

                else:

                    print("   ⚠️ CẢNH BÁO: Đã hết sạch táo dự trữ trong túi!")
                    break

            if current_food == 0 and get_item_index(current_inventory, "apple") == -1:

                print("🛑 Bot dừng: Nhân vật đã kiệt sức và không còn táo!")
                break

        else:

            reason = break_res.get("reason", "Lỗi server")
            print(f"❌ Pos {pos:05} Thất bại: {reason}")

            if reason == "no_food":
                print("🛑 Hết thể lực thật rồi. Dừng bot!")
                break

    print(f"\n🎉 TỔNG KẾT CHIẾN DỊCH: Đã gom gọn {collected} khối về kho!")

except FileNotFoundError:
    print("❌ Lỗi: Không tìm thấy file 'map.json' trên Colab.")
