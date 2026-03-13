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

API_BASE = "https://api.eeventapp.io/minegram"
INIT_DATA = os.getenv("INIT_DATA")
SALT = os.getenv("SALT")

SMELT_ENTITY = "diamond_ore"
FURNACE_POSITIONS = [8712, 8713, 8714, 8715]

def generate_headers():
    request_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    timestamp = str(int(time.time() * 1000))
    msg = f"{INIT_DATA}.{request_id}.{timestamp}.{SALT}"
    signature = hmac.new(SALT.encode(), msg.encode(), hashlib.sha256).hexdigest()
    
    return {
        "accept": "*/*",
        "content-type": "application/json",
        "x-esecure-initdata": INIT_DATA,
        "x-esecure-requestid": request_id,
        "x-esecure-timestamp": timestamp,
        "x-esecure-signature": signature,
        "Referer": "https://api.eeventapp.io/"
    }

def send_api(endpoint, payload={}):
    try:
        res = requests.post(
            f"{API_BASE}/{endpoint}",
            headers=generate_headers(),
            json=payload,
            timeout=15
        )
        text = res.text
        if text.startswith("{") or text.startswith("["):
            return json.loads(text)
        return json.loads(gzip.decompress(base64.b64decode(text)).decode())
    except Exception as e:
        print(f"Lỗi khi gọi API {endpoint}: {e}")
        return {}

def main():
    pending_furnaces = FURNACE_POSITIONS.copy()

    while len(pending_furnaces) > 0:
        print(f"\n🔄 Bắt đầu quét map. Các lò cần xử lý: {pending_furnaces}")
        map_data = send_api("world")
        
        meta_data = map_data.get("meta", {})
        processes = meta_data.get("Processes", [])
        active_processes = {p.get("BlockPosition"): p for p in processes}
        
        min_sleep_time = None
        successfully_handled = []

        for pos in pending_furnaces:
            print(f"\n--- Xử lý lò tại {pos} ---")
            process = active_processes.get(pos)
            can_smelt = False 

            if process:
                process_id = process.get("ID")
                is_complete = process.get("IsComplete", False)
                
                if not is_complete:
                    seconds_remaining = process.get("SecondsRemaining", 0)
                    print(f"⏳ Lò đang nung. Còn lại: {seconds_remaining} giây.")
                    
                    if seconds_remaining > 0:
                        if min_sleep_time is None or seconds_remaining < min_sleep_time:
                            min_sleep_time = seconds_remaining
                    continue
                    
                print(f"⚒️  Đã chín! Thu hoạch mẻ cũ processId: {process_id}")
                collect_res = send_api("furnace/collect", {"processId": process_id})
                
                if collect_res.get("success"):
                    print("✅ Thu hoạch thành công!")
                    can_smelt = True
                else:
                    print("⚠️ Lỗi thu hoạch. Thử lại vòng sau.")
                    if min_sleep_time is None or min_sleep_time > 10:
                        min_sleep_time = 10
                    continue 
            else:
                print("ℹ️ Lò đang trống.")
                can_smelt = True
                
            time.sleep(1) # Delay 1s chống spam API
            
            if can_smelt:
                print(f"🔥 Nung mẻ mới: {SMELT_ENTITY}")
                smelt_res = send_api("furnace/smelt", {
                    "blockPosition": pos,
                    "inputEntityId": SMELT_ENTITY
                })
                
                if smelt_res.get("success"):
                    new_process_id = smelt_res["process"]["ID"]
                    print(f"✅ Xong lò {pos}! processId mới: {new_process_id}")
                    successfully_handled.append(pos)
                else:
                    print("❌ Lỗi nhét mẻ mới. Thử lại vòng sau.")
                    if min_sleep_time is None or min_sleep_time > 10:
                        min_sleep_time = 10
                
            time.sleep(1) # Delay 1s chống spam API

        for pos in successfully_handled:
            pending_furnaces.remove(pos)

        if len(pending_furnaces) == 0:
            print("\n🎉 Đã hoàn thành nung mới cho toàn bộ 4 lò. Kết thúc script!")
            break

        if min_sleep_time is not None:
            # Chỉ cộng đúng 1 giây bù trừ trễ server
            sleep_time = min_sleep_time + 1 
            print(f"\n💤 Có lò chưa xong. Script sẽ ngủ {sleep_time} giây rồi dậy làm tiếp...")
            time.sleep(sleep_time)
        else:
            print("\n⚠️ Không tính được thời gian ngủ, tự động ngủ 10s...")
            time.sleep(10)

if __name__ == "__main__":
    main()
