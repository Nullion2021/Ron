import json

class MjxGameRecorder:
    """
    负责收集 mjx 的原始数据，不进行任何格式转换。
    """
    def __init__(self):
        self.history = []

    def record_turn(self, player_id, obs, legal_actions, chosen_action):
        """
        记录一个回合的原始信息
        """
        # 1. 获取刚摸到的牌 (用于后续恢复 tsumo 事件)
        draw_tile_id = None
        try:
            curr_hand = obs.curr_hand()
            if hasattr(curr_hand, 'last_added_tile'):
                last_tile = curr_hand.last_added_tile()
                if last_tile is not None:
                    draw_tile_id = self._obj_to_id(last_tile)
        except:
            pass

        # 2. 序列化 Action (转为 ID 或 dict)
        # 这里为了通用，我们存 ID 和 type
        actions_data = []
        for act in legal_actions:
            actions_data.append({
                "type": self._obj_to_id(act.type()),
                "tile": self._obj_to_id(act.tile())
            })

        chosen_data = {
            "type": self._obj_to_id(chosen_action.type()),
            "tile": self._obj_to_id(chosen_action.tile()),
            "who": self._obj_to_id(chosen_action.who())
        }

        # 3. 序列化 State/Obs (mjx 原生 JSON)
        try:
            state_json = json.loads(obs.to_json())
        except:
            state_json = {}

        # 存入列表
        record_entry = {
            "player_id": player_id,
            "draw_tile": draw_tile_id,
            "legal_actions": actions_data,
            "chosen_action": chosen_data,
            "state": state_json
        }
        self.history.append(record_entry)

    def _obj_to_id(self, obj):
        if obj is None: return None
        if hasattr(obj, 'id'): return obj.id()
        if hasattr(obj, 'value'): return obj.value
        try: return int(obj)
        except: return None

    def save_mjx(self, filename="mjx_record.json"):
        """保存 mjx 原生记录"""
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.history, f, separators=(',', ':'))
        print(f"[Recorder] Mjx 原生记录已保存: {filename}")


class MjxToMjaiConverter:
    """
    负责将 mjx 原生记录转换为 MJAI 格式
    """
    def __init__(self):
        self.events = []
        # 初始化牌 ID 缓存 (0-135 -> 1m, 2m...)
        self.tile_cache = {i: self._id_to_mjai(i) for i in range(136)}
        self.current_round = -1

    def _id_to_mjai(self, tile_id):
        if tile_id is None: return "??"
        type_idx = tile_id // 36
        num_idx = (tile_id % 36) // 4
        suffixes = ['m', 'p', 's', 'z']
        if type_idx > 3: return "5z" 
        return f"{num_idx + 1}{suffixes[type_idx]}"

    def convert(self, mjx_record_path, output_path):
        print(f"[Converter] 正在转换 {mjx_record_path} -> {output_path} ...")
        self.events = []
        self.current_round = -1
        
        with open(mjx_record_path, "r", encoding="utf-8") as f:
            history = json.load(f)

        if not history:
            print("[Converter] 记录为空")
            return

        # 处理第一局的开始
        first_state = history[0].get("state", {})
        self._record_new_round(first_state)

        for step in history:
            state = step.get("state", {})
            player_id = step.get("player_id")
            draw_tile_id = step.get("draw_tile")
            legal_actions = step.get("legal_actions", [])
            chosen_action = step.get("chosen_action", {})

            # 1. 检查是否切局 (New Round)
            self._check_new_round(state)

            # 2. 摸牌检测 logic (Tsumo)
            # 如果可以切牌(1,2)或暗杠(6)或自摸(10)或立直(3)，说明刚摸了牌
            can_act_on_draw = False
            for act in legal_actions:
                atype = act.get("type")
                if atype in [1, 2, 3, 6, 10]:
                    can_act_on_draw = True
                    break
            
            if can_act_on_draw and draw_tile_id is not None:
                self.events.append({
                    "type": "tsumo",
                    "actor": player_id,
                    "pai": self.tile_cache.get(draw_tile_id, "?")
                })

            # 3. 记录动作 (Action)
            self._log_action(chosen_action)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.events, f, separators=(',', ':'))
        print(f"[Converter] MJAI 转换完成: {output_path}")

    def _check_new_round(self, state_meta):
        r = state_meta.get('round', 0)
        if r != self.current_round:
            self._record_new_round(state_meta)
            self.current_round = r

    def _record_new_round(self, meta):
        bakaze_map = {0: "E", 1: "S", 2: "W", 3: "N"}
        r = meta.get('round', 0)
        honba = meta.get('honba', 0)
        # 兼容 mjx 不同版本的字段名
        sticks = meta.get('riichiSticks', meta.get('riichi_sticks', 0))
        dora_markers = meta.get('doraMarkers', meta.get('dora_markers', []))
        
        dora_str = "?"
        if dora_markers:
            # mjx json 中 doraMarkers 通常是 ID 列表
            d = dora_markers[-1]
            dora_str = self.tile_cache.get(int(d), "?")

        # 为了获取手牌 (tehais)，mjx 的 obs json 中通常有 'privateObservation' 或类似字段
        # 但 obs.to_json() 往往只包含当前视角的。
        # 这里做一个简化：如果无法从 json 还原初始手牌，MJAI 查看器可能会显示为空或只能看到自己的。
        # *在完整实现中，mjx record 应该包含所有人的手牌信息*
        # 这里暂存空手牌占位
        tehais = [[], [], [], []]

        event = {
            "type": "start_kyoku",
            "bakaze": bakaze_map.get((r // 4) % 4, "E"),
            "kyoku": (r % 4) + 1,
            "honba": honba,
            "kyotaku": sticks,
            "dora_marker": dora_str,
            "tehais": tehais 
        }
        self.events.append(event)

    def _log_action(self, action_data):
        act_type = action_data.get("type")
        who = action_data.get("who")
        tile_id = action_data.get("tile")
        pai_str = self.tile_cache.get(tile_id, "?")

        mjai_event = {"type": "none"}

        if act_type == 1:   # DISCARD (手切)
            mjai_event = {"type": "dahai", "actor": who, "pai": pai_str, "tsumogiri": False}
        elif act_type == 2: # TSUMOGIRI (摸切)
            mjai_event = {"type": "dahai", "actor": who, "pai": pai_str, "tsumogiri": True}
        elif act_type == 3: # RIICHI
            self.events.append({"type": "reach", "actor": who})
            mjai_event = {"type": "dahai", "actor": who, "pai": pai_str, "tsumogiri": False}
        elif act_type == 4: # CHI
            mjai_event = {"type": "naki", "actor": who, "pai": pai_str, "type_naki": "chi"}
        elif act_type == 5: # PON
            mjai_event = {"type": "naki", "actor": who, "pai": pai_str, "type_naki": "pon"}
        elif act_type == 6: # ANKAN
            mjai_event = {"type": "naki", "actor": who, "pai": pai_str, "type_naki": "ankan"}
        elif act_type == 7: # MINKAN
            mjai_event = {"type": "naki", "actor": who, "pai": pai_str, "type_naki": "minkan"}
        elif act_type == 8: # KAKAN
            mjai_event = {"type": "naki", "actor": who, "pai": pai_str, "type_naki": "kakan"}
        elif act_type == 9: # RON
            mjai_event = {"type": "hora", "actor": who, "target": "ron"}
        elif act_type == 10:# TSUMO
            mjai_event = {"type": "hora", "actor": who, "target": "tsumo"}
        elif act_type == 11:# RYUKYOKU
            mjai_event = {"type": "ryukyoku"}

        if mjai_event["type"] != "none":
            self.events.append(mjai_event)