import asyncio
import time
import httpx
import json
import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from cachetools import TTLCache
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import pickle
from datetime import datetime
from google.protobuf import json_format
from collections import defaultdict

# ============= VERCEL PATH FIX =============
current_dir = os.path.dirname(os.path.abspath(__file__))
proto_dir = os.path.join(current_dir, 'proto')
if proto_dir not in sys.path:
    sys.path.insert(0, proto_dir)

# Import proto files
try:
    from proto import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2
    from proto import GetOutfit_pb2
    print("✅ Proto files imported successfully")
except ImportError as e:
    print(f"❌ Proto import error: {e}")
    # Vercel-এ fallback
    try:
        import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2
        import GetOutfit_pb2
        print("✅ Proto files imported directly")
    except ImportError as e2:
        print(f"❌ Both imports failed: {e2}")

# =============================================
# 🔧 কনফিগারেশন
# =============================================

RELEASEVERSION = "OB54"
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 14; CPH2095 Build/RKQ1.211119.001)"

MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')

# =============================================
# 👤 একাউন্ট ক্রেডেনশিয়াল
# =============================================

ACCOUNT_CREDENTIALS = {
    "BD": {"uid": "4270778393", "password": "MG24_GAMER_9NMYG_BY_SPIDEERIO_GAMING_FXK8R"},
    "IND": {"uid": "4269013803", "password": "MG24_GAMER_XSBOS_BY_SPIDEERIO_GAMING_TE5NG"},
    "ME": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"},
    "SG": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"},
    "ID": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"},
    "TH": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"},
    "VN": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"},
    "PK": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"},
    "BR": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"},
    "US": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"},
    "EU": {"uid": "4269012488", "password": "MG24_GAMER_U27YB_BY_SPIDEERIO_GAMING_0PNCN"}
}

# =============================================
# 🌍 রিজন কনফিগ
# =============================================

REGION_CONFIG = {
    "BD": {"server_url": "https://loginbp.ggblueshark.com", "release_version": "OB54", "client_version": "1.124.0"},
    "IND": {"server_url": "https://loginbp.ggpolarbear.com", "release_version": "OB54", "client_version": "1.124.0"},
    "ME": {"server_url": "https://loginbp.ggblueshark.com", "release_version": "OB54", "client_version": "1.124.0"},
    "SG": {"server_url": "https://loginbp.ggblueshark.com", "release_version": "OB54", "client_version": "1.124.0"},
    "ID": {"server_url": "https://loginbp.ggblueshark.com", "release_version": "OB54", "client_version": "1.124.0"},
    "TH": {"server_url": "https://loginbp.ggblueshark.com", "release_version": "OB54", "client_version": "1.124.0"},
    "VN": {"server_url": "https://loginbp.ggblueshark.com", "release_version": "OB54", "client_version": "1.124.0"},
    "PK": {"server_url": "https://loginbp.ggblueshark.com", "release_version": "OB54", "client_version": "1.124.0"},
    "BR": {"server_url": "https://loginbp.ggpolarbear.com", "release_version": "OB54", "client_version": "1.124.0"},
    "US": {"server_url": "https://loginbp.ggpolarbear.com", "release_version": "OB54", "client_version": "1.124.0"},
    "EU": {"server_url": "https://loginbp.ggblueshark.com", "release_version": "OB54", "client_version": "1.124.0"}
}

REGION_PRIORITY = ["BD", "IND", "ME", "SG", "ID", "TH", "VN", "PK", "BR", "US", "EU"]

# === Flask App ===
app = Flask(__name__)
CORS(app)
token_manager = None

# === Token Manager ===
class TokenManager:
    def __init__(self):
        self.tokens = {}
        self.lock = asyncio.Lock()
    
    async def get_token(self, region: str):
        async with self.lock:
            token_info = self.tokens.get(region)
            if token_info and token_info.get('expires_at', 0) > time.time():
                return token_info
            
            print(f"🔄 Generating new token for {region}")
            new_token = await self.generate_token(region)
            if new_token:
                self.tokens[region] = new_token
                return new_token
            return None
    
    async def generate_token(self, region: str):
        try:
            cred = ACCOUNT_CREDENTIALS.get(region, ACCOUNT_CREDENTIALS["ME"])
            account = f"uid={cred['uid']}&password={cred['password']}"
            
            token_val, open_id = await get_access_token(account)
            
            if not token_val or not open_id:
                print(f"❌ Failed to get access token for {region}")
                return None
            
            body = json.dumps({
                "open_id": open_id, 
                "open_id_type": "4", 
                "login_token": token_val, 
                "orign_platform_type": "4"
            })
            proto_bytes = await json_to_proto(body, FreeFire_pb2.LoginReq())
            payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, proto_bytes)
            
            config = REGION_CONFIG.get(region, REGION_CONFIG["ME"])
            url = f"{config['server_url']}/MajorLogin"
            
            headers = {
                'User-Agent': USERAGENT,
                'Connection': "Keep-Alive",
                'Accept-Encoding': "gzip",
                'Content-Type': "application/octet-stream",
                'Expect': "100-continue",
                'X-Unity-Version': "2018.4.11f1",
                'X-GA': "v1 1",
                'ReleaseVersion': config['release_version']
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, data=payload, headers=headers)
                if resp.status_code != 200:
                    print(f"❌ MajorLogin returned {resp.status_code} for {region}")
                    return None
                
                login_res = FreeFire_pb2.LoginRes()
                login_res.ParseFromString(resp.content)
                msg_json = json_format.MessageToJson(login_res)
                msg = json.loads(msg_json)
                
                token_info = {
                    'token': f"Bearer {msg.get('token','0')}",
                    'region': msg.get('lockRegion','0'),
                    'server_url': msg.get('serverUrl','0'),
                    'expires_at': time.time() + 25200
                }
                print(f"✅ Token generated for {region}")
                return token_info
                
        except Exception as e:
            print(f"❌ generate_token error for {region}: {e}")
            return None

# === Helper Functions ===
def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(plaintext))

async def json_to_proto(json_data: str, proto_message) -> bytes:
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

async def get_access_token(account: str):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = account + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    headers = {'User-Agent': USERAGENT, 'Content-Type': "application/x-www-form-urlencoded"}
    
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, data=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("access_token"), data.get("open_id")
                await asyncio.sleep(2)
        except:
            await asyncio.sleep(2)
    return None, None

async def GetAccountInformation(uid, region):
    try:
        token_info = await token_manager.get_token(region)
        if not token_info:
            return None
        
        token = token_info['token']
        server_url = token_info['server_url']
        config = REGION_CONFIG.get(region, REGION_CONFIG["ME"])
        
        payload = await json_to_proto(json.dumps({'a': uid, 'b': '7'}), main_pb2.GetPlayerPersonalShow())
        data_enc = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, payload)
        
        headers = {
            'User-Agent': USERAGENT,
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/octet-stream",
            'Expect': "100-continue",
            'Authorization': token,
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': config['release_version']
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(server_url + '/GetPlayerPersonalShow', data=data_enc, headers=headers)
            
            if resp.status_code != 200:
                return None
            
            account_info = AccountPersonalShow_pb2.AccountPersonalShowInfo()
            account_info.ParseFromString(resp.content)
            result = json.loads(json_format.MessageToJson(account_info))
            return result
            
    except Exception as e:
        print(f"❌ GetAccountInformation error: {e}")
        return None

async def GetOutfitInfo(uid, region):
    try:
        token_info = await token_manager.get_token(region)
        if not token_info:
            return None
        
        token = token_info['token']
        server_url = token_info['server_url']
        config = REGION_CONFIG.get(region, REGION_CONFIG["ME"])
        
        req = GetOutfit_pb2.CSGetOutfitReq()
        req.AccountId = uid
        proto_bytes = req.SerializeToString()
        data_enc = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, proto_bytes)
        
        headers = {
            'User-Agent': USERAGENT,
            'Content-Type': "application/octet-stream",
            'Authorization': token,
            'ReleaseVersion': config['release_version'],
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            endpoints = ['/GetAccountOutfit', '/GetOutfit', '/AccountOutfit']
            for endpoint in endpoints:
                try:
                    resp = await client.post(server_url + endpoint, data=data_enc, headers=headers)
                    if resp.status_code == 200:
                        res = GetOutfit_pb2.CSGetOutfitRes()
                        res.ParseFromString(resp.content)
                        return {
                            "WeaponSkinShows": list(res.WeaponSkinShows),
                            "ProfileInfo": {
                                "CharacterId": res.ProfileInfo.CharacterId,
                                "SkinColor": res.ProfileInfo.SkinColor,
                                "Clothes": list(res.ProfileInfo.Clothes),
                                "Skills": [{"SlotNo": s.SlotNo, "SkillId": s.SkillId} for s in res.ProfileInfo.EquippedSkills],
                                "IsSelected": res.ProfileInfo.IsSelected if res.ProfileInfo.HasField('IsSelected') else None,
                                "IsAwakenSelected": res.ProfileInfo.IsAwakenSelected if res.ProfileInfo.HasField('IsAwakenSelected') else None
                            }
                        }
                except:
                    continue
            return None
    except Exception as e:
        print(f"❌ GetOutfitInfo error: {e}")
        return None

# =============================================
# 🚀 মেইন API
# =============================================

@app.route('/info')
def get_full_info():
    uid = request.args.get('uid')
    server = request.args.get('server')
    
    if not uid:
        return jsonify({"error": "UID required"}), 400
    
    try:
        uid_int = int(uid)
    except:
        return jsonify({"error": "Invalid UID"}), 400
    
    if server:
        server = server.upper()
        if server not in REGION_CONFIG:
            return jsonify({"error": f"Server '{server}' not found"}), 400
        regions_to_try = [server]
    else:
        regions_to_try = REGION_PRIORITY
    
    account_data = None
    used_region = None
    
    for region in regions_to_try:
        print(f"🌍 Trying {region}...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data = loop.run_until_complete(GetAccountInformation(uid_int, region))
            loop.close()
            
            if data:
                account_data = data
                used_region = region
                print(f"✅ Success with {region}")
                break
        except Exception as e:
            print(f"⚠️ {region} error: {e}")
            continue
    
    if not account_data:
        return jsonify({"error": "Player not found"}), 404
    
    outfit_data = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        outfit_data = loop.run_until_complete(GetOutfitInfo(uid_int, used_region))
        loop.close()
    except:
        pass
    
    basic = account_data.get("basicInfo", {})
    clan = account_data.get("clanBasicInfo", {})
    social = account_data.get("socialInfo", {})
    
    response = {
        "status": "success",
        "server_used": used_region,
        "server_requested": server if server else "auto",
        "AccountInfo": {
            "AccountAvatarId": str(basic.get("headPic", "0")),
            "AccountBPBadges": str(basic.get("badgeCnt", "0")),
            "AccountBPID": str(basic.get("badgeId", "0")),
            "AccountBannerId": str(basic.get("bannerId", "0")),
            "AccountCreateTime": str(basic.get("createAt", "0")),
            "AccountEXP": str(basic.get("exp", "0")),
            "AccountLastLogin": str(basic.get("lastLoginAt", "0")),
            "AccountLevel": str(basic.get("level", "0")),
            "AccountLikes": str(basic.get("liked", "0")),
            "AccountName": basic.get("nickname", "Unknown"),
            "AccountRegion": basic.get("region", "Unknown"),
            "AccountSeasonId": str(basic.get("seasonId", "0")),
            "AccountType": str(basic.get("accountType", "0")),
            "BrMaxRank": str(basic.get("maxRank", "0")),
            "BrRankPoint": str(basic.get("rankingPoints", "0")),
            "CsMaxRank": str(basic.get("csMaxRank", "0")),
            "CsRankPoint": str(basic.get("csRankingPoints", "0")),
            "EquippedWeapon": basic.get("weaponSkinShows", []),
            "ReleaseVersion": basic.get("releaseVersion", RELEASEVERSION),
            "ShowBrRank": str(basic.get("showBrRank", "0")),
            "ShowCsRank": str(basic.get("showCsRank", "0")),
            "Title": str(basic.get("title", "0"))
        },
        "AccountProfileInfo": {
            "EquippedOutfit": account_data.get("profileInfo", {}).get("clothes", []),
            "EquippedSkills": account_data.get("profileInfo", {}).get("equipedSkills", [])
        },
        "GuildInfo": {
            "GuildCapacity": str(clan.get("capacity", "0")),
            "GuildID": str(clan.get("clanId", "0")),
            "GuildLevel": str(clan.get("clanLevel", "0")),
            "GuildMember": str(clan.get("memberNum", "0")),
            "GuildName": clan.get("clanName", "No Guild"),
            "GuildOwner": str(clan.get("captainId", "0"))
        },
        "captainBasicInfo": account_data.get("captainBasicInfo", {}),
        "creditScoreInfo": account_data.get("creditScoreInfo", {}),
        "petInfo": account_data.get("petInfo", {}),
        "socialinfo": {
            "accountId": str(social.get("accountId", "0")),
            "language": social.get("language", "en_US")
        }
    }
    
    if outfit_data:
        response["OutfitInfo"] = outfit_data
    
    return jsonify(response)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "version": "OB54",
        "endpoint": "/info?uid=UID&server=SERVER",
        "example": "/info?uid=4270778393&server=BD"
    })

@app.route('/servers')
def list_servers():
    return jsonify({"available_servers": list(REGION_CONFIG.keys())})

@app.route('/status')
def token_status():
    status = {}
    if token_manager:
        for region, info in token_manager.tokens.items():
            expires_in = info['expires_at'] - time.time()
            status[region] = {"has_token": True, "expires_in": f"{expires_in/3600:.1f} hours"}
    return jsonify({"total_tokens": len(token_manager.tokens) if token_manager else 0, "tokens": status})

@app.route('/refresh')
def refresh_tokens():
    global token_manager
    if not token_manager:
        token_manager = TokenManager()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for region in ["BD", "IND", "ME"]:
        loop.run_until_complete(token_manager.get_token(region))
    loop.close()
    return jsonify({"status": "refreshed", "count": len(token_manager.tokens)})

# =============================================
# 🚀 স্টার্টআপ
# =============================================

def start_background():
    global token_manager
    token_manager = TokenManager()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for region in ["BD", "IND", "ME"]:
        try:
            loop.run_until_complete(token_manager.get_token(region))
        except:
            pass
    loop.run_forever()

# Vercel-এর জন্য
try:
    import threading
    bg_thread = threading.Thread(target=start_background, daemon=True)
    bg_thread.start()
except:
    pass

if __name__ == '__main__':
    import threading
    bg_thread = threading.Thread(target=start_background, daemon=True)
    bg_thread.start()
    app.run(host='0.0.0.0', port=5004)