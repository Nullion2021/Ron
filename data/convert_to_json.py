import os
import glob
import gzip
import json
import xml.etree.ElementTree as ET

# 📂 路径配置
# RAW_DIR: 存放从天凤下载的 .mjlog 文件的目录
RAW_DIR = "./data/raw_mjlog"
# JSON_DIR: 转换后的 .json 文件存放目录
JSON_DIR = "./data/json_logs"

def setup_dir():
    """如果输出目录不存在，创建一个"""
    if not os.path.exists(JSON_DIR):
        os.makedirs(JSON_DIR)

def tenhou_tile_to_mjai(tile_id):
    """
    🀄 牌代码转换函数
    
    天凤使用 0-135 的整数来表示 136 张麻将牌。
    规则：
    - 0-35:   万子 (Man) -> 1m ~ 9m (每种4张)
    - 36-71:  筒子 (Pin) -> 1p ~ 9p
    - 72-107: 条子 (Sou) -> 1s ~ 9s
    - 108-135: 字牌 (Zi) -> 东南西北白发中 (1z-7z)
    
    举例: tile_id=0 是 1万(1m), tile_id=4 是 2万(2m)
    注意：这里暂未处理"赤宝牌"(Red Dora, 通常是 id 为 16, 52, 88 的牌)，
    如果需要区分赤牌，需要额外逻辑。
    """
    tm = tile_id // 4  # 除以4，算出它是哪一种牌(0-33)
    
    if tm < 9:
        return f"{tm + 1}m"  # 万子
    elif tm < 18:
        return f"{tm - 9 + 1}p" # 筒子
    elif tm < 27:
        return f"{tm - 18 + 1}s" # 条子
    else:
        return f"{tm - 27 + 1}z" # 字牌

def parse_xml_to_json(file_path):
    try:
        # --- 1. 读取文件内容 ---
        content = None
        try:
            # 以二进制模式读取，因为可能是 gzip 压缩文件
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                # 检查文件头魔数 (Magic Number) 1f 8b 来判断是否为 gzip
                if raw_data.startswith(b'\x1f\x8b'):
                    content = gzip.decompress(raw_data).decode('utf-8')
                else:
                    # 如果不是压缩文件，直接解码文本
                    content = raw_data.decode('utf-8')
        except Exception as e:
            print(f"读取文件失败: {file_path}, {e}")
            return None

        # --- 2. 解析 XML ---
        try:
            # 将字符串转换为 XML 树结构
            root = ET.fromstring(content)
        except ET.ParseError:
            return None

        game_log = []
        
        # --- 3. 遍历 XML 节点 (事件流) ---
        # 天凤的 XML 是扁平的，每一个子节点代表一个动作
        for child in root:
            tag = child.tag      # 标签名 (如 INIT, T12, D30)
            attrs = child.attrib # 属性 (如 seed="...", hai0="...")
            
            event = {}
            
            # === 事件类型：一局开始 (INIT) ===
            if tag == 'INIT':
                # seed 格式: "局数,本场,供托,骰子1,骰子2,宝牌指示牌ID"
                seed = [int(x) for x in attrs['seed'].split(',')]
                
                # 计算场风 (Prevalent Wind)
                # 局数 0-3: 东场, 4-7: 南场, 8-11: 西场
                round_idx = seed[0] // 4
                winds = ['E', 'S', 'W', 'N'] # 东, 南, 西, 北
                bakaze = winds[round_idx % 4]
                
                event = {
                    "type": "start_kyoku",
                    "bakaze": bakaze,             # 场风
                    "kyoku": (seed[0] % 4) + 1,   # 第几局 (1-4)
                    "honba": seed[1],             # 本场数
                    "kyotaku": seed[2],           # 供托(立直棒)数量
                    "dora_marker": tenhou_tile_to_mjai(seed[5]), # 宝牌指示牌
                    "tehais": [] # [重要新增] 初始手牌
                }
                
                # [新增] 解析四位玩家的初始手牌 (hai0, hai1, hai2, hai3)
                for i in range(4):
                    hai_str = attrs.get(f'hai{i}')
                    if hai_str:
                        # 将 "11,22,33..." 这种字符串转为牌的代码列表
                        tiles = [tenhou_tile_to_mjai(int(t)) for t in hai_str.split(',')]
                        event['tehais'].append(tiles)
                    else:
                        event['tehais'].append([]) # 这一局可能少人?
                
            # === 事件类型：鸣牌 (N) ===
            elif tag == 'N':
                # N 标签代表吃、碰、杠。
                # 'who': 谁鸣牌 (0-3)
                # 'm': 这是一个复杂的位掩码(Bitmask)，包含吃了哪张牌、从谁那里吃的。
                # 暂时保留原始 m 值，完全解码需要复杂的位运算逻辑。
                event = {
                    "type": "naki", 
                    "who": int(attrs.get('who')), 
                    "raw_m": attrs.get('m')
                }
                
            # === 事件类型：立直 (REACH) ===
            elif tag == 'REACH':
                # 立直分两步：
                # step=1: 玩家宣言立直 (紧接着会切出一张牌)
                # step=2: 玩家放上点棒 (立直成立)
                event = {
                    "type": "reach", 
                    "who": int(attrs.get('who')), 
                    "step": attrs.get('step')
                }
                
            # === 事件类型：和牌/结束 (AGARI) ===
            elif tag == 'AGARI':
                # 包含谁胡了(who)、胡了谁(fromWho)、分值(ten)等信息
                # 这里简单标记为和牌
                event = {"type": "hora"} 

            # === 事件类型：流局 (RYUUKYOKU) ===
            elif tag == 'RYUUKYOKU':
                event = {"type": "ryukyoku"}
                
            # === 事件类型：摸牌/切牌 (T/D/U/E...) ===
            # 天凤用首字母表示玩家动作：
            # T, D -> 玩家0 (东家) 的 摸牌(Tsumo) / 切牌(Dahai)
            # U, E -> 玩家1 (南家)
            # V, F -> 玩家2 (西家)
            # W, G -> 玩家3 (北家)
            # 后面跟的数字是牌的ID
            elif len(tag) > 1 and tag[0] in ['T', 'D', 'U', 'E', 'V', 'F', 'W', 'G'] and tag[1:].isdigit():
                # 判断是摸牌还是切牌
                action_type = "tsumo" if tag[0] in ['T','U','V','W'] else "dahai"
                
                # 映射字母到玩家 ID
                player_map = {
                    'T':0, 'D':0, 
                    'U':1, 'E':1, 
                    'V':2, 'F':2, 
                    'W':3, 'G':3
                }
                player_id = player_map[tag[0]]
                tile_id = int(tag[1:])
                
                event = {
                    "type": action_type,
                    "actor": player_id,
                    "pai": tenhou_tile_to_mjai(tile_id)
                }
            
            # 如果解析出了有效事件，加入列表
            if event:
                game_log.append(event)
                
        return game_log

    except Exception as e:
        print(f"解析异常 {file_path}: {e}")
        return None

def main():
    setup_dir()
    files = glob.glob(os.path.join(RAW_DIR, "*.mjlog"))
    print(f"开始转换 {len(files)} 个文件...")
    
    count = 0
    for fpath in files:
        json_data = parse_xml_to_json(fpath)
        
        if json_data:
            # 保存为 .json
            # separators=(',', ':') 可以去掉 json 中的空格，减小文件体积
            fname = os.path.basename(fpath).replace('.mjlog', '.json')
            save_path = os.path.join(JSON_DIR, fname)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, separators=(',', ':')) 
            
            count += 1
            if count % 10 == 0:
                print(f"已转换 {count} 个文件")

    print(f"转换完成！JSON文件保存在: {JSON_DIR}")

if __name__ == "__main__":
    main()