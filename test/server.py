import socket
import json
import mjx
from mjx.agents import RandomAgent
from google.protobuf import json_format

# === 新增：安全的动作ID获取函数 ===
def get_action_idx(action):
    """尝试多种方式获取动作的整数ID"""
    # 优先尝试标准方法 to_idx()
    if hasattr(action, 'to_idx'):
        return action.to_idx()
    # 其次尝试转为 int
    try:
        return int(action)
    except:
        # 如果都不行，抛出详细错误供调试
        raise AttributeError(f"Action object has no ID method. Dir: {dir(action)}")

def run_server(host='127.0.0.1', port=65432):
    # 初始化 mjx 环境
    agent = RandomAgent()
    env = mjx.MjxEnv()
    
    # 建立 Socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(1)
    
    print(f"[*] 服务端启动 (MjxEnv模式) - 监听 {host}:{port}")
    print(f"[*] 等待 Player 0 接入...")
    
    conn, addr = server_socket.accept()
    print(f"[*] 客户端已连接: {addr}")

    try:
        # 重置环境，开始新的一局
        obs_dict = env.reset()
        
        while not env.done():
            action_dict = {}
            
            # --- 处理 Player 0 (客户端) ---
            # 兼容不同版本的 Key (可能为 "player_0" 或 0)
            p0_obs = obs_dict.get("player_0") or obs_dict.get(0)

            if p0_obs is not None:
                print("\n[Server] 轮到客户端 (Player 0) 行动...")
                
                # 1. 获取合法动作
                legal_actions = p0_obs.legal_actions()
                
                # 【修复点 1】 使用 get_action_idx 替代 a.id()
                legal_action_ids = [get_action_idx(a) for a in legal_actions]
                
                # 2. 准备发送数据
                curr_state = env.state()
                proto_data = curr_state.to_proto()
                json_state = json_format.MessageToJson(proto_data)
                
                packet = {
                    "type": "turn",
                    "mjx_raw_json": json_state,
                    "legal_actions": legal_action_ids
                }
                conn.sendall((json.dumps(packet) + "\n").encode('utf-8'))
                
                # 3. 接收客户端决策
                recv_data = conn.recv(1024).decode('utf-8').strip()
                if not recv_data: break
                
                try:
                    client_act_id = int(recv_data)
                    print(f"[Server] 收到动作ID: {client_act_id}")
                    
                    # 【修复点 2】 在查找动作时，也使用 get_action_idx
                    selected_action = None
                    for a in legal_actions:
                        if get_action_idx(a) == client_act_id:
                            selected_action = a
                            break
                    
                    if selected_action:
                        action_dict["player_0"] = selected_action
                    else:
                        print(f"[!] 警告：客户端动作ID {client_act_id} 不在合法列表 {legal_action_ids} 中，将执行随机动作。")
                        action_dict["player_0"] = agent.act(p0_obs)
                        
                except ValueError:
                    print("[!] 数据格式错误，执行随机动作")
                    action_dict["player_0"] = agent.act(p0_obs)

            # --- 处理其他 AI 玩家 ---
            for player_id, obs in obs_dict.items():
                if player_id != "player_0" and player_id != 0:
                    action_dict[player_id] = agent.act(obs)
            
            # 环境步进
            obs_dict = env.step(action_dict)

        # 游戏结束
        print("[*] 对局结束")
        rewards = env.rewards()
        print(f"[*] 最终得点: {rewards}")
        conn.sendall(json.dumps({"type": "game_over", "rewards": str(rewards)}).encode('utf-8'))

    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        server_socket.close()

if __name__ == "__main__":
    run_server()