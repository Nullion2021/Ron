import socket
import json
import sys
import random
import time

# --- 辅助显示工具 ---
def get_tile_str(tid):
    t_type = tid // 4
    if 0 <= t_type <= 8: return f"{t_type + 1}m" # 万
    if 9 <= t_type <= 17: return f"{t_type - 9 + 1}p" # 筒
    if 18 <= t_type <= 26: return f"{t_type - 18 + 1}s" # 索
    z_map = {27:'东', 28:'南', 29:'西', 30:'北', 31:'白', 32:'发', 33:'中'}
    return z_map.get(t_type, '?')

def get_action_str(aid):
    if 0 <= aid < 136:
        return f"切 {get_tile_str(aid)}"
    return f"操作(ID:{aid})" 
# ------------------

def run_client(mode):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(('127.0.0.1', 65432))
        print(f"[*] 已连接服务端 | 模式: {mode}")
    except:
        print("[!] 连接失败，请先启动 server.py")
        return

    buffer = ""
    while True:
        try:
            chunk = sock.recv(65536).decode('utf-8')
            if not chunk: break
            buffer += chunk
            
            if "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                data = json.loads(line)
                
                if data['type'] == 'game_over':
                    print(f"\n=== GAME OVER ===\n得分: {data.get('rewards')}")
                    break
                
                elif data['type'] == 'turn':
                    # 解析数据
                    raw_json = data['mjx_raw_json']
                    legal_actions = data['legal_actions']
                    state_obj = json.loads(raw_json)
                    
                    # 1. 简单渲染界面
                    my_info = state_obj.get('privateInfos', [{}])[0]
                    hand = sorted(my_info.get('hand', []))
                    hand_str = " ".join([get_tile_str(t) for t in hand])
                    
                    print("\n" + "="*50)
                    print(f"【Player 0 - {mode.upper()}】")
                    print(f"手牌: [{hand_str}]")
                    
                    # 2. 原始 MJX 信息 (Requirement 5)
                    wall_count = len(state_obj.get('hiddenState', {}).get('wall', []))
                    dora_inds = state_obj.get('publicObservation', {}).get('doraInds', [])
                    print(f"[MJX Info] Wall: {wall_count}, DoraInds: {dora_inds}")
                    print("-" * 50)
                    
                    # 3. 决策
                    chosen = None
                    if mode == 'human':
                        print("可行操作:")
                        for idx, act in enumerate(legal_actions):
                            print(f"  [{idx}] {get_action_str(act)} (ID: {act})")
                        while True:
                            try:
                                i = int(input("请输入序号: "))
                                if 0 <= i < len(legal_actions):
                                    chosen = legal_actions[i]
                                    break
                            except: pass
                    else:
                        # Auto
                        time.sleep(0.1)
                        chosen = random.choice(legal_actions)
                        print(f"[Auto] 执行: {get_action_str(chosen)}")
                    
                    sock.sendall(str(chosen).encode('utf-8'))

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            break
    sock.close()

if __name__ == "__main__":
    if len(sys.argv) < 2: 
        print("Usage: python client.py [human|auto]")
    else:
        run_client(sys.argv[1])