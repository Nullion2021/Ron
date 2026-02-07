import socket
import json
import sys
import random
import time

HOST = '127.0.0.1'
PORT = 65432

class MahjongClient:
    def __init__(self, mode="manual"):
        self.mode = mode
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = -1

    def connect(self):
        try:
            self.sock.connect((HOST, PORT))
            # 接收 Server 的 Hello 包
            data = self.read_json()
            if data and data['type'] == 'hello':
                self.player_id = data['player_id']
                print(f"✅ 已连接服务器，我是玩家 P{self.player_id}，模式: [{self.mode.upper()}]")
        except ConnectionRefusedError:
            print("❌ 无法连接服务器，请确认 server.py 已启动")
            sys.exit()

    def read_json(self):
        """简单的按行读取 JSON"""
        try:
            data = self.sock.recv(4096).strip()
            if not data: return None
            # 处理粘包风险（简单处理：假设每次只有一条json）
            return json.loads(data.decode())
        except Exception as e:
            return None

    def display_ascii_hand(self, hand, actions, info):
        print("\n" + "="*40)
        print(f"🎮 轮到你了 (P{self.player_id}) | {info}")
        print(f"🀄 手牌: {' '.join(hand)}")
        print("-" * 40)
        print("可执行动作:")
        for i, act in enumerate(actions):
            print(f"  [{i}] {act}")
        print("="*40)

    def run(self):
        self.connect()
        
        while True:
            msg = self.read_json()
            if not msg:
                break
            
            if msg['type'] == 'game_over':
                print("🏁 对局结束")
                break
            
            if msg['type'] == 'turn':
                # 是我的回合
                hand = msg['hand']
                actions = msg['actions']
                
                # === 决策逻辑 ===
                choice = 0
                
                if self.mode == "manual":
                    self.display_ascii_hand(hand, actions, msg['info'])
                    while True:
                        try:
                            user_input = input(f"请输入动作编号 (0-{len(actions)-1}): ")
                            choice = int(user_input)
                            if 0 <= choice < len(actions):
                                break
                        except ValueError:
                            pass
                else:
                    # === 自动模式 (AI) ===
                    # 这里为了演示，我们使用 Random AI
                    # 如果你想接入你的 AI，就在这里调用你的 model.predict()
                    # 简单模拟思考时间
                    print(f"[Auto] P{self.player_id} 正在思考...", end="\r")
                    time.sleep(0.1) 
                    choice = random.randint(0, len(actions) - 1)
                    # 打印一下机器人的选择
                    print(f"[Auto] P{self.player_id} 选择了: {actions[choice]}")

                # 发送响应
                resp = {"act_idx": choice}
                self.sock.sendall(json.dumps(resp).encode())

        self.sock.close()

if __name__ == "__main__":
    # 使用方法: python client.py [auto/manual]
    mode = "manual"
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    
    client = MahjongClient(mode=mode)
    client.run()