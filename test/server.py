import socket
import json
import mjx
import time
from mjx_logger import MjxGameRecorder, MjxToMjaiConverter # 引用新类

HOST = '127.0.0.1'
PORT = 65432

class MahjongServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(4)
        self.clients = [] 
        
        # 实例化记录器和转换器
        self.recorder = MjxGameRecorder()
        self.converter = MjxToMjaiConverter()
        self.tile_converter = self.converter.tile_cache 
        
        self.action_type_map = {
            1: "切牌(手切)", 2: "切牌(摸切)", 3: "立直", 
            4: "吃", 5: "碰", 6: "暗杠", 7: "明杠", 8: "加杠", 
            9: "荣", 10: "自摸", 11: "流局"
        }

    def wait_for_players(self):
        print(f"🀄 服务器启动 {HOST}:{PORT}，等待 4 名玩家加入...")
        while len(self.clients) < 4:
            conn, addr = self.server_socket.accept()
            print(f"玩家 {len(self.clients)} 已连接: {addr}")
            conn.sendall(json.dumps({"type": "hello", "player_id": len(self.clients)}).encode() + b'\n')
            self.clients.append(conn)
        print(">>> 4人集结完毕，对局开始！ <<<")

    def _parse_player_id(self, player_key):
        try: return int(player_key.split('_')[-1])
        except: return 0

    def _obj_to_id(self, obj):
        if obj is None: return None
        if hasattr(obj, 'id'): return obj.id()
        if hasattr(obj, 'value'): return obj.value
        try: return int(obj)
        except: return None

    def run_game(self):
        print(f"正在初始化 MjxEnv 环境...")
        env = mjx.MjxEnv()
        obs_dict = env.reset()

        print("游戏开始！")

        # 循环条件：只要有 obs 返回，说明游戏还在进行
        while obs_dict:
            action_dict = {}

            for player_key, obs in obs_dict.items():
                player_id = self._parse_player_id(player_key)
                legal_actions = obs.legal_actions()
                
                if not legal_actions: continue
                
                # --- 通信逻辑 ---
                # 构建 actions 描述
                action_descriptions = []
                for act in legal_actions:
                    raw_type = self._obj_to_id(act.type())
                    type_str = self.action_type_map.get(raw_type, str(raw_type))
                    tile_str = self.tile_converter.get(self._obj_to_id(act.tile()), "")
                    action_descriptions.append(f"[{type_str}] {tile_str}")

                # 手牌显示 (仅视觉)
                hand_str = []
                try:
                    curr_hand = obs.curr_hand()
                    closed = curr_hand.closed_tiles()
                    tids = sorted([self._obj_to_id(t) for t in closed if self._obj_to_id(t) is not None])
                    hand_str = [self.tile_converter.get(t, "??") for t in tids]
                except: pass

                # 发送给 Client
                payload = {
                    "type": "turn",
                    "hand": hand_str,
                    "actions": action_descriptions,
                    "info": "Playing" 
                }
                conn = self.clients[player_id]
                try:
                    conn.sendall(json.dumps(payload).encode() + b'\n')
                    data = conn.recv(1024).strip()
                    if not data: return

                    resp = json.loads(data.decode())
                    choice_idx = resp.get("act_idx", 0)
                    if choice_idx >= len(legal_actions): choice_idx = 0
                    
                    chosen_action = legal_actions[choice_idx]
                    action_dict[player_key] = chosen_action

                    # === 核心修改：记录原生数据 ===
                    # 在这里我们不转换 MJAI，只存 mjx 对象的信息
                    self.recorder.record_turn(player_id, obs, legal_actions, chosen_action)

                except Exception as e:
                    print(f"Error P{player_id}: {e}")
                    break

            if action_dict:
                obs_dict = env.step(action_dict)
            else:
                break

        print("游戏结束！")
        
        # === 核心修改：两步走保存 ===
        # 1. 保存 mjx 原生记录
        self.recorder.save_mjx("mjx_record.json")
        
        # 2. 转换为 MJAI 格式
        self.converter.convert("mjx_record.json", "game_log.json")

        for conn in self.clients:
            try: conn.close()
            except: pass

if __name__ == "__main__":
    server = MahjongServer()
    server.wait_for_players()
    server.run_game()