import lang
import os.path
import json
import struct
import logging
import threading
import multiprocessing
import binascii
#import atexit
from tkinter import *
from tkinter import messagebox, Entry
from tkinter import filedialog
from typing import Dict, Any
#from pathlib import Path
#from playsound import playsound

# 日誌等級
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# 全局遊戲數據
game_data = {}
# 存檔文件位置(R1存檔1, R2存檔2, R3存檔3)
save_file_path = ""
# 動態數據文件位置(D1存檔1, D2存檔2, D3存檔3)
dync_file_path = ""
# 遊戲數據文件位置(Z.dat)
zdata_file_path = ""

# 設定主角開局屬性
# 從data.json中加載屬性地址
char_attributes_address = {}
char_attributes_value: Dict[str, int] = {}
# 主角姓名(big编码)
char_name_main=""
char_name_address=0x034c
char_name_maxcount=3
char_home_name_address=0x1896E

# 主角位置
char_position_address=0x04
char_position=[]
# 全地圖位置，坐標為[x,y]數組
map_positions={}

# 商人位置坐標
merc_position=""
merchant_positions={}

# 中毒除數(遊戲算法數值，不在存檔中)
zdata_venom_divisor_address = 0x3600B
zdata_venom_divisor_value = 0x01
zdata_venom_divisor_desc = ""

# 武功(區分大小寫)
# 從data.json中加載武功地址
martial_arts_names = {}
# 武功最大數
char_martial_maxcount = 10
# 武功種類起始地址和步進
char_martial_type_start_address = 0x3C2
char_martial_type_address_step = 0x02
char_martial_type_list: [int] = []
# 武功等級起始地址和步進
# 武功等級: 0x8503 10級 (註：short是逆序寫入 little endian)
char_martial_tier_start_address = 0x3D6
char_martial_tier_address_step = 0x02
char_martial_tier_list: [int] = []

# 隊友
# 從data.json中加載隊友地址
team_members_names = {}
team_members_maxcount = 6
team_members_start_address = 0x18
team_members_address_step = 0x02
team_members_list: [str] = []
team_members_desc = ""

# 戰鬥事件
battle_events = []
battle_events_desc = ""

# 音樂進程
p_music = None

# 主窗口
root = None


# 武功等級轉換(從經驗值到級別)
def martial_ladder_from_tier(tier):
    return tier // 100 + 1


# 武功等級轉換(從級別到經驗值)
def martial_tier_from_ladder(ladder):
    tier = (int(ladder) - 1) * 100 + 1
    return tier


# 武功名稱轉換(從數值到名稱)
def martial_name_from_type(type):
    martial_arts_key = "0x{:02X}".format(type)
    return martial_arts_names[martial_arts_key]


# 武功名稱轉換(從名稱到數值)
def martial_type_from_name(name):
    for key, val in martial_arts_names.items():
        if val == name:
            return int(key, 16)
    return 0x00


# 主函數，不用在乎函數定義順序
def main_entry_point():
    # atexit.register(on_exit)

    #changes the default process start method to 'spawn' instead of 'fork' on macOS.
    multiprocessing.set_start_method('spawn')
    play_sound()

    # 取得上回存檔位置
    retrieve_path_data()
    show_main_window()


def char_window_btn_refresh():
    retrieve_character()

    # 重設姓名
    input = root.input_char_name
    reset_char_item(input, char_name_main)

    # 重設位置
    input = root.input_char_pos
    reset_char_pos(input, char_position)

    # 重設屬性
    for key, val in char_attributes_value.items():
        input = root.input_attrs[key]
        reset_char_item(input, val)

    # 重設武功列表
    for x in range(0, char_martial_maxcount):
        type = char_martial_type_list[x]
        tier = char_martial_tier_list[x]
        input = root.input_martial[x]
        reset_martial_list_item(input, type, tier)

    # 重設隊友列表
    for x in range(0, team_members_maxcount):
        member = team_members_list[x]
        input = root.input_team[x]
        reset_team_list_member(input, member)

    # 重設商人位置
    input = root.input_merc_pos
    reset_merc_pos(input, merc_position)

    # 重置中毒除數
    reset_data_item(root.input_venom_divisor, zdata_venom_divisor_value)

    root.label_status.set(lang.TXT_SAVE_REFRESHED)


# 重置單個屬性
def reset_char_item(input, text):
    input.delete(0, END)
    input.insert(0, text)

# 重置主角位置
def reset_char_pos(mp, position):
    name = retrieve_map_name(position)
    options = mp
    options.set(name)

# 重置商人位置
def reset_merc_pos(mp, position):
    name = position
    options = mp
    options.set(name)

# 重置單個武功
def reset_martial_list_item(mp, type, tier):
    name = martial_name_from_type(type)
    text = martial_ladder_from_tier(tier)
    options = mp[0]
    options.set(name)
    input = mp[1]
    input.delete(0, END)
    input.insert(0, text)

# 重置單個隊友
def reset_team_list_member(mp, member):
    options = mp
    options.set(member)

# 重置單個數據
def reset_data_item(input, text):
    input.delete(0, END)
    input.insert(0, text)

# 取得單個屬性值
def retrieve_char_item(input):
    value = input.get()
    return int(value)

# 取得姓名
def retrieve_char_name(input):
    value = input.get()
    return value

# 取得商人位置
def retrieve_merc_pos(mp):
    options = mp
    name = options.get()
    return name

# 取得單個武功的值
def retrieve_martial_list_item(mp):
    options = mp[0]
    name = martial_type_from_name(options.get())
    input = mp[1]
    text = martial_tier_from_ladder(input.get())
    return name, text

# 取得單個隊友名字
def retrieve_team_list_member(mp):
    options = mp
    name = options.get()
    return name

# 取得單個數據值
def retrieve_data_item(input):
    value = input.get()
    return int(value)

# 取得地圖坐標
def retrieve_map_pos(mp):
    options = mp
    name = options.get()
    return map_positions[name]

# 取得地圖位置名
def retrieve_map_name(position):
    for key, val in map_positions.items():
        if val[0] == position[0] and val[1] == position[1]:
            return key
    pos = ""
    #pos = next(iter(map_positions))
    for key in map_positions:
        pos = key
        break
    # 自由位置，需要重設位置坐標
    map_positions[pos] = position
    return pos

def char_window_btn_write():
    global char_name_main
    global char_position
    global char_attributes_value
    global merc_position
    global zdata_venom_divisor_value

    # 读取姓名
    input = root.input_char_name
    char_name_main = retrieve_char_name(input)

    # 讀取地址
    input = root.input_char_pos
    char_position = retrieve_map_pos(input)

    # 讀取全部屬性
    for key, val in char_attributes_value.items():
        input = root.input_attrs[key]
        char_attributes_value[key] = retrieve_char_item(input)

    # 讀取武功列表
    for x in range(0, char_martial_maxcount):
        input = root.input_martial[x]
        (type, tier) = retrieve_martial_list_item(input)
        char_martial_type_list[x] = type
        char_martial_tier_list[x] = tier
        # logging.debug("武功%d種類 %s 經驗 %s" % (x+1, '0x{:02X}'.format(type), hex(tier)))

    # 讀取隊友列表
    for x in range(0, team_members_maxcount):
        input = root.input_team[x]
        member = retrieve_team_list_member(input)
        team_members_list[x] = member

    # 讀取商人位置
    input = root.input_merc_pos
    merc_position = retrieve_merc_pos(input)

    # 讀取中毒除數
    zdata_venom_divisor_value = retrieve_data_item(root.input_venom_divisor)

    # 寫入存檔
    rewrite_character()
    root.label_status.set(lang.TXT_SAVE_WRITEN)


def battle_window_btn_close():
    global root
    root.destroy()
    show_main_window()

def char_window_btn_close():
    global root
    root.destroy()
    show_main_window()

# 生成人物單個屬性輸入框
def create_sub_character_input(parent_pane, desc, text, desc_width=6, text_width=6):
    pane = Frame(parent_pane)
    pane.pack(fill=X, expand=True, padx=10, pady=2)
    label = Label(pane, text=desc, width=desc_width)
    label.pack(side=LEFT, fill=BOTH, expand=True)
    input = Entry(pane, width=text_width)
    input.pack(side=RIGHT, fill=BOTH, expand=True)
    input.insert(0, text)
    return input


# 生成人物單個武功輸入框
def create_sub_martial_input(parent_pane, type, tier, type_width=10, tier_width=6):
    pane = Frame(parent_pane)
    pane.pack(fill=X, expand=True, padx=10, pady=2)
    # 讓武功成為選擇列表，而不是輸入
    '''
    input_type = Entry(pane)
    input_type.pack(side=LEFT, fill=BOTH, expand=True)
    input_type.insert(0, type)
    '''
    options = StringVar(root)
    options.set(type)
    # [value for value in martial_arts_names.values()]
    dp = OptionMenu(pane, options, *martial_arts_names.values())
    dp.config(width=type_width)
    dp.pack(side=LEFT, fill=BOTH, expand=True)

    input_tier = Entry(pane, width=tier_width)
    input_tier.pack(side=RIGHT, fill=BOTH, expand=True)
    input_tier.insert(0, tier)
    return options, input_tier

# 生成單個隊友列表
def create_sub_team_menu(parent_pane, member, width=10):
    pane = Frame(parent_pane)
    pane.pack(fill=X, expand=True, padx=10, pady=2)
    options = StringVar(root)
    options.set(member)
    dp = OptionMenu(pane, options, *team_members_names.keys())
    dp.config(width=width)
    dp.pack(side=TOP, fill=BOTH, expand=True)
    return options

# 生成人物地圖位置列表
def create_sub_char_pos_menu(parent_pane, desc, position, desc_width=6, pos_width=6):
    pane = Frame(parent_pane)
    pane.pack(fill=X, expand=True, padx=10, pady=2)
    label = Label(pane, text=desc, width=desc_width)
    label.pack(side=LEFT, fill=BOTH, expand=True)

    options = StringVar(root)
    options.set(retrieve_map_name(position))
    dp = OptionMenu(pane, options, *map_positions.keys())
    dp.config(width=pos_width)
    dp.pack(side=RIGHT, fill=BOTH, expand=True)
    return options

# 生成商人地圖位置列表
def create_sub_merc_pos_menu(parent_pane, desc, pos, desc_width=6, pos_width=6):
    pane = Frame(parent_pane)
    pane.pack(fill=X, expand=True, padx=10, pady=2)
    label = Label(pane, text=desc, width=desc_width)
    label.pack(side=TOP, fill=BOTH, expand=True)
    options = StringVar(root)
    options.set(pos)
    dp = OptionMenu(pane, options, *merchant_positions.keys())
    dp.config(width=pos_width)
    dp.pack(side=BOTTOM, fill=BOTH, expand=True)
    return options

# 創建戰鬥事件標題欄
def create_sub_battle_heading(parent_pane, title_width, status_width, desc_width):
    pane = Frame(parent_pane)
    pane.pack(fill=X, expand=True, padx=4, pady=0)

    label = Label(pane, text=lang.TXT_BTL_HEADER_RESET, padx=4, pady=2, width=6, font=lang.FONT_BTL_HEADER)
    label.pack(side=LEFT, fill=X, expand=True)
    label = Label(pane, text=lang.TXT_BTL_HEADER_DESC, padx=2, pady=2, width=desc_width, font=lang.FONT_BTL_HEADER)
    label.pack(side=RIGHT, fill=X, expand=True)
    label = Label(pane, text=lang.TXT_BTL_HEADER_STATUS, padx=2, pady=2, width=status_width, font=lang.FONT_BTL_HEADER)
    label.pack(side=RIGHT, fill=X, expand=True)
    label = Label(pane, text=lang.TXT_BTL_HEADER_TITLE, padx=2, pady=2, width=title_width, font=lang.FONT_BTL_HEADER)
    label.pack(side=RIGHT, fill=X, expand=True)

def check_sub_battle(check):
    val = check.get()
    #print(val)

def reset_sub_battle_check(check, status, willchange, doable):
    check.set(willchange)
    if doable:
        status.config(text=lang.TXT_BTL_DOABLE)
        status.config(fg="green")
    else:
        status.config(text=lang.TXT_BTL_NOT_DOABLE)
        status.config(fg="gray")

# 生成單個戰鬥選擇項
def create_sub_battle_check(parent_pane, on_image, off_image, title, desc, willchange, doable, title_width=6, status_width=6, desc_width=6):
    pane = Frame(parent_pane)
    pane.pack(fill=X, expand=True, padx=4, pady=2)

    # 選擇
    chk_pane = Frame(pane, bg="grey")
    chk_pane.pack(side=LEFT, fill=X, expand=True, padx=18, pady=0)
    check = IntVar(root)
    chk_button = Checkbutton(chk_pane, image=off_image, selectimage=on_image, indicatoron=False,
                            command=lambda: check_sub_battle(check),
                            onvalue=1, offvalue=0, variable=check)
    chk_button.pack(fill=BOTH, expand=True)

    # 說明
    label_desc = Label(pane, text=desc, padx=2, pady=0, width=desc_width)
    label_desc.pack(side=RIGHT, fill=BOTH, expand=True)

    # 可戰狀態
    label_status = Label(pane, padx=2, pady=0, width=status_width)
    label_status.pack(side=RIGHT, fill=BOTH, expand=True)

    # 設定狀態
    reset_sub_battle_check(check, label_status, willchange, doable)

    # 標題
    label_title = Label(pane, text=title, padx=2, pady=0, width=title_width)
    label_title.pack(side=RIGHT, fill=BOTH, expand=True)

    return check, label_status

# 刷新戰鬥事件所有控件
def battle_window_btn_refresh():
    retrieve_battle()
    # 刷新重置和戰鬥狀態
    for x in range(0, len(battle_events)):
        (check, status) = root.input_battles[x]
        battle = battle_events[x]
        doable = battle["doable"]
        willchange = battle["willchange"]
        reset_sub_battle_check(check, status, willchange, doable)

    root.label_status.set(lang.TXT_SAVE_REFRESHED)

# 重置戰鬥事件
def battle_window_btn_reset():
    # 取得全部重置事件
    for x in range(0, len(battle_events)):
        (check, status) = root.input_battles[x]
        battle = battle_events[x]
        battle["willchange"] = check.get()

    # 寫入戰鬥事件數據
    rewrite_battle()
    root.label_status.set(lang.TXT_SAVE_WRITEN)

    # 刷新數據
    t = threading.Thread(target=battle_window_btn_refresh)
    t.start()

# 顯示戰鬥事件窗口
def show_battle_window():
    global root
    root = Tk()
    root.title(lang.TITLE_BATTLE_DATA)
    root.resizable(0, 0)

    # check image
    on_image = PhotoImage(width=36, height=18)
    off_image = PhotoImage(width=36, height=18)
    on_image.put(("green",), to=(1, 1, 17, 17))
    off_image.put(("red",), to=(18, 1, 35, 17))

    # paned window
    pane = Frame(root)
    pane.pack(fill=BOTH, expand=True, padx=0, pady=0)

    # 事件面板
    pane_battle = LabelFrame(pane, text=lang.TXT_BATTLE_LST)
    pane_battle.pack(side=LEFT, fill=BOTH, expand=True, padx=(10,2), pady=(4,8))

    # 方法說明與按鈕
    pane_battle_ctrl = Frame(pane)
    pane_battle_ctrl.pack(side=RIGHT, fill=Y, expand=True, padx=(2, 10), pady=(4,8))

    # 標題欄
    pane_heading = Frame(pane_battle)
    pane_heading.pack(side=TOP, fill=X, expand=True, padx=0, pady=0)
    create_sub_battle_heading(pane_heading, 16, 8, 30)

    # 展示全部戰鬥事件
    root.input_battles = []
    for battle in battle_events:
        title = battle["title"]
        description = battle["description"]
        doable = battle["doable"]
        willchange = battle["willchange"]
        # 返回check var和status label
        (check, status) = create_sub_battle_check(pane_battle, on_image, off_image, title, description, willchange, doable, 18, 8, 30)
        root.input_battles.append((check, status))

    pane = Frame(pane_battle)
    pane.pack(fill=X, expand=True, padx=10, pady=2)

    # 關於戰鬥事件的說明
    pane_battle_desc = LabelFrame(pane_battle_ctrl, text=lang.TXT_BATTLE_DESC)
    pane_battle_desc.pack(side=TOP, expand=False)
    msg = Message(pane_battle_desc, text=battle_events_desc)
    msg.pack(side=TOP, fill=X, expand=False, padx=5, pady=5)

    # 下側按鈕
    pane = Frame(pane_battle_ctrl)
    pane.pack(side=TOP, fill=X, expand=False, padx=10, pady=(5, 8))

    label_status = StringVar()
    label_status.set(lang.TXT_SAVE_LOADED)
    label = Label(pane, textvariable=label_status)
    label.pack(side=TOP, fill=X, expand=False, padx=5, pady=10)
    root.label_status = label_status

    # 返回，写入，刷新
    btn = Button(pane, text=lang.BTN_REFRESH, command=battle_window_btn_refresh)
    btn.pack(side=TOP, fill=BOTH, expand=True, padx=10, pady=5)
    btn = Button(pane, text=lang.BTN_RESET, command=battle_window_btn_reset)
    btn.pack(side=TOP, fill=BOTH, expand=True, padx=10, pady=5)
    btn = Button(pane, text=lang.BTN_RETURN, command=battle_window_btn_close)
    btn.pack(side=TOP, fill=BOTH, expand=True, padx=10, pady=5)

    root.protocol("WM_DELETE_WINDOW", battle_window_btn_close)
    root.update_idletasks()  # Update "requested size" from geometry manager
    root.geometry("+%d+%d" % ((root.winfo_screenwidth() - root.winfo_reqwidth()) / 2,
                              (root.winfo_screenheight() - root.winfo_reqheight()) / 2))
    root.mainloop()

# 顯示人物屬性窗口
def show_character_window():
    global root
    root = Tk()
    root.title(lang.TITLE_CHAR_DATA)
    root.resizable(0, 0)

    # paned window
    pane = Frame(root)
    pane.pack(fill=BOTH, expand=True, padx=0, pady=0)

    # 做側面板
    pane_left = Frame(pane)
    pane_left.pack(side=LEFT, fill=Y, expand=True, padx=10, pady=10)

    # 右側面板
    pane_right = Frame(pane)
    pane_right.pack(side=RIGHT, fill=Y, expand=True, padx=10, pady=10)

    # 中間面板
    pane_middle = Frame(pane)
    pane_middle.pack(side=RIGHT, fill=Y, expand=True, padx=10, pady=10)

    # 左側人物數據
    pane_char = LabelFrame(pane_left, text=lang.TXT_CHAR_DATA)
    pane_char.pack(side=TOP, fill=BOTH, expand=True, padx=0, pady=(0, 2))

    # 中側上方武功列表
    pane_martial = LabelFrame(pane_middle, text=lang.TXT_ATTACK_LST)
    pane_martial.pack(side=TOP, fill=BOTH, expand=True, padx=0, pady=(0, 2))

    # 中側下方隊友列表
    pane_team = LabelFrame(pane_middle, text=lang.TXT_MEMBER_LST)
    pane_team.pack(side=BOTTOM, fill=BOTH, expand=True, padx=0, pady=(2, 2))

    # 右侧上方主角設定
    pane_char_setting = LabelFrame(pane_right, text=lang.TXT_MAIN_SETTING)
    pane_char_setting.pack(side=TOP, fill=BOTH, expand=True, padx=0, pady=(0, 2))

    # 右側下方關於隊友的說明
    pane_team_desc = LabelFrame(pane_right, text=lang.TXT_MEMBER_DESC)
    pane_team_desc.pack(side=BOTTOM, fill=BOTH, expand=True, padx=0, pady=(4, 2))

    # 右側中間毒性增強
    pane_venom = LabelFrame(pane_right, text=lang.TXT_VENOM_ENHANCE)
    pane_venom.pack(side=BOTTOM, fill=BOTH, expand=True, padx=0, pady=(2, 2))

    # 右側商人位置
    pane_merchant = LabelFrame(pane_right, text=lang.TXT_MERCHANT_POS)
    pane_merchant.pack(side=BOTTOM, fill=BOTH, expand=True, padx=0, pady=(2, 2))

    # 每一個輸入框都變成root的一個屬性，方面後面取值
    # 左側人物屬性列表
    root.input_attrs = {}
    for key, val in char_attributes_value.items():
        input = create_sub_character_input(pane_char, key, val)
        root.input_attrs[key] = input

    pane = Frame(pane_char)
    pane.pack(fill=X, expand=True, padx=10, pady=2)

    # 中间武功列表
    pane = Frame(pane_martial)
    pane.pack(side=TOP, fill=BOTH, expand=True, padx=10, pady=2)
    label = Label(pane, text=lang.TXT_ATTACK, width=14)
    label.pack(side=LEFT, fill=BOTH, expand=True)
    label = Label(pane, text=lang.TXT_LEVEL, width=6)
    label.pack(side=RIGHT, fill=BOTH, expand=True)

    pane = Frame(pane_martial)
    pane.pack(fill=X, expand=True)
    # 10種武功(返回:選擇武功, 等級輸入框)
    root.input_martial = []
    for x in range(0, char_martial_maxcount):
        type = char_martial_type_list[x]
        tier = char_martial_tier_list[x]
        input = create_sub_martial_input(pane, martial_name_from_type(type), martial_ladder_from_tier(tier), type_width=12)
        root.input_martial.append(input)

    pane = Frame(pane_martial)
    pane.pack(fill=X, expand=True, padx=10, pady=2)

    # 中間隊友列表
    pane = Frame(pane_team)
    pane.pack(fill=X, expand=True, padx=10, pady=2)
    label = Label(pane, text=lang.TXT_TEAM, width=6)
    label.pack(side=TOP, fill=BOTH, expand=True)

    pane = Frame(pane_team)
    pane.pack(fill=X, expand=True)
    root.input_team = []
    for x in range(0, team_members_maxcount):
        member = team_members_list[x]
        input = create_sub_team_menu(pane, member)
        root.input_team.append(input)

    pane = Frame(pane_team)
    pane.pack(fill=X, expand=True, padx=10, pady=2)

    # 右侧主角姓名
    pane = Frame(pane_char_setting)
    pane.pack(fill=X, expand=True, padx=10, pady=2)
    label = Label(pane, text=lang.TXT_MAIN_DESC, width=16)
    label.pack(side=TOP, fill=BOTH, expand=True)

    input = create_sub_character_input(pane_char_setting, lang.TXT_NAME, char_name_main, 6, 10)
    root.input_char_name = input
    pane = Frame(pane_char_setting)
    pane.pack(side=TOP, fill=X, expand=True, padx=0, pady=2)

    # 右側主角位置
    input = create_sub_char_pos_menu(pane_char_setting, lang.TXT_POSITION, char_position, 6, 8)
    root.input_char_pos = input
    pane = Frame(pane_char_setting)
    pane.pack(side=BOTTOM, fill=X, expand=True, padx=0, pady=(0, 2))

    pane = Frame(pane_char_setting)
    pane.pack(fill=X, expand=True, padx=10, pady=2)

    # 商人位置設定
    input = create_sub_merc_pos_menu(pane_merchant, lang.TXT_MERC_POSITION, merc_position)
    root.input_merc_pos = input
    pane = Frame(pane_merchant)
    pane.pack(fill=X, expand=True, padx=10, pady=(0, 4))

    # 毒性增強設定
    label = Label(pane_venom, text=zdata_venom_divisor_desc)
    label.pack(side=TOP, fill=BOTH, expand=True)
    input = create_sub_character_input(pane_venom, lang.TXT_VENOM_DIVISOR, zdata_venom_divisor_value)
    root.input_venom_divisor = input

    # 關於隊友的說明
    msg = Message(pane_team_desc, text=team_members_desc)
    msg.pack(side=BOTTOM, fill=BOTH, anchor=W, expand=True)

    # 下側按鈕
    pane = Frame(root)
    pane.pack(fill=X, expand=False, padx=10, pady=(3, 10))

    label_status = StringVar()
    label_status.set(lang.TXT_SAVE_LOADED)
    label = Label(pane, textvariable=label_status)
    label.pack(side=LEFT, fill=BOTH, expand=True)
    root.label_status = label_status

    # 返回，写入，刷新
    btn = Button(pane, text=lang.BTN_RETURN, command=char_window_btn_close)
    btn.pack(side=RIGHT, fill=BOTH, expand=True, padx=4)
    btn = Button(pane, text=lang.BTN_WRITE, command=char_window_btn_write)
    btn.pack(side=RIGHT, fill=BOTH, expand=True, padx=4)
    btn = Button(pane, text=lang.BTN_REFRESH, command=char_window_btn_refresh)
    btn.pack(side=RIGHT, fill=BOTH, expand=True, padx=4)

    root.protocol("WM_DELETE_WINDOW", char_window_btn_close)
    root.update_idletasks()  # Update "requested size" from geometry manager
    root.geometry("+%d+%d" % ((root.winfo_screenwidth() - root.winfo_reqwidth()) / 2,
                              (root.winfo_screenheight() - root.winfo_reqheight()) / 2))
    root.mainloop()

# 退出程序
def on_exit():
    # 必須停止音樂(因為有子進程)
    stop_sound()
    # 關閉窗口
    main_window_btn_close()

# 關閉主窗口
def main_window_btn_close():
    # 不主動停止音樂
    global root
    root.destroy()

# 保存全部文件路徑
def save_all_paths():
    err = ""
    save_path = root.input_save_path.get()
    if not os.path.exists(save_path):
        err = lang.ERR_SAVE_NOT_EXIST
        root.input_save_status.set(err)
        logging.error(err)
        return False
    root.input_save_status.set(err)

    dync_path = root.input_dync_path.get()
    if not os.path.exists(dync_path):
        err = lang.ERR_DYNC_NOT_EXIST
        root.input_dync_status.set(err)
        logging.error(err)
        return False
    root.input_dync_status.set(err)

    zdata_path = root.input_zdata_path.get()
    if not os.path.exists(zdata_path):
        err = lang.ERR_DATA_NOT_EXIST
        root.input_zdata_status.set(err)
        logging.error(err)
        return False
    root.input_zdata_status.set(err)

    dump_save_path(save_path, dync_path, zdata_path)
    return True

# 修改戰鬥事件
def main_window_btn_mod_battle():
    # 保存全部文件路徑
    save = save_all_paths()
    if not save:
        return

    # 取得遊戲信息
    retrieve_game_data()

    # 取得戰鬥事件信息
    retrieve_battle()

    # 打開戰鬥事件窗口
    main_window_btn_close()
    show_battle_window()

# 修改人物相關
def main_window_btn_mod_char():
    # 保存全部文件路徑
    save = save_all_paths()
    if not save:
        return

    # 取得遊戲信息
    retrieve_game_data()

    # 取得人物信息
    retrieve_character()

    # 打開人物窗口
    main_window_btn_close()
    show_character_window()


# 生成通用單個屬性輸入框
def create_sub_path_input(parent_pane, desc, text, btn_command):
    pane = Frame(parent_pane)
    pane.pack(fill=X, expand=True, padx=(5,0), pady=2)

    pane_info = Frame(pane)
    pane_info.pack(side=TOP, fill=X, expand=True)

    label = Label(pane_info, text=desc)
    label.pack(side=LEFT, anchor=NW)

    # 提示文件狀態
    label_status = StringVar()
    label_status.set("")
    label = Label(pane_info, textvariable=label_status)
    label.pack(side=RIGHT)

    pane = Frame(pane)
    pane.pack(side=BOTTOM, fill=X, expand=True)

    input = Entry(pane)
    input.pack(side=LEFT, fill=BOTH, expand=True)
    input.insert(0, text)
    #input.config(state="disabled")

    btn = Button(pane, text=lang.BTN_SELECT, width=8, command=btn_command)
    btn.pack(side=RIGHT, fill=X, expand=False, padx=(8))

    return label_status, input


# 選擇存檔文件位置
def main_window_select_save_file():
    global save_file_path
    path = filedialog.askopenfilename(defaultextension=".grp", filetypes=[(lang.TXT_SAVE_PATH, "*.GRP")], multiple=False, title=lang.TITLE_SAVE_PATH_SEL)
    if not path:
        return
    save_file_path = path
    root.input_save_path.delete(0, END)
    root.input_save_path.insert(0, save_file_path)
    # 保存
    dump_save_path(save_file_path, dync_file_path, zdata_file_path)

# 選擇動態數據文件
def main_window_select_dync_file():
    global dync_file_path
    path = filedialog.askopenfilename(defaultextension=".grp", filetypes=[(lang.TXT_DYNC_PATH, "*.GRP")], multiple=False, title=lang.TITLE_DYNC_PATH_SEL)
    if not path:
        return
    dync_file_path = path
    root.input_dync_path.delete(0, END)
    root.input_dync_path.insert(0, dync_file_path)
    # 保存
    dump_save_path(save_file_path, dync_file_path, zdata_file_path)

# 選擇數據文件位置
def main_window_select_zdata_file():
    global zdata_file_path
    path = filedialog.askopenfilename(defaultextension=".dat", filetypes=[(lang.TXT_DATA_PATH, "*.DAT")], multiple=False, title=lang.TITLE_DATA_PATH_SEL)
    if not path:
        return
    zdata_file_path = path
    root.input_zdata_path.delete(0, END)
    root.input_zdata_path.insert(0, zdata_file_path)
    # 保存
    dump_save_path(save_file_path, dync_file_path, zdata_file_path)


# 顯示存檔窗口
def show_main_window():
    global root
    root = Tk()
    root.title(lang.TITLE_APP)

    '''
    root.minsize(width=400, height=0) 
    root.maxsize(width=300, height=300)
    '''
    root.resizable(0, 0)

    img = PhotoImage(file='img/logo.png')
    Label(root, image=img).pack(fill=BOTH, expand=True)

    pane = Frame(root)
    pane.pack(fill=X, expand=True, padx=5, pady=(5, 5))

    # 返回(文件狀態,文件路徑)
    input: Entry
    (status, input) = create_sub_path_input(pane, lang.TXT_SAVE_PATH, save_file_path, main_window_select_save_file)
    root.input_save_path = input
    root.input_save_status = status

    # 返回(文件狀態,文件路徑)
    input: Entry
    (status, input) = create_sub_path_input(pane, lang.TXT_DYNC_PATH, dync_file_path, main_window_select_dync_file)
    root.input_dync_path = input
    root.input_dync_status = status

    # 返回(文件狀態,文件路徑)
    (status, input) = create_sub_path_input(pane, lang.TXT_DATA_PATH, zdata_file_path, main_window_select_zdata_file)
    root.input_zdata_path = input
    root.input_zdata_status = status

    pane = Frame(root)
    pane.pack(fill=X, expand=True, padx=5, pady=(5, 5))

    # 音樂標籤
    music = IntVar(root)
    music.set(1)
    chk_music = Checkbutton(pane, text=lang.TXT_PLAY_MUSIC, variable=music,
                            command=lambda: check_play_sound())
    chk_music.pack(side=LEFT, anchor=NW, expand=False, padx=(5, 2))
    root.music_status = music

    # 下方按鈕
    pane = Frame(pane)
    pane.pack(side=RIGHT, fill=X, expand=False, padx=10)

    btn = Button(pane, text=lang.BTN_MOD_BATTLE, width=8, command=main_window_btn_mod_battle)
    btn.pack(side=LEFT, fill=BOTH, expand=True, padx=4)

    btn = Button(pane, text=lang.BTN_MOD_CHAR, width=8, command=main_window_btn_mod_char)
    btn.pack(side=LEFT, fill=BOTH, expand=True, padx=4)

    btn = Button(pane, text=lang.BTN_CLOSE, width=8, command=on_exit)
    btn.pack(side=RIGHT, fill=BOTH, expand=True, padx=4)

    # 版權
    label = Label(root, text=lang.TXT_COPYRIGHT)
    label.pack(side=TOP, fill=BOTH, expand=True, padx=10, pady=(0,5))

    root.protocol("WM_DELETE_WINDOW", on_exit)
    root.update_idletasks()  # Update "requested size" from geometry manager
    root.geometry("+%d+%d" % ((root.winfo_screenwidth() - root.winfo_reqwidth()) / 2,
                              (root.winfo_screenheight() - root.winfo_reqheight()) / 2))
    root.mainloop()

# 播放音樂按鈕事件
def check_play_sound():
    status = root.music_status.get()
    if status:
        play_sound()
    else:
        stop_sound()

# 播放音樂
def play_sound():
    global p_music

    relative_path = "snd/sound.mp3"
    #  audio_file_path = Path(relative_path).resolve()
    '''
    if p_music is None:
        # p_music = threading.Thread(target=playsound, args=('snd/sound.mp3',), daemon=True)
        p_music = multiprocessing.Process(target=playsound, args=(relative_path,))
        p_music.start()
    else:
        p_music.terminate()
        p_music = None
    '''

def stop_sound():
    global p_music
    '''
    if p_music is not None:
        p_music.terminate()
        p_music = None
    '''

#
def retrieve_path_data():
    global game_data
    global save_file_path
    global dync_file_path
    global zdata_file_path
    zdata_file_path = ""
    save_file_path = ""
    dync_file_path = ""
    with open("data.json", "r") as f:
        game_data = json.load(f)
        if "save_file_path" in game_data:
            save_file_path = game_data["save_file_path"]
        if "dync_file_path" in game_data:
            dync_file_path = game_data["dync_file_path"]
        if "zdata_file_path" in game_data:
            zdata_file_path = game_data["zdata_file_path"]

# 讀取全局數據文件
def retrieve_game_data():
    # Read data from file
    global game_data
    global save_file_path
    global dync_file_path
    global zdata_file_path
    global char_name_address
    global char_name_maxcount
    global char_home_name_address
    global char_position_address
    global map_positions
    global merchant_positions
    global char_attributes_address
    global martial_arts_names
    global zdata_venom_divisor_address
    global zdata_venom_divisor_desc
    global char_martial_type_start_address
    global char_martial_type_address_step
    global char_martial_tier_start_address
    global char_martial_tier_address_step
    global char_martial_maxcount
    global team_members_names
    global team_members_maxcount
    global team_members_start_address
    global team_members_address_step
    global team_members_desc
    global battle_events
    global battle_events_desc

    map_positions = {}
    merchant_positions = {}
    char_attributes_address = {}
    martial_arts_names = {}
    team_members_names = {}
    battle_events = []
    zdata_file_path = ""
    save_file_path = ""
    dync_file_path = ""

    with open("data.json", "r") as f:
        game_data = json.load(f)
        if "save_file_path" in game_data:
            save_file_path = game_data["save_file_path"]
        if "dync_file_path" in game_data:
            dync_file_path = game_data["dync_file_path"]
        if "zdata_file_path" in game_data:
            zdata_file_path = game_data["zdata_file_path"]
        if "map_positions" in game_data:
            map_positions = game_data["map_positions"]
        if "merchant_positions" in game_data:
            merchant_positions = game_data["merchant_positions"]
        if "char_attributes_address" in game_data:
            char_attributes_address = game_data["char_attributes_address"]
        if "martial_arts_names" in game_data:
            martial_arts_names = game_data["martial_arts_names"]
        if "team_members_names" in game_data:
            team_members_names = game_data["team_members_names"]
        if "battle_events" in game_data:
            battle_events = game_data["battle_events"]

        for key, val in char_attributes_address.items():
            # 第一次加載的是16進製文字，進行了整形轉換，重新寫入data.json
            # 第二次加載的就是int了，不需要再轉換
            if isinstance(val, int):
                char_attributes_address[key] = val
            else:
                char_attributes_address[key] = int(val, 16)

        for key, val in team_members_names.items():
            # 第一次加載的是16進製文字，進行了整形轉換，重新寫入data.json
            # 第二次加載的就是int了，不需要再轉換
            if isinstance(val, int):
                team_members_names[key] = val
            else:
                team_members_names[key] = int(val, 16)

        for key, val in merchant_positions.items():
            # 第一次加載的是16進製文字，進行了整形轉換，重新寫入data.json
            # 第二次加載的就是int了，不需要再轉換
            if isinstance(val, int):
                merchant_positions[key] = val
            else:
                merchant_positions[key] = int(val, 16)

        char_name_address = int(game_data["char_name_address"], 16)
        char_name_maxcount = int(game_data["char_name_maxcount"])
        char_home_name_address = int(game_data["char_home_name_address"], 16)
        char_position_address = int(game_data["char_position_address"], 16)
        char_martial_type_start_address = int(game_data["char_martial_type_start_address"], 16)
        char_martial_type_address_step = int(game_data["char_martial_type_address_step"], 16)
        char_martial_tier_start_address = int(game_data["char_martial_tier_start_address"], 16)
        char_martial_tier_address_step = int(game_data["char_martial_tier_address_step"], 16)
        char_martial_maxcount = int(game_data["char_martial_maxcount"])
        team_members_start_address = int(game_data["team_members_start_address"], 16)
        team_members_address_step = int(game_data["team_members_address_step"], 16)
        team_members_maxcount = int(game_data["team_members_maxcount"])
        team_members_desc = game_data["team_members_desc"]
        battle_events_desc = game_data["battle_events_desc"]
        zdata_venom_divisor_address = int(game_data["zdata_venom_divisor_address"], 16)
        zdata_venom_divisor_desc = game_data["zdata_venom_divisor_desc"]


# 寫入全局數據文件
# 若想修改原始遊戲編輯數據
# 修改data_local.json文件，然後執行python convert_data.py
# 把data_local.json轉換成data.json unicode化
# 不要直接改data.json
def dump_save_path(save_path, dync_path, zdata_path):
    # Write data to file
    global game_data
    game_data["save_file_path"] = save_path
    game_data["dync_file_path"] = dync_path
    game_data["zdata_file_path"] = zdata_path
    with open("data.json", "w") as f:
        # prevent json from transforming chars to unicode
        json.dump(game_data, f, ensure_ascii=True)

# 讀取戰鬥事件信息():
def retrieve_battle():
    with open(dync_file_path, mode='rb') as f:
        logging.debug("讀取戰鬥事件 開始:")

        for battle in battle_events:
            check = battle["check"]
            pos = check["pos"]
            val = check["val"]
            byte_val = binascii.unhexlify(val)
            byte_len = len(byte_val)
            # 讀取文件原始數據進行比較
            byte_raw = read_file_byte_raw(f, pos, byte_len)
            # 增加doable變量，記錄是否可以戰鬥
            battle["doable"] = (byte_val == byte_raw)
            # 增加willchange變量，記錄是否要重置
            battle["willchange"] = 0
            logging.debug("讀取戰鬥事件 -> %s check(%s(%d)) file(%s) doable(%d)" % (battle["title"], byte_val, byte_len, byte_raw, battle["doable"]))

        logging.debug("讀取戰鬥 完成.")

# 讀取人物數據
def retrieve_character():
    global char_name_main
    global char_position
    global char_attributes_value
    global char_martial_type_list
    global char_martial_tier_list
    global team_members_list

    '''
    struct.unpack('<')
    the short integer is stored in little-endian byte-order(<). 
    If the short integer is stored in big-endian byte-order, 
    then we need to use > character in the format string instead of <.
    '''
    with open(save_file_path, mode='rb') as f:
        logging.debug("讀取人物數據 開始:")

        bytes = read_file_byte_raw(f, char_name_address, char_name_maxcount*2)
        bytes = remove_trailing_zeros(bytes) # 默認存檔中姓名含有0x00，需要去掉
        try:
            char_name_main = bytes.decode("big5_tw")
        except UnicodeDecodeError as e:
            char_name_main = ""
            logging.debug(f"Error: {e}")
        logging.debug("讀取人物姓名 -> %s" % char_name_main)

        posx = read_file_byte(f, char_position_address, 2)
        posy = read_file_byte(f, char_position_address+2, 2)
        char_position.clear()
        char_position.append(posx)
        char_position.append(posy)
        logging.debug("讀取人物位置 -> (%d,%d)" % (posx, posy))

        char_attributes_value = {}
        for key, val in char_attributes_address.items():
            address = char_attributes_address[key]
            value = read_file_byte(f, address, 2)
            char_attributes_value[key] = value
            logging.debug("讀取 -> %s: %d" % (key, value))

        logging.debug("讀取人物武功")
        char_martial_type_list.clear()
        char_martial_tier_list.clear()
        for x in range(0, char_martial_maxcount):
            address = char_martial_type_start_address + x * char_martial_type_address_step
            mtype = read_file_byte(f, address, char_martial_type_address_step)
            char_martial_type_list.append(mtype)
            address = char_martial_tier_start_address + x * char_martial_tier_address_step
            tier = read_file_byte(f, address, char_martial_tier_address_step)
            char_martial_tier_list.append(tier)
            logging.debug(
                "讀取 -> 武功%d: %s 等級 %s" % (x + 1, martial_name_from_type(mtype), martial_ladder_from_tier(tier)))

        logging.debug("讀取隊友列表")
        team_members_list.clear()
        for x in range(0, team_members_maxcount):
            address = team_members_start_address + x * team_members_address_step
            member = read_file_byte(f, address, team_members_address_step, unsigned=True) #註意：隊友數據是無符號short
            for key, value in team_members_names.items():
                if value == member:
                    logging.debug("讀取 -> 隊友%d: %s" % (x + 1, key))
                    team_members_list.append(key)
                    break

    logging.debug("讀取人物數據 完成.")

    logging.debug("讀取動態數據 開始:")
    global merc_position
    with open(dync_file_path, mode='rb') as f:
        for key, val in merchant_positions.items():
            pos = read_file_byte(f, val, 2)
            if pos != 0:
                merc_position = key
                logging.debug("讀取商人位置 -> %s" % merc_position)
                break

    logging.debug("讀取動態數據 完成.")

    logging.debug("讀取遊戲數據 開始:")
    global zdata_venom_divisor_value
    with open(zdata_file_path, mode='rb') as f:
        zdata_venom_divisor_value = read_file_byte(f, zdata_venom_divisor_address, 2)
        logging.debug("讀取 -> 中毒除數: %d" % zdata_venom_divisor_value)

    logging.debug("讀取遊戲數據 完成.")

def remove_trailing_zeros(byte_array):
    """
    Removes trailing zeros from a byte array.

    :param byte_array: The byte array to remove trailing zeros from.
    :type byte_array: bytes
    :return: The byte array without trailing zeros.
    :rtype: bytes
    """
    i = len(byte_array) - 1
    while i >= 0 and byte_array[i] == 0:
        i -= 1
    return byte_array[:i + 1]

def fill_with_holder(byte_array, length, holder=0):
    """
    Fills a bytes object with zeros up to a specified length.

    :param byte_array: The bytes object to fill with zeros.
    :type byte_array: bytes
    :param length: The length to fill the bytes object up to.
    :type length: int
    :return: The filled bytes object.
    :rtype: bytes
    """
    hl = length - len(byte_array)
    if hl < 0:
        byte_array = byte_array[:length]
    elif hl > 0:
        byte_array = byte_array + holder.to_bytes(hl, 'little') #多餘的地方會填充0x00
        # 下面方法會把整個數組填滿holder(不按0x00填充)
        '''
        b = bytearray(hl)
        b[:] = [holder] * hl
        byte_array = byte_array + b
        '''
    return byte_array

# 從文件中讀取字節(金庸大部分數據都是short)
def read_file_byte(f, address, count, unsigned=False):
    f.seek(address)
    binary_data = f.read(count)
    fmt = '<H'  # short
    if count == 2:
        fmt = '<H'
    elif count == 4:
        fmt = '<I'  # integer
    else:
        return 0
    if unsigned:
        fmt = fmt.upper()
    val = struct.unpack(fmt, binary_data)[0]
    return val

def read_file_byte_raw(f, address, count):
    f.seek(address)
    binary_data = f.read(count)
    return binary_data

# 向文件中寫入字節(金庸大部分數據都是short)
def write_file_byte(f, address, count, value, unsigned=False):
    if value < 0:
        return
    f.seek(address)
    # H for unsigned, h for signed
    fmt = 'H'  # short
    if count == 2:
        fmt = 'H'
    elif count == 4:
        fmt = 'I'  # integer
    if unsigned:
        fmt = fmt.upper()
    f.write(struct.pack(fmt, value))

def write_file_byte_raw(f, address, bytes):
    f.seek(address)
    f.write(bytes)

def rewrite_battle():
    logging.debug("重寫戰鬥事件 開始:")

    with open(dync_file_path, 'r+b') as f:
        for battle in battle_events:
            willchange = battle["willchange"]
            if willchange:
                logging.debug("重寫戰鬥事件 -> %s" % (battle["title"]))
                overlays = battle["overlays"]
                for overlay in overlays:
                    for key, val in overlay.items():
                        address = int(key, 16)
                        byte_data = binascii.unhexlify(val)
                        write_file_byte_raw(f, address, byte_data)
                        logging.debug("\t %s -> %s" % (key, byte_data))

    logging.debug("重寫戰鬥事件 完成.")

# 重寫人物數據
def rewrite_character():
    logging.debug("重寫人物數據 開始:")
    with open(save_file_path, 'r+b') as f:
        # seek to the position where the value to be rewritten is
        # ?: boolean
        # h: short
        # l: long
        # i: int
        # f: float
        # q: long long int [1]

        try:
            bigb = char_name_main.encode("big5_tw")
        except UnicodeEncodeError as e:
            bigb = bytes(char_name_maxcount * 2)
            logging.debug(f"Error: {e}")
        name_b = fill_with_holder(bigb, char_name_maxcount * 2, 0)
        #home_name_b = fill_with_holder(bigb, char_name_maxcount * 2, 0x20)
        home_name_b = fill_with_holder(bigb, char_name_maxcount * 2 + 2, 0x7EA9) # 最多3個字，然後"居"字填充
        write_file_byte_raw(f, char_name_address, name_b)
        write_file_byte_raw(f, char_home_name_address, home_name_b)
        logging.debug("重寫人物姓名 -> %s 主角居 -> %s" % (name_b.decode("big5"), home_name_b.decode("big5")))

        posx = char_position[0]
        posy = char_position[1]
        write_file_byte(f, char_position_address, 2, posx)
        write_file_byte(f, char_position_address+2, 2, posy)
        logging.debug("重寫人物位置 -> (%d,%d)" % (posx, posy))

        logging.debug("重寫人物屬性")
        for key, val in char_attributes_address.items():
            address = char_attributes_address[key]
            value = char_attributes_value[key]
            logging.debug("重寫 -> %s: %d" % (key, value))
            write_file_byte(f, address, 2, value)

        logging.debug("重寫人物武功")
        for x in range(0, char_martial_maxcount):
            address = char_martial_type_start_address + x * char_martial_type_address_step
            mtype = char_martial_type_list[x]
            logging.debug("重寫 -> 武功%d: %s" % (x + 1, martial_name_from_type(mtype)))
            write_file_byte(f, address, char_martial_type_address_step, mtype)

            address = char_martial_tier_start_address + x * char_martial_tier_address_step
            tier = char_martial_tier_list[x]
            logging.debug("重寫 -> 武功%d 等級: %s" % (x + 1, martial_ladder_from_tier(tier)))
            write_file_byte(f, address, char_martial_tier_address_step, tier)

        logging.debug("重寫隊友列表")
        for x in range(0, team_members_maxcount):
            address = team_members_start_address + x * team_members_address_step
            member = team_members_list[x]
            value = team_members_names[member]
            logging.debug("重寫 -> 隊友%d : %s" % (x + 1, member))
            write_file_byte(f, address, team_members_address_step, value, unsigned=True) #註意：隊友數據是無符號short

    logging.debug("重寫人物數據 完成.")

    logging.debug("重寫動態數據 開始:")
    with open(dync_file_path, 'r+b') as f:
        logging.debug("清空商人從前位置")
        for key, val in merchant_positions.items():
            if key != merc_position:
                address = val
                clear_merc_byte(f, address)
        logging.debug("重寫 -> 商人新位置: %s" % merc_position)
        address = merchant_positions[merc_position]
        write_merc_byte(f, address)

    logging.debug("重寫動態數據 完成.")

    logging.debug("重寫遊戲數據 開始:")
    with open(zdata_file_path, 'r+b') as f:
        logging.debug("重寫 -> 中毒除數: %d" % zdata_venom_divisor_value)
        write_file_byte(f, zdata_venom_divisor_address, 2, zdata_venom_divisor_value)

    logging.debug("重寫遊戲數據 完成.")

# 清空商人坐標文件位置
def clear_merc_byte(f, address):
    write_file_byte(f, address, 2, 0x0000)
    write_file_byte(f, address + 2, 2, 0x0000)
    write_file_byte(f, address + 4, 2, 0xFFFF)
    write_file_byte(f, address + 10, 2, 0xFFFF)
    write_file_byte(f, address + 12, 2, 0xFFFF)
    write_file_byte(f, address + 14, 2, 0xFFFF)

# 寫入商人位置
'''
xx xx xx xx xxxx (FFFF FFFF) xxxx xxxx xxxx
xx xx xx xx：
0100 0100代表小宝人物在，如果是0000，就会穿过人物；人物不在时为0000，不显示人物
xxxx:
AA03代表小宝对话事件，改为其他的对话内容会改变，甚至可能变开箱子，比如AA00变成“跟定逸师太战斗”，
人物不在时为FFFF，无事件
(FFFF FFFF)间隔不用管，不用设置
xxxx xxxx xxxx ：4020 4020 4020代表小宝造型，换成其他值，会变成不同图块
如果不显示小宝，就设置为0000 0000 FFFF (FFFF FFFF) FFFF FFFF FFFF，()中不用设置
所以，当更改小宝位置时，要把其他4个客栈的小宝位置清空，
只保留一个0100 0100 AA03 (FFFF FFFF) 4020 4020 4020
'''
def write_merc_byte(f, address):
    # little endian
    write_file_byte(f, address, 2, 0x0001)
    write_file_byte(f, address + 2, 2, 0x0001)
    write_file_byte(f, address + 4, 2, 0x03AA)
    write_file_byte(f, address + 10, 2, 0x2040)
    write_file_byte(f, address + 12, 2, 0x2040)
    write_file_byte(f, address + 14, 2, 0x2040)

# 全局主函數
if __name__ == '__main__':
    main_entry_point()
