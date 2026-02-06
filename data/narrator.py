import json
import os

class MahjongNarrator:
    def __init__(self):
        self.players = ["玩家0", "玩家1", "玩家2", "玩家3"]
        self.tile_map = self._build_tile_map()
    
    def _build_tile_map(self):
        """构建牌代码到中文的映射"""
        mapping = {}
        # 万筒条
        nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九"]
        for i, n in enumerate(nums):
            mapping[f"{i+1}m"] = f"{n}万"
            mapping[f"{i+1}p"] = f"{n}筒"
            mapping[f"{i+1}s"] = f"{n}条"
        # 字牌
        z_names = ["东", "南", "西", "北", "白", "发", "中"]
        for i, z in enumerate(z_names):
            mapping[f"{i+1}z"] = z
        return mapping

    def t(self, tile_code):
        """将 1m 转换为 [一万]"""
        if not tile_code: return ""
        return f"[{self.tile_map.get(tile_code, tile_code)}]"

    def sort_hand(self, tiles):
        """简单理牌（排序）"""
        def sort_key(t):
            # 排序权重: m=0, p=1, s=2, z=3, 数字在后
            type_order = {'m': 0, 'p': 1, 's': 2, 'z': 3}
            return type_order.get(t[-1], 9), int(t[:-1])
        
        return sorted(tiles, key=sort_key)

    def decode_naki(self, raw_m):
        """
        简单解析天凤的副露编码 (raw_m)
        注意：完整解析非常复杂，这里只区分吃/碰/杠类型
        """
        try:
            m = int(raw_m)
            if m & 0x4:
                return "吃"
            elif m & 0x18:
                return "碰"
            elif m & 0x20:
                return "加杠"
            else:
                return "杠" # 暗杠或大明杠
        except:
            return "副露"

    def narrate(self, json_data):
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        print("="*60)
        print("🀄 麻将对局中文解说开始")
        print("="*60)

        # 状态追踪
        last_draw = {} # 记录每个玩家最后摸的牌，用于判断"摸切"

        for event in data:
            etype = event.get("type")
            who = event.get("actor")
            if who is None: who = event.get("who") # 部分事件用 who
            
            p_name = self.players[who] if who is not None else ""

            # --- 1. 开局 ---
            if etype == "start_kyoku":
                print(f"\n>>> {event['bakaze']}风 {event['kyoku']}局 (本场:{event['honba']}) <<<")
                print(f"宝牌指示: {self.t(event['dora_marker'])}")
                
                # 展示初始手牌
                tehais = event.get("tehais")
                if tehais:
                    print("-" * 30)
                    for idx, hand in enumerate(tehais):
                        sorted_hand = self.sort_hand(hand)
                        hand_str = " ".join([self.t(x) for x in sorted_hand])
                        print(f"玩家{idx} 起手: {hand_str}")
                    print("-" * 30)
            
            # --- 2. 摸牌 ---
            elif etype == "tsumo":
                tile = event['pai']
                last_draw[who] = tile
                # 摸牌通常不单独打印，除非为了调试，或者合并在切牌里显示
                pass 

            # --- 3. 切牌 ---
            elif etype == "dahai":
                tile = event['pai']
                draw_tile = last_draw.get(who)
                
                action_str = ""
                if draw_tile == tile:
                    action_str = "摸切" # 摸什么打什么
                else:
                    action_str = f"手切" # 换了一张牌打
                    
                print(f"{p_name} {action_str} {self.t(tile)}")

            # --- 4. 鸣牌 (副露) ---
            elif etype == "naki":
                naki_type = self.decode_naki(event.get('raw_m'))
                print(f"⚡ {p_name} {naki_type}!")

            # --- 5. 立直 ---
            elif etype == "reach":
                step = event.get('step')
                if step == '1':
                    print(f"🚩 {p_name} 宣布立直!")
                elif step == '2':
                    print(f"   (立直成立，放棒)")

            # --- 6. 和牌/流局 ---
            elif etype == "hora":
                print(f"🎉 和牌 (Ron/Tsumo)!")
                print("="*30)
            
            elif etype == "ryukyoku":
                print(f"💨 流局")
                print("="*30)

if __name__ == "__main__":
    # 读取刚才生成的 json 文件
    # 请替换为你实际的文件名
    target_file = "./data/json_logs/2026013000gm-00a9-0000-0cb89d26.json"
    
    # 自动查找第一个json文件演示
    if not os.path.exists(target_file):
        files = [f for f in os.listdir("./data/json_logs") if f.endswith(".json")]
        if files:
            target_file = os.path.join("./data/json_logs", files[0])
        else:
            print("找不到JSON文件，请先运行数据转换脚本。")
            exit()

    print(f"正在读取: {target_file}")
    with open(target_file, 'r', encoding='utf-8') as f:
        content = json.load(f)
        
    narrator = MahjongNarrator()
    narrator.narrate(content)