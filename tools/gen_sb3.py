"""產生 Scratch 積木群島每一區的「動手做」範例專案（.sb3）。
用法：python3 gen.py <輸出資料夾>   → 產生 *.sb3 與 labs.json
"""
import sys, os, json, zipfile, hashlib, io, math, wave, struct

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
os.makedirs(OUT, exist_ok=True)

# ---------- 素材（原創、簡單的向量圖與合成音） ----------
def svg(body, w=96, h=96):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>'.encode()

def hero_svg(step=0):
    legs = ('<rect x="30" y="74" width="12" height="16" rx="6" fill="#7a4a22"/><rect x="54" y="70" width="12" height="16" rx="6" fill="#7a4a22"/>' if step
            else '<rect x="32" y="72" width="12" height="18" rx="6" fill="#7a4a22"/><rect x="52" y="72" width="12" height="18" rx="6" fill="#7a4a22"/>')
    return svg(legs + '<circle cx="48" cy="44" r="32" fill="#ff8c1a" stroke="#c96a0c" stroke-width="3"/>'
               '<circle cx="38" cy="40" r="6" fill="#fff"/><circle cx="58" cy="40" r="6" fill="#fff"/>'
               '<circle cx="39" cy="41" r="3" fill="#222"/><circle cx="59" cy="41" r="3" fill="#222"/>'
               '<path d="M38 56 Q48 64 58 56" stroke="#7a3a00" stroke-width="3" fill="none" stroke-linecap="round"/>'
               '<path d="M24 22 L48 4 L72 22 Z" fill="#4c97ff" stroke="#3373cc" stroke-width="2"/>')

def enemy_svg():
    return svg('<circle cx="40" cy="40" r="26" fill="#e2483d" stroke="#a52a22" stroke-width="3"/>'
               '<path d="M14 40 L4 34 M66 40 L76 34 M40 14 L40 2" stroke="#a52a22" stroke-width="4" stroke-linecap="round"/>'
               '<circle cx="31" cy="38" r="5" fill="#fff"/><circle cx="49" cy="38" r="5" fill="#fff"/>'
               '<circle cx="32" cy="39" r="2.5" fill="#222"/><circle cx="50" cy="39" r="2.5" fill="#222"/>', 80, 80)

def bird_svg():
    return svg('<ellipse cx="40" cy="42" rx="26" ry="20" fill="#4cbf56" stroke="#2f8a39" stroke-width="3"/>'
               '<path d="M62 40 L76 36 L64 48 Z" fill="#ffbf00"/><circle cx="54" cy="36" r="4" fill="#222"/>'
               '<path d="M26 40 Q34 26 44 40" fill="#7fd48a"/>', 80, 80)

def backdrop_svg():
    lines = ''.join(f'<line x1="{x}" y1="0" x2="{x}" y2="360" stroke="#e3eef3" stroke-width="1"/>' for x in range(0, 481, 40))
    lines += ''.join(f'<line x1="0" y1="{y}" x2="480" y2="{y}" stroke="#e3eef3" stroke-width="1"/>' for y in range(0, 361, 40))
    return svg('<rect width="480" height="360" fill="#f7fbfc"/>' + lines +
               '<line x1="240" y1="0" x2="240" y2="360" stroke="#b9d3dd" stroke-width="2"/><line x1="0" y1="180" x2="480" y2="180" stroke="#b9d3dd" stroke-width="2"/>', 480, 360)

def tone_wav(notes, rate=22050):
    buf = io.BytesIO(); w = wave.open(buf, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    frames = bytearray(); n = 0
    for f, d in notes:
        cnt = int(rate * d)
        for i in range(cnt):
            env = min(1, i / 300) * max(0, 1 - i / cnt) ** 0.6
            v = 0 if f == 0 else int(9000 * env * math.sin(2 * math.pi * f * i / rate))
            frames += struct.pack('<h', v); n += 1
    w.writeframes(bytes(frames)); w.close()
    return buf.getvalue(), n

ASSETS = {}
def asset(data, ext):
    md5 = hashlib.md5(data).hexdigest(); ASSETS[md5 + '.' + ext] = data; return md5

def costume(name, data, cx, cy):
    md5 = asset(data, 'svg')
    return {"name": name, "bitmapResolution": 1, "dataFormat": "svg", "assetId": md5, "md5ext": md5 + ".svg", "rotationCenterX": cx, "rotationCenterY": cy}

def sound(name, notes):
    data, n = tone_wav(notes); md5 = asset(data, 'wav')
    return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "", "rate": 22050, "sampleCount": n, "md5ext": md5 + ".wav"}

DING = [(1318, .12), (1760, .25)]
MUSIC = [(523, .25), (659, .25), (784, .25), (659, .25), (698, .25), (880, .25), (784, .5), (0, .1)]

# ---------- 積木產生器 ----------
class Script:
    def __init__(self):
        self.blocks = {}; self.n = 0
    def _id(self):
        self.n += 1; return f"b{self.n}"
    def b(self, opcode, inputs=None, fields=None, shadow=False, mutation=None):
        i = self._id()
        self.blocks[i] = {"opcode": opcode, "next": None, "parent": None, "inputs": inputs or {}, "fields": fields or {},
                          "shadow": shadow, "topLevel": False}
        if mutation: self.blocks[i]["mutation"] = mutation
        for v in (inputs or {}).values():          # 讓子積木知道 parent
            for x in v[1:]:
                if isinstance(x, str) and x in self.blocks: self.blocks[x]["parent"] = i
        return i
    def stack(self, ids, x=None, y=None):
        ids = [i for i in ids if i]
        for a, c in zip(ids, ids[1:]):
            self.blocks[a]["next"] = c; self.blocks[c]["parent"] = a
        if x is not None:
            self.blocks[ids[0]].update({"topLevel": True, "x": x, "y": y})
        return ids[0]
    # 小工具
    def menu(self, opcode, field, value):
        return self.b(opcode, fields={field: [value, None]}, shadow=True)

def num(v): return [1, [4, str(v)]]
def pos(v): return [1, [5, str(v)]]
def whole(v): return [1, [6, str(v)]]
def ang(v): return [1, [8, str(v)]]
def txt(v): return [1, [10, str(v)]]
def rep(i, kind=10): return [3, i, [kind, ""]]
def boo(i): return [2, i]
def sub(i): return [2, i]
def menu_in(i): return [1, i]
def var_in(name, vid, kind=10): return [3, [12, name, vid], [kind, ""]]

class Proj:
    def __init__(self, key, title):
        self.key = key; self.title = title; self.targets = []; self.vars = {}; self.lists = {}; self.bcasts = {}
        self.ext = set(); self.comments_stage = {}
    def var(self, name, val=0):
        vid = "v_" + hashlib.md5(name.encode()).hexdigest()[:8]; self.vars[vid] = [name, val]; return vid
    def lst(self, name, items=None):
        lid = "l_" + hashlib.md5(name.encode()).hexdigest()[:8]; self.lists[lid] = [name, items or []]; return lid
    def bc(self, name):
        bid = "m_" + hashlib.md5(name.encode()).hexdigest()[:8]; self.bcasts[bid] = name; return bid
    def sprite(self, name, script, costumes, sounds=None, x=0, y=0, size=100, comments=None, rot="all around"):
        com = {}
        for k, (text, cx, cy, w, h) in enumerate(comments or []):
            com[f"c{len(self.targets)}_{k}"] = {"blockId": None, "x": cx, "y": cy, "width": w, "height": h, "minimized": False, "text": text}
        self.targets.append({"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {}, "blocks": script.blocks,
                             "comments": com, "currentCostume": 0, "costumes": costumes, "sounds": sounds or [], "volume": 100,
                             "layerOrder": len(self.targets) + 1, "visible": True, "x": x, "y": y, "size": size, "direction": 90,
                             "draggable": False, "rotationStyle": rot})
    def save(self):
        stage = {"isStage": True, "name": "Stage", "variables": self.vars, "lists": self.lists, "broadcasts": self.bcasts, "blocks": {},
                 "comments": {}, "currentCostume": 0, "costumes": [costume("格線", backdrop_svg(), 240, 180)], "sounds": [], "volume": 100,
                 "layerOrder": 0, "tempo": 60, "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None}
        pj = {"targets": [stage] + self.targets, "monitors": [], "extensions": sorted(self.ext),
              "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": "scratch-islands"}}
        used = set()
        for t in pj["targets"]:
            for c in t["costumes"] + t["sounds"]: used.add(c["md5ext"])
        path = os.path.join(OUT, self.key + ".sb3")
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json", json.dumps(pj, ensure_ascii=False))
            for u in used: z.writestr(u, ASSETS[u])
        return path

HERO = lambda: [costume("走路1", hero_svg(0), 48, 48), costume("走路2", hero_svg(1), 48, 48)]
NOTE = lambda t, x=330, y=20, w=300, h=200: (t, x, y, w, h)
LABS = {}
def lab(key, title, steps, challenges):
    LABS[key] = {"file": key + ".sb3", "title": title, "steps": steps, "challenges": challenges}

# ================= 1 事件島 =================
p = Proj("events-start", "事件島：綠旗與廣播"); s = Script(); m = p.bc("遊戲開始")
s.stack([s.b("event_whenflagclicked"), s.b("motion_gotoxy", {"X": num(0), "Y": num(0)}),
         s.b("looks_switchcostumeto", {"COSTUME": menu_in(s.menu("looks_costume", "COSTUME", "走路1"))}),
         s.b("looks_sayforsecs", {"MESSAGE": txt("準備好了！"), "SECS": num(1)}),
         s.b("event_broadcast", {"BROADCAST_INPUT": [1, [11, "遊戲開始", m]]})], 40, 40)
s.stack([s.b("event_whenkeypressed", fields={"KEY_OPTION": ["space", None]}), s.b("looks_sayforsecs", {"MESSAGE": txt("哈囉！"), "SECS": num(1)})], 40, 300)
p.sprite("小島民", s, HERO(), x=-80, comments=[NOTE("① 按舞台上方的綠旗 ⚑，看程式從上往下一顆一顆執行。\n② 按空白鍵，看看另一段程式。\n\n挑戰：加一段「當角色被點擊」，讓小島民說「好癢！」")])
s2 = Script()
s2.stack([s2.b("event_whenbroadcastreceived", fields={"BROADCAST_OPTION": ["遊戲開始", m]}), s2.b("looks_sayforsecs", {"MESSAGE": txt("收到廣播，我也開始！"), "SECS": num(2)})], 40, 40)
p.sprite("小鳥", s2, [costume("小鳥", bird_svg(), 40, 40)], x=120, y=60)
p.save()
lab("events-start", "綠旗與廣播", ["按綠旗：小島民先說話，再廣播「遊戲開始」", "小鳥收到廣播，也跟著說話", "按空白鍵試試另一段程式"],
    ["加一段「當角色被點擊」，讓小島民說「好癢！」", "把「說出…持續 1 秒」改成 3 秒，小鳥會晚一點才說話嗎？為什麼？"])

# ================= 2 動作島 =================
p = Proj("motion-move", "動作島：座標與移動"); s = Script()
loop = s.stack([s.b("motion_movesteps", {"STEPS": num(5)}), s.b("motion_ifonedgebounce")])
s.stack([s.b("event_whenflagclicked"), s.b("motion_gotoxy", {"X": num(-200), "Y": num(0)}), s.b("motion_pointindirection", {"DIRECTION": ang(90)}),
         s.b("motion_setrotationstyle", fields={"STYLE": ["left-right", None]}), s.b("control_forever", {"SUBSTACK": sub(loop)})], 40, 40)
p.sprite("小島民", s, HERO(), x=-200, rot="left-right", comments=[NOTE("按綠旗，小島民會在舞台上來回走。\n\n挑戰：\n① 把「移動 5 點」改成 15，速度變怎樣？\n② 把「定位到 x:-200」改成 y:100，角色從哪裡出發？\n③ 拿掉「迴轉方式設為 左-右」，反彈時會發生什麼事？")])
p.save()
lab("motion-move", "來回走的角色", ["按綠旗：角色從左邊出發，碰到邊緣就反彈", "注意右下角的 x、y 數字一直在變"], ["把移動 5 點改成 15，速度變快還是變慢？", "拿掉「迴轉方式設為 左-右」，反彈時角色會怎樣？"])

# ================= 3 外觀島 =================
p = Proj("looks-look", "外觀島：逐格動畫"); s = Script()
loop = s.stack([s.b("looks_nextcostume"), s.b("control_wait", {"DURATION": pos(0.2)})])
s.stack([s.b("event_whenflagclicked"), s.b("looks_switchcostumeto", {"COSTUME": menu_in(s.menu("looks_costume", "COSTUME", "走路1"))}),
         s.b("control_forever", {"SUBSTACK": sub(loop)})], 40, 40)
s.stack([s.b("event_whenthisspriteclicked"), s.b("looks_changeeffectby", {"CHANGE": num(25)}, {"EFFECT": ["COLOR", None]}),
         s.b("looks_sayforsecs", {"MESSAGE": txt("變色了！"), "SECS": num(1)})], 40, 260)
p.sprite("小島民", s, HERO(), size=160, comments=[NOTE("按綠旗：兩個造型輪流換，就是動畫。\n點一下角色會變色。\n\n挑戰：\n① 等待改成 0.05 和 1 秒，差在哪？\n② 到「造型」分頁畫第 3 個造型。\n③ 加「尺寸改變 10」讓角色越點越大。")])
p.save()
lab("looks-look", "兩格動畫", ["按綠旗：兩個造型輪流切換，看起來像在走路", "點角色一下，會改變顏色"], ["把等待改成 0.05 秒和 1 秒，動畫有什麼不同？", "到「造型」分頁加畫第 3 個造型，動畫變怎樣？"])

# ================= 4 音效島 =================
p = Proj("sound-play", "音效島：背景音樂"); s = Script()
loop = s.b("sound_playuntildone", {"SOUND_MENU": menu_in(s.menu("sound_sounds_menu", "SOUND_MENU", "背景音樂"))})
s.stack([s.b("event_whenflagclicked"), s.b("sound_setvolumeto", {"VOLUME": num(60)}), s.b("control_forever", {"SUBSTACK": sub(loop)})], 40, 40)
s.stack([s.b("event_whenthisspriteclicked"), s.b("sound_play", {"SOUND_MENU": menu_in(s.menu("sound_sounds_menu", "SOUND_MENU", "叮"))})], 40, 260)
p.sprite("小島民", s, HERO(), sounds=[sound("背景音樂", MUSIC), sound("叮", DING)], size=140,
         comments=[NOTE("按綠旗：背景音樂一首播完再重播。\n點角色會「叮」一聲（不會等，馬上就能再點）。\n\n挑戰：把迴圈裡的「播放音效 直到結束」換成「播放音效」，聽聽看哪裡怪怪的？")])
p.save()
lab("sound-play", "背景音樂與音效", ["按綠旗：音樂播完一首再重播", "點角色：叮一聲，可以一直點"], ["把迴圈裡改成不會等的「播放音效」，聽起來怎樣？", "加「音量改變 -10」，做出漸漸變小聲"])

# ================= 5 迴圈島 =================
p = Proj("loop-loop", "迴圈島：用迴圈畫正方形"); p.ext.add("pen"); s = Script()
body = s.stack([s.b("motion_movesteps", {"STEPS": num(100)}), s.b("motion_turnright", {"DEGREES": num(90)}), s.b("control_wait", {"DURATION": pos(0.3)})])
s.stack([s.b("event_whenflagclicked"), s.b("motion_gotoxy", {"X": num(-50), "Y": num(-50)}), s.b("motion_pointindirection", {"DIRECTION": ang(90)}),
         s.b("pen_clear"), s.b("pen_penDown"), s.b("control_repeat", {"TIMES": whole(4), "SUBSTACK": sub(body)}), s.b("pen_penUp"),
         s.b("looks_sayforsecs", {"MESSAGE": txt("畫完了！"), "SECS": num(2)})], 40, 40)
p.sprite("小島民", s, HERO(), size=50, comments=[NOTE("按綠旗：重複 4 次「走 100、右轉 90」畫出正方形。\n\n挑戰：\n① 畫三角形：重複幾次？轉幾度？\n② 畫六邊形。\n③ 規律：轉角 = 360 ÷ 邊數")])
p.save()
lab("loop-loop", "用迴圈畫正方形", ["按綠旗：重複 4 次「移動 100、右轉 90 度」", "畫筆跟著角色畫出正方形"], ["改成三角形：重複 3 次、右轉 120 度", "畫六邊形，轉角要幾度？（360 ÷ 邊數）"])

# ================= 6 偵測島 =================
p = Proj("sensing-sense", "偵測島：詢問與回答"); s = Script()
j = s.b("operator_join", {"STRING1": txt("你好，"), "STRING2": rep(s.b("sensing_answer"))})
s.stack([s.b("event_whenflagclicked"), s.b("sensing_askandwait", {"QUESTION": txt("你叫什麼名字？")}),
         s.b("looks_sayforsecs", {"MESSAGE": rep(j), "SECS": num(2)})], 40, 40)
s.stack([s.b("event_whenkeypressed", fields={"KEY_OPTION": ["space", None]}), s.b("looks_sayforsecs", {"MESSAGE": rep(s.b("sensing_timer")), "SECS": num(1)})], 40, 280)
p.sprite("小島民", s, HERO(), size=140, comments=[NOTE("按綠旗：輸入你的名字，按 Enter。\n按空白鍵：角色說出計時器過了幾秒。\n\n挑戰：\n① 再問一題「你幾歲？」並說出來。\n② 用「計時器重置」做一個反應速度測驗。")])
p.save()
lab("sensing-sense", "詢問與回答", ["按綠旗：輸入名字按 Enter，角色會跟你打招呼", "按空白鍵：說出計時器的秒數"], ["再問一題「你最喜歡什麼？」並說出答案", "綠旗後先「計時器重置」，再按空白鍵看看秒數"])

# ================= 7 運算島（七區） =================
def ops_proj(key, title, build, note, steps, chal):
    p = Proj(key, title); s = Script(); build(s); p.sprite("小島民", s, HERO(), size=140, comments=[NOTE(note)]); p.save(); lab(key, title.split('：')[1], steps, chal)

def b_arith(s):
    a = s.b("operator_add", {"NUM1": num(3), "NUM2": num(4)}); m_ = s.b("operator_multiply", {"NUM1": rep(a, 4), "NUM2": num(2)})
    s.stack([s.b("event_whenflagclicked"), s.b("looks_sayforsecs", {"MESSAGE": rep(m_), "SECS": num(2)}),
             s.b("looks_sayforsecs", {"MESSAGE": rep(s.b("operator_divide", {"NUM1": num(7), "NUM2": num(2)})), "SECS": num(2)})], 40, 40)
ops_proj("ops-arith", "運算島：四則運算", b_arith, "按綠旗：先說 (3+4)×2，再說 7÷2。\n\n挑戰：把 + 積木拿出來放到外層，變成 3+(4×2)，答案變多少？",
         ["按綠旗：角色說出 (3+4)×2 的答案", "接著說出 7÷2，注意有小數"], ["把積木包法反過來，算 3+(4×2)", "算算看 100 − 37 × 2"])

def b_random(s):
    s.stack([s.b("event_whenthisspriteclicked"), s.b("looks_sayforsecs", {"MESSAGE": rep(s.b("operator_random", {"FROM": num(1), "TO": num(6)})), "SECS": num(1)})], 40, 40)
    s.stack([s.b("event_whenflagclicked"), s.b("looks_say", {"MESSAGE": txt("點我擲骰子！")})], 40, 200)
ops_proj("ops-random", "運算島：隨機骰子", b_random, "點角色：擲一顆 1～6 的骰子。\n\n挑戰：\n① 改成 1～100 的猜數字。\n② 加「定位到 x:(隨機) y:(隨機)」讓角色亂跳。",
         ["按綠旗，再點角色：每次說出不同的 1～6", "多點幾次，看看會不會重複"], ["改成 1 到 100", "加「定位到 x:隨機 y:隨機」讓角色跳到隨機位置"])

def b_compare(s):
    gt = s.b("operator_gt", {"OPERAND1": rep(s.b("sensing_answer")), "OPERAND2": txt(59)})
    s.stack([s.b("event_whenflagclicked"), s.b("sensing_askandwait", {"QUESTION": txt("考幾分？")}),
             s.b("looks_sayforsecs", {"MESSAGE": rep(gt), "SECS": num(2)})], 40, 40)
ops_proj("ops-compare", "運算島：比較", b_compare, "按綠旗：輸入分數，角色說出「分數 > 59」是 true 還是 false。\n\n挑戰：輸入 59、60、100 各試一次。",
         ["按綠旗：輸入分數", "角色說出 true（成立）或 false（不成立）"], ["分別輸入 59、60，結果一樣嗎？", "改成「< 60」，結果會怎麼變？"])

def b_logic(s):
    a = s.b("operator_gt", {"OPERAND1": rep(s.b("sensing_answer")), "OPERAND2": txt(0)})
    c = s.b("operator_lt", {"OPERAND1": rep(s.b("sensing_answer")), "OPERAND2": txt(100)})
    an = s.b("operator_and", {"OPERAND1": boo(a), "OPERAND2": boo(c)})
    s.stack([s.b("event_whenflagclicked"), s.b("sensing_askandwait", {"QUESTION": txt("輸入一個數字")}),
             s.b("looks_sayforsecs", {"MESSAGE": rep(an), "SECS": num(2)})], 40, 40)
ops_proj("ops-logic", "運算島：且、或", b_logic, "按綠旗：檢查數字是不是「大於 0 且 小於 100」。\n\n挑戰：把「且」換成「或」，輸入 200 試試。",
         ["按綠旗：輸入一個數字", "兩個條件都成立才說 true"], ["輸入 -5、50、200 各一次", "把「且」換成「或」，再輸入 200"])

def b_string(s):
    j = s.b("operator_join", {"STRING1": txt("你好，"), "STRING2": rep(s.b("sensing_answer"))})
    l = s.b("operator_length", {"STRING": rep(s.b("sensing_answer"))})
    s.stack([s.b("event_whenflagclicked"), s.b("sensing_askandwait", {"QUESTION": txt("你叫什麼名字？")}),
             s.b("looks_sayforsecs", {"MESSAGE": rep(j), "SECS": num(2)}), s.b("looks_sayforsecs", {"MESSAGE": rep(l), "SECS": num(2)})], 40, 40)
ops_proj("ops-string", "運算島：字串", b_string, "按綠旗：輸入名字，角色打招呼，再說出名字有幾個字。\n\n挑戰：用「字串 (答案) 的第 1 字」說出你的姓。",
         ["按綠旗：輸入名字", "角色把文字接起來打招呼，再說出字數"], ["用「第 1 字」說出你的姓", "用字串組合說出「〇〇同學你好」"])

def b_mod(s):
    m_ = s.b("operator_mod", {"NUM1": rep(s.b("sensing_answer"), 4), "NUM2": num(2)})
    s.stack([s.b("event_whenflagclicked"), s.b("sensing_askandwait", {"QUESTION": txt("輸入一個整數")}),
             s.b("looks_sayforsecs", {"MESSAGE": rep(m_), "SECS": num(2)})], 40, 40)
ops_proj("ops-mod", "運算島：餘數", b_mod, "按綠旗：說出「數字 除以 2 的餘數」。\n0 → 偶數，1 → 奇數。\n\n挑戰：改成除以 3，輸入 9、10、11 看看。",
         ["按綠旗：輸入整數", "說出除以 2 的餘數：0 是偶數，1 是奇數"], ["改成除以 3，輸入 9、10、11", "加「四捨五入」積木，試試輸入 2.5"])

def b_func(s):
    q = s.b("operator_mathop", {"NUM": rep(s.b("sensing_answer"), 4)}, {"OPERATOR": ["sqrt", None]})
    s.stack([s.b("event_whenflagclicked"), s.b("sensing_askandwait", {"QUESTION": txt("輸入一個數字")}),
             s.b("looks_sayforsecs", {"MESSAGE": rep(q), "SECS": num(2)})], 40, 40)
ops_proj("ops-func", "運算島：數學函式", b_func, "按綠旗：說出數字的平方根。\n\n挑戰：點下拉選單換成「絕對值」「無條件捨去」試試。",
         ["按綠旗：輸入數字（例如 81）", "角色說出平方根"], ["把選單換成「絕對值」，輸入 -8", "換成「無條件捨去」，輸入 3.9"])

# ================= 8 變數列表島 =================
p = Proj("vars-var", "變數列表島：點點樂計分"); vid = p.var("分數", 0); s = Script()
s.stack([s.b("event_whenflagclicked"), s.b("data_setvariableto", {"VALUE": txt(0)}, {"VARIABLE": ["分數", vid]}),
         s.b("data_showvariable", fields={"VARIABLE": ["分數", vid]})], 40, 40)
s.stack([s.b("event_whenthisspriteclicked"), s.b("data_changevariableby", {"VALUE": num(1)}, {"VARIABLE": ["分數", vid]}),
         s.b("sound_play", {"SOUND_MENU": menu_in(s.menu("sound_sounds_menu", "SOUND_MENU", "叮"))}),
         s.b("motion_goto", {"TO": menu_in(s.menu("motion_goto_menu", "TO", "_random_"))})], 40, 240)
p.sprite("小島民", s, HERO(), sounds=[sound("叮", DING)], comments=[NOTE("按綠旗，再一直點角色：每點一次分數 +1。\n左上角就是變數「分數」。\n\n挑戰：\n① 把「改變 1」改成「設為 1」，會怎樣？\n② 讓角色越點越小（尺寸改變 -5）。")])
p.save()
lab("vars-var", "點點樂計分", ["按綠旗：分數歸零並顯示在舞台左上角", "一直點角色：分數 +1，角色跳到別的地方"], ["把「改變 1」換成「設為 1」，分數會怎樣？", "每點一次加 10 分"])

p = Proj("vars-patterns", "變數列表島：交換兩個變數"); a_ = p.var("a", 3); b_ = p.var("b", 7); t_ = p.var("暫存", 0); s = Script()
show = s.b("operator_join", {"STRING1": txt("a="), "STRING2": rep(s.b("operator_join", {"STRING1": var_in("a", a_), "STRING2": rep(s.b("operator_join", {"STRING1": txt("  b="), "STRING2": var_in("b", b_)}))}))})
show2 = s.b("operator_join", {"STRING1": txt("交換後 a="), "STRING2": rep(s.b("operator_join", {"STRING1": var_in("a", a_), "STRING2": rep(s.b("operator_join", {"STRING1": txt("  b="), "STRING2": var_in("b", b_)}))}))})
s.stack([s.b("event_whenflagclicked"), s.b("data_setvariableto", {"VALUE": txt(3)}, {"VARIABLE": ["a", a_]}), s.b("data_setvariableto", {"VALUE": txt(7)}, {"VARIABLE": ["b", b_]}),
         s.b("looks_sayforsecs", {"MESSAGE": rep(show), "SECS": num(2)}),
         s.b("data_setvariableto", {"VALUE": var_in("a", a_)}, {"VARIABLE": ["暫存", t_]}), s.b("data_setvariableto", {"VALUE": var_in("b", b_)}, {"VARIABLE": ["a", a_]}),
         s.b("data_setvariableto", {"VALUE": var_in("暫存", t_)}, {"VARIABLE": ["b", b_]}), s.b("looks_sayforsecs", {"MESSAGE": rep(show2), "SECS": num(3)})], 40, 40)
p.sprite("小島民", s, HERO(), size=120, comments=[NOTE("按綠旗：用「暫存」交換 a 和 b。\n\n挑戰：拿掉暫存的那一步，直接 a 設為 b、b 設為 a，結果對嗎？", 420)])
p.save()
lab("vars-patterns", "交換兩個變數", ["按綠旗：先說出 a=3 b=7", "透過「暫存」交換，再說出 a=7 b=3"], ["拿掉暫存，直接互相設定，結果對嗎？", "加一個「總和」變數，算出 a + b"])

p = Proj("vars-list", "變數列表島：水果列表"); lid = p.lst("水果", []); iv = p.var("i", 1); s = Script()
item = s.b("data_itemoflist", {"INDEX": var_in("i", iv, 7)}, {"LIST": ["水果", lid]})
body = s.stack([s.b("looks_sayforsecs", {"MESSAGE": rep(item), "SECS": num(1)}), s.b("data_changevariableby", {"VALUE": num(1)}, {"VARIABLE": ["i", iv]})])
s.stack([s.b("event_whenflagclicked"), s.b("data_deletealloflist", fields={"LIST": ["水果", lid]}),
         s.b("data_addtolist", {"ITEM": txt("蘋果")}, {"LIST": ["水果", lid]}), s.b("data_addtolist", {"ITEM": txt("香蕉")}, {"LIST": ["水果", lid]}),
         s.b("data_addtolist", {"ITEM": txt("芭樂")}, {"LIST": ["水果", lid]}), s.b("data_showlist", fields={"LIST": ["水果", lid]}),
         s.b("data_setvariableto", {"VALUE": txt(1)}, {"VARIABLE": ["i", iv]}),
         s.b("control_repeat", {"TIMES": [3, s.b("data_lengthoflist", fields={"LIST": ["水果", lid]}), [6, ""]], "SUBSTACK": sub(body)})], 40, 40)
p.sprite("小島民", s, HERO(), size=120, comments=[NOTE("按綠旗：清空列表、放入 3 種水果，再一項一項說出來。\n\n挑戰：再加 2 種水果，程式其他地方要改嗎？", 460)])
p.save()
lab("vars-list", "水果列表", ["按綠旗：列表清空後放入蘋果、香蕉、芭樂", "迴圈用 i 一項一項說出來"], ["再加 2 種水果，迴圈次數要改嗎？", "改成隨機說出一種水果"])

# ================= 9 判斷島 =================
p = Proj("if-if", "判斷島：成績等第"); sc = p.var("分數", 0); s = Script()
inner = s.b("control_if_else", {"CONDITION": boo(s.b("operator_gt", {"OPERAND1": var_in("分數", sc), "OPERAND2": txt(59)})),
        "SUBSTACK": sub(s.b("looks_sayforsecs", {"MESSAGE": txt("及格"), "SECS": num(2)})), "SUBSTACK2": sub(s.b("looks_sayforsecs", {"MESSAGE": txt("加油"), "SECS": num(2)}))})
outer = s.b("control_if_else", {"CONDITION": boo(s.b("operator_gt", {"OPERAND1": var_in("分數", sc), "OPERAND2": txt(89)})),
        "SUBSTACK": sub(s.b("looks_sayforsecs", {"MESSAGE": txt("優等"), "SECS": num(2)})), "SUBSTACK2": sub(inner)})
s.stack([s.b("event_whenflagclicked"), s.b("sensing_askandwait", {"QUESTION": txt("考幾分？")}),
         s.b("data_setvariableto", {"VALUE": rep(s.b("sensing_answer"))}, {"VARIABLE": ["分數", sc]}), outer], 40, 40)
p.sprite("小島民", s, HERO(), size=120, comments=[NOTE("按綠旗：輸入分數，依序判斷優等、及格、加油。\n\n挑戰：\n① 輸入 95、70、40 各一次。\n② 把兩個判斷的順序對調，輸入 95 會說什麼？", 480)])
p.save()
lab("if-if", "成績等第", ["按綠旗：輸入分數", "先判斷 > 89，不成立再判斷 > 59"], ["輸入 95、70、40，各說什麼？", "加一個等第：大於 79 說「很好」"])

p = Proj("if-gameloop", "判斷島：躲避遊戲"); lv = p.var("生命", 3); s = Script()
loop = s.stack([
    s.b("control_if", {"CONDITION": boo(s.b("sensing_keypressed", {"KEY_OPTION": menu_in(s.menu("sensing_keyoptions", "KEY_OPTION", "right arrow"))})), "SUBSTACK": sub(s.b("motion_changexby", {"DX": num(6)}))}),
    s.b("control_if", {"CONDITION": boo(s.b("sensing_keypressed", {"KEY_OPTION": menu_in(s.menu("sensing_keyoptions", "KEY_OPTION", "left arrow"))})), "SUBSTACK": sub(s.b("motion_changexby", {"DX": num(-6)}))}),
    s.b("control_if", {"CONDITION": boo(s.b("sensing_touchingobject", {"TOUCHINGOBJECTMENU": menu_in(s.menu("sensing_touchingobjectmenu", "TOUCHINGOBJECTMENU", "敵人"))})),
        "SUBSTACK": sub(s.stack([s.b("data_changevariableby", {"VALUE": num(-1)}, {"VARIABLE": ["生命", lv]}), s.b("control_wait", {"DURATION": pos(1)})]))}),
    s.b("control_if", {"CONDITION": boo(s.b("operator_lt", {"OPERAND1": var_in("生命", lv), "OPERAND2": txt(1)})),
        "SUBSTACK": sub(s.stack([s.b("looks_sayforsecs", {"MESSAGE": txt("遊戲結束"), "SECS": num(1)}), s.b("control_stop", fields={"STOP_OPTION": ["all", None]}, mutation={"tagName": "mutation", "children": [], "hasnext": "false"})]))}),
])
s.stack([s.b("event_whenflagclicked"), s.b("motion_gotoxy", {"X": num(0), "Y": num(-130)}), s.b("data_setvariableto", {"VALUE": txt(3)}, {"VARIABLE": ["生命", lv]}),
         s.b("data_showvariable", fields={"VARIABLE": ["生命", lv]}), s.b("control_forever", {"SUBSTACK": sub(loop)})], 40, 40)
p.sprite("小島民", s, HERO(), y=-130, size=70, comments=[NOTE("按綠旗，用左右鍵躲開掉下來的敵人。\n碰到敵人生命 -1，生命用完遊戲結束。\n\n挑戰：\n① 加上下鍵移動。\n② 把等待 1 秒拿掉，碰一下會扣幾條命？", 520)])
e = Script()
fall = e.stack([e.b("motion_changeyby", {"DY": num(-5)}),
    e.b("control_if", {"CONDITION": boo(e.b("operator_lt", {"OPERAND1": rep(e.b("motion_yposition"), 4), "OPERAND2": num(-170)})),
        "SUBSTACK": sub(e.b("motion_gotoxy", {"X": rep(e.b("operator_random", {"FROM": num(-220), "TO": num(220)}), 4), "Y": num(170)}))})])
e.stack([e.b("event_whenflagclicked"), e.b("motion_gotoxy", {"X": num(0), "Y": num(170)}), e.b("control_forever", {"SUBSTACK": sub(fall)})], 40, 40)
p.sprite("敵人", e, [costume("敵人", enemy_svg(), 40, 40)], y=170, size=80)
p.save()
lab("if-gameloop", "躲避遊戲", ["按綠旗：用左右鍵移動小島民", "敵人從上面掉下來，碰到會扣 1 條命，生命用完就結束"], ["加上「上、下鍵」移動", "拿掉「等待 1 秒」，碰一下會扣幾條命？為什麼？"])

# ================= 10 函式積木島 =================
p = Proj("my-define", "函式積木島：畫多邊形"); p.ext.add("pen"); s = Script()
ids = '["arg_n","arg_len"]'; names = '["邊數","邊長"]'; defaults = '["",""]'; proc = "畫多邊形 %s %s"
proto = s.b("procedures_prototype", {}, shadow=True, mutation={"tagName": "mutation", "children": [], "proccode": proc, "argumentids": ids, "argumentnames": names, "argumentdefaults": defaults, "warp": "false"})
argn = s.b("argument_reporter_string_number", fields={"VALUE": ["邊數", None]}, shadow=True)
proto_in = {"arg_n": [1, s.b("argument_reporter_string_number", fields={"VALUE": ["邊數", None]}, shadow=True)], "arg_len": [1, s.b("argument_reporter_string_number", fields={"VALUE": ["邊長", None]}, shadow=True)]}
s.blocks[proto]["inputs"] = proto_in
for v in proto_in.values(): s.blocks[v[1]]["parent"] = proto
del s.blocks[argn]
defn = s.b("procedures_definition", {"custom_block": [1, proto]})
r_len = s.b("argument_reporter_string_number", fields={"VALUE": ["邊長", None]})
r_n1 = s.b("argument_reporter_string_number", fields={"VALUE": ["邊數", None]})
r_n2 = s.b("argument_reporter_string_number", fields={"VALUE": ["邊數", None]})
body = s.stack([s.b("motion_movesteps", {"STEPS": rep(r_len, 4)}), s.b("motion_turnright", {"DEGREES": rep(s.b("operator_divide", {"NUM1": num(360), "NUM2": rep(r_n2, 4)}), 4)})])
s.stack([defn, s.b("pen_penDown"), s.b("control_repeat", {"TIMES": rep(r_n1, 6), "SUBSTACK": sub(body)}), s.b("pen_penUp")], 40, 300)
def call(n, l):
    return s.b("procedures_call", {"arg_n": txt(n), "arg_len": txt(l)}, mutation={"tagName": "mutation", "children": [], "proccode": proc, "argumentids": ids, "warp": "false"})
s.stack([s.b("event_whenflagclicked"), s.b("pen_clear"), s.b("motion_gotoxy", {"X": num(-150), "Y": num(0)}), s.b("motion_pointindirection", {"DIRECTION": ang(90)}),
         call(3, 100), s.b("motion_gotoxy", {"X": num(30), "Y": num(-40)}), call(6, 50)], 40, 40)
p.sprite("小島民", s, HERO(), size=40, comments=[NOTE("按綠旗：同一顆自訂積木，換參數畫出三角形和六邊形。\n下面是「定義」，上面是「呼叫」。\n\n挑戰：\n① 再呼叫一次畫正方形（4, 80）。\n② 呼叫畫 36 邊、邊長 10，會變成什麼？", 460)])
p.save()
lab("my-define", "畫多邊形", ["按綠旗：同一顆「畫多邊形」積木畫出三角形和六邊形", "下面是定義，上面是呼叫，參數不同畫出的圖就不同"], ["再呼叫一次「畫多邊形 4 80」", "呼叫「畫多邊形 36 10」，畫出來像什麼？"])

json.dump(LABS, open(os.path.join(OUT, 'labs.json'), 'w'), ensure_ascii=False, indent=1)
print(len(LABS), 'projects ->', OUT)
